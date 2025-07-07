import logging
from typing import List, Optional, Tuple

from src.edi_schemas.edi_guide import ImplementationGuideSchema, StructureLoopDefinition, StructureSegmentDefinition, StructureChild
from src.core.cdm import CdmInterchange, CdmFunctionalGroup, CdmTransaction, CdmLoop, CdmSegment, CdmElement, CdmValidationError

logger = logging.getLogger(__name__)

def get_guide_version_from_edi(edi_string: str) -> Optional[str]:
    # This initial detection is a "best guess" before full parsing
    element_delimiter = '*'
    segment_delimiter = '~'

    clean_edi = edi_string.strip()
    # A standard X12 file will have the ISA segment as the first 106 characters
    if clean_edi.startswith('ISA') and len(clean_edi) >= 106:
        element_delimiter = clean_edi[103]
        segment_delimiter = clean_edi[105]

    # Handle the edge case where the segment delimiter itself is a newline
    if segment_delimiter in ('\r', '\n'):
        # Normalize all line endings to the detected delimiter
        edi_for_splitting = clean_edi.replace('\r\n', '\n').replace('\r', '\n')
    else:
        # If the delimiter is a normal character, we can safely split by it
        edi_for_splitting = clean_edi

    for segment in edi_for_splitting.split(segment_delimiter):
        clean_segment = segment.strip()
        if clean_segment.startswith("GS" + element_delimiter):
            parts = clean_segment.split(element_delimiter)
            if len(parts) > 8: return parts[8]
    return None

class EdiParser:
    def __init__(self, edi_string: str, schema: ImplementationGuideSchema):
        self.schema = schema
        self.all_segments: List[CdmSegment] = self._segmentize_and_parse(edi_string)
        self.errors: List[CdmValidationError] = []
        logger.debug(f"Parser initialized with {len(self.all_segments)} segments.")

    def _detect_delimiters(self, edi_string: str) -> Tuple[str, str, str]:
        """
        Detects the element delimiter, segment terminator, and component separator from the ISA segment.
        Returns defaults if ISA is not present or malformed.
        """
        clean_edi = edi_string.strip()
        if clean_edi.startswith('ISA') and len(clean_edi) >= 106:
            # ISA segment has a fixed length of 106 characters (including the segment ID 'ISA')
            element_delimiter = clean_edi[103]
            segment_terminator = clean_edi[105]
            component_separator = clean_edi[104]
            return element_delimiter, segment_terminator, component_separator
        
        # Fallback to defaults if ISA is not standard
        logger.warning("Could not find standard ISA segment. Falling back to default delimiters ('*', '~', ':').")
        return '*', '~', ':'


    def _segmentize_and_parse(self, edi_string: str) -> List[CdmSegment]:
        """
        Tokenizes the raw EDI string into a list of CdmSegment objects using the
        delimiters specified in the ISA segment.
        """
        element_delimiter, segment_terminator, _ = self._detect_delimiters(edi_string)
        segments = []
        
        # First, normalize all possible line endings to a single character (\n)
        # This simplifies the logic without destroying a potential \n or \r delimiter.
        edi_content = edi_string.strip().replace('\r\n', '\n').replace('\r', '\n')

        # If the segment terminator is NOT a newline, we can safely remove all newlines
        # before splitting. This handles files that use both newlines AND a character
        # terminator (e.g., ~) for readability.
        if segment_terminator != '\n':
            edi_content = edi_content.replace('\n', '')

        raw_segments = edi_content.split(segment_terminator)

        for i, seg_str in enumerate(raw_segments):
            clean_seg = seg_str.strip()
            if not clean_seg:
                continue

            parts = clean_seg.split(element_delimiter)
            segment_id = parts[0]
            elements = [CdmElement(value=val, position=i + 1) for i, val in enumerate(parts[1:])]
            
            segments.append(CdmSegment(
                segment_id=segment_id,
                elements=elements,
                line_number=i + 1,
                raw_segment=clean_seg
            ))
            
            if segment_id == 'IEA':
                break
                
        return segments

    def _find_next_segment(self, segment_id: str, segments: List[CdmSegment], start_index: int) -> int:
        for i in range(start_index, len(segments)):
            if segments[i].segment_id == segment_id:
                return i
        return -1

    def _get_starting_segment_id(self, node: StructureChild) -> Optional[str]:
        if isinstance(node, StructureSegmentDefinition):
            return node.xid
        if isinstance(node, StructureLoopDefinition) and node.children:
            return self._get_starting_segment_id(node.children[0])
        return None

    def _build_tree(self, segments: List[CdmSegment], schema_nodes: List[StructureChild]) -> Tuple[CdmLoop, int]:
        cdm_loop = CdmLoop(loop_id="level_content")
        cursor = 0
        
        for schema_node in schema_nodes:
            if cursor >= len(segments): break

            max_repeats = 1
            if isinstance(schema_node, StructureLoopDefinition):
                repeat_str = str(schema_node.repeat).replace('>', '')
                max_repeats = int(repeat_str) if repeat_str.isdigit() else 99999
            elif isinstance(schema_node, StructureSegmentDefinition):
                max_repeats = schema_node.max_use

            for i in range(max_repeats):
                if cursor >= len(segments): break
                
                current_segment = segments[cursor]
                logger.debug(f"  Cursor {cursor}: Segment '{current_segment.segment_id}'. Evaluating schema node '{schema_node.xid}' (Repetition {i+1}/{max_repeats})")

                if isinstance(schema_node, StructureSegmentDefinition) and current_segment.segment_id == schema_node.xid:
                    logger.debug(f"    -> MATCH (Segment): Consuming '{schema_node.xid}'")
                    cdm_loop.segments.append(current_segment)
                    cursor += 1
                elif isinstance(schema_node, StructureLoopDefinition) and self._get_starting_segment_id(schema_node) == current_segment.segment_id:
                    logger.debug(f"    -> MATCH (Loop): Descending into '{schema_node.xid}'")
                    sub_loop, segments_consumed = self._build_tree(segments[cursor:], schema_node.children)
                    sub_loop.loop_id = schema_node.xid
                    cdm_loop.errors.extend(sub_loop.errors)
                    cdm_loop.add_loop(sub_loop)
                    cursor += segments_consumed
                else:
                    logger.debug(f"    -> NO MATCH. Moving to next schema node.")
                    break
        
        return cdm_loop, cursor
    def _parse_transaction_set(self, segments: List[CdmSegment]) -> CdmTransaction:
        st_segment = segments[0]
        se_segment = segments[-1]
        transaction_body_segments = segments[1:-1]
        
        isa_loop = next((n for n in self.schema.structure if isinstance(n, StructureLoopDefinition) and n.xid == 'ISA_LOOP'))
        gs_loop = next((n for n in isa_loop.children if isinstance(n, StructureLoopDefinition) and n.xid == 'GS_LOOP'))
        st_loop_schema = next((n for n in gs_loop.children if isinstance(n, StructureLoopDefinition) and n.xid == 'ST_LOOP'))
        st_loop_children = st_loop_schema.children[1:-1]

        body_loop, consumed_count = self._build_tree(transaction_body_segments, st_loop_children)
        body_loop.loop_id = "ST_LOOP"

        transaction = CdmTransaction(header=st_segment, trailer=se_segment, body=body_loop)
        
        transaction.errors.extend(body_loop.errors)

        if consumed_count != len(transaction_body_segments):
            error_line = None
            error_seg_id = None
            message_detail = f"Processed {consumed_count} segments, but expected to process {len(transaction_body_segments)} segments in the transaction body."

            if consumed_count < len(transaction_body_segments):
                problematic_segment = transaction_body_segments[consumed_count]
                error_line = problematic_segment.line_number
                error_seg_id = problematic_segment.segment_id
                message_detail = f"Unexpected structure or missing mandatory segment at or before '{error_seg_id}' (line {error_line}). {message_detail}"
            elif consumed_count == 0 and len(transaction_body_segments) > 0:
                error_line = transaction_body_segments[0].line_number
                error_seg_id = transaction_body_segments[0].segment_id
                message_detail = f"Could not parse transaction body starting with '{error_seg_id}' (line {error_line}). {message_detail}"


            error = CdmValidationError(
                message=f"Transaction parsing incomplete. {message_detail}",
                line_number=error_line,
                segment_id=error_seg_id
            )
            transaction.errors.append(error)

        return transaction

    def parse(self) -> CdmInterchange:
        self.errors.clear()
        
        isa_idx = self._find_next_segment('ISA', self.all_segments, 0)
        iea_idx = self._find_next_segment('IEA', self.all_segments, isa_idx if isa_idx != -1 else 0)

        if isa_idx == -1 or iea_idx == -1:
            self.errors.append(CdmValidationError(message="ISA/IEA envelope not found."))
            return CdmInterchange(
                header=self.all_segments[isa_idx] if isa_idx != -1 else CdmSegment(segment_id='ISA', elements=[], line_number=0, raw_segment=''),
                trailer=self.all_segments[iea_idx] if iea_idx != -1 else CdmSegment(segment_id='IEA', elements=[], line_number=0, raw_segment=''),
                errors=self.errors
            )

        interchange = CdmInterchange(header=self.all_segments[isa_idx], trailer=self.all_segments[iea_idx])
        
        group_segments = self.all_segments[isa_idx + 1:iea_idx]
        cursor = 0
        while cursor < len(group_segments):
            gs_idx = self._find_next_segment('GS', group_segments, cursor)
            if gs_idx == -1: break

            ge_idx = self._find_next_segment('GE', group_segments, gs_idx)
            if ge_idx == -1:
                interchange.errors.append(CdmValidationError(message=f"Unclosed functional group found at line {group_segments[gs_idx].line_number}."))
                break

            func_group = CdmFunctionalGroup(header=group_segments[gs_idx], trailer=group_segments[ge_idx])
            transaction_segments = group_segments[gs_idx + 1:ge_idx]
            ts_cursor = 0
            while ts_cursor < len(transaction_segments):
                st_idx = self._find_next_segment('ST', transaction_segments, ts_cursor)
                if st_idx == -1: break

                se_idx = self._find_next_segment('SE', transaction_segments, st_idx)
                if se_idx == -1:
                    interchange.errors.append(CdmValidationError(message=f"Unclosed transaction set found at line {transaction_segments[st_idx].line_number}."))
                    break
                
                single_transaction_block = transaction_segments[st_idx : se_idx + 1]
                cdm_transaction = self._parse_transaction_set(single_transaction_block)
                func_group.transactions.append(cdm_transaction)
                
                ts_cursor = se_idx + 1

            interchange.functional_groups.append(func_group)
            cursor = ge_idx + 1
            
        return interchange