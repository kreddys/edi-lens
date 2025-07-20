# FILE: backend/src/core/edi_parser.py
import logging
from typing import List, Optional, Tuple

# --- THIS IS THE FIX: Import the new v2-compatible models ---
from src.edi_schemas.edi_guide import ImplementationGuideSchema, StructureLoop, StructureSegment, StructureChild
from src.core.cdm import CdmInterchange, CdmFunctionalGroup, CdmTransaction, CdmLoop, CdmSegment, CdmElement, CdmValidationError

logger = logging.getLogger(__name__)

def get_guide_version_from_edi(edi_string: str) -> Optional[str]:
    # This logic remains the same as it reads the raw EDI string
    element_delimiter = '*'
    segment_delimiter = '~'

    clean_edi = edi_string.strip()
    if clean_edi.startswith('ISA') and len(clean_edi) >= 106:
        element_delimiter = clean_edi[103]
        segment_delimiter = clean_edi[105]

    if segment_delimiter in ('\r', '\n'):
        edi_for_splitting = clean_edi.replace('\r\n', '\n').replace('\r', '\n')
    else:
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

    # --- The _detect_delimiters and _segmentize_and_parse methods are unchanged ---
    def _detect_delimiters(self, edi_string: str) -> Tuple[str, str, str]:
        clean_edi = edi_string.strip()
        if clean_edi.startswith('ISA') and len(clean_edi) >= 106:
            element_delimiter = clean_edi[103]
            segment_terminator = clean_edi[105]
            component_separator = clean_edi[104]
            return element_delimiter, segment_terminator, component_separator
        logger.warning("Could not find standard ISA segment. Falling back to default delimiters ('*', '~', ':').")
        return '*', '~', ':'

    def _segmentize_and_parse(self, edi_string: str) -> List[CdmSegment]:
        element_delimiter, segment_terminator, _ = self._detect_delimiters(edi_string)
        segments = []
        edi_content = edi_string.strip().replace('\r\n', '\n').replace('\r', '\n')
        if segment_terminator != '\n':
            edi_content = edi_content.replace('\n', '')
        raw_segments = edi_content.split(segment_terminator)
        for i, seg_str in enumerate(raw_segments):
            clean_seg = seg_str.strip()
            if not clean_seg: continue
            parts = clean_seg.split(element_delimiter)
            segment_id = parts[0]
            elements = [CdmElement(value=val, position=i + 1) for i, val in enumerate(parts[1:])]
            segments.append(CdmSegment(segment_id=segment_id, elements=elements, line_number=i + 1, raw_segment=clean_seg))
            if segment_id == 'IEA': break
        return segments
    
    def _find_next_segment(self, segment_id: str, segments: List[CdmSegment], start_index: int) -> int:
        for i in range(start_index, len(segments)):
            if segments[i].segment_id == segment_id:
                return i
        return -1

    # --- This logic is updated to use the new model attributes ---
    def _get_starting_segment_id(self, node: StructureChild) -> Optional[str]:
        if isinstance(node, StructureSegment):
            return node.xid
        if isinstance(node, StructureLoop) and node.children:
            return self._get_starting_segment_id(node.children[0])
        return None

    def _build_tree(self, segments: List[CdmSegment], schema_nodes: List[StructureChild]) -> Tuple[CdmLoop, int]:
        cdm_loop = CdmLoop(loop_id="level_content")
        cursor = 0
        
        for schema_node in schema_nodes:
            if cursor >= len(segments): break

            max_repeats = 1
            if isinstance(schema_node, StructureLoop):
                repeat_str = str(schema_node.repeat).replace('>', '')
                max_repeats = int(repeat_str) if repeat_str.isdigit() else 99999
            elif isinstance(schema_node, StructureSegment):
                max_repeats = schema_node.max_use

            for i in range(max_repeats):
                if cursor >= len(segments): break
                
                current_segment = segments[cursor]
                logger.debug(f"  Cursor {cursor}: Segment '{current_segment.segment_id}'. Evaluating schema node '{schema_node.xid}' (Repetition {i+1}/{max_repeats})")

                if isinstance(schema_node, StructureSegment) and current_segment.segment_id == schema_node.xid:
                    logger.debug(f"    -> MATCH (Segment): Consuming '{schema_node.xid}'")
                    cdm_loop.segments.append(current_segment)
                    cursor += 1
                elif isinstance(schema_node, StructureLoop) and self._get_starting_segment_id(schema_node) == current_segment.segment_id:
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

    # --- This logic is updated for the new v2 schema structure ---
    def _parse_transaction_set(self, segments: List[CdmSegment]) -> CdmTransaction:
        st_segment = segments[0]
        se_segment = segments[-1]
        transaction_body_segments = segments[1:-1]
        
        # The structure is now a list of loops at the root
        isa_loop = next((n for n in self.schema.structure if n.xid == 'ISA_LOOP'), None)
        if not isa_loop: raise ValueError("ISA_LOOP not found in schema structure")
        gs_loop = next((n for n in isa_loop.children if n.xid == 'GS_LOOP'), None)
        if not gs_loop: raise ValueError("GS_LOOP not found in schema structure")
        st_loop_schema = next((n for n in gs_loop.children if n.xid == 'ST_LOOP'), None)
        if not st_loop_schema: raise ValueError("ST_LOOP not found in schema structure")
        
        # The content of the transaction is the children of ST_LOOP, excluding the ST and SE segments themselves
        st_loop_children = [child for child in st_loop_schema.children if child.xid not in ('ST', 'SE')]

        body_loop, consumed_count = self._build_tree(transaction_body_segments, st_loop_children)
        body_loop.loop_id = "ST_LOOP"

        transaction = CdmTransaction(header=st_segment, trailer=se_segment, body=body_loop)
        transaction.errors.extend(body_loop.errors)

        if consumed_count != len(transaction_body_segments):
            # This error handling logic is still valid
            error_line, error_seg_id, message_detail = None, None, ""
            if consumed_count < len(transaction_body_segments):
                problematic_segment = transaction_body_segments[consumed_count]
                error_line, error_seg_id = problematic_segment.line_number, problematic_segment.segment_id
                message_detail = f"Unexpected structure or missing mandatory segment at or before '{error_seg_id}' (line {error_line})."
            
            transaction.errors.append(CdmValidationError(
                message=f"Transaction parsing incomplete. {message_detail}",
                line_number=error_line,
                segment_id=error_seg_id
            ))

        return transaction

    # --- The main parse() method remains largely unchanged ---
    def parse(self) -> CdmInterchange:
        self.errors.clear()
        isa_idx = self._find_next_segment('ISA', self.all_segments, 0)
        iea_idx = self._find_next_segment('IEA', self.all_segments, isa_idx if isa_idx != -1 else 0)
        if isa_idx == -1 or iea_idx == -1:
            self.errors.append(CdmValidationError(message="ISA/IEA envelope not found."))
            return CdmInterchange(header=CdmSegment(...), trailer=CdmSegment(...), errors=self.errors)

        interchange = CdmInterchange(header=self.all_segments[isa_idx], trailer=self.all_segments[iea_idx])
        group_segments = self.all_segments[isa_idx + 1:iea_idx]
        cursor = 0
        while cursor < len(group_segments):
            gs_idx = self._find_next_segment('GS', group_segments, cursor)
            if gs_idx == -1: break
            ge_idx = self._find_next_segment('GE', group_segments, gs_idx)
            if ge_idx == -1:
                interchange.errors.append(CdmValidationError(message=f"Unclosed functional group at line {group_segments[gs_idx].line_number}."))
                break
            func_group = CdmFunctionalGroup(header=group_segments[gs_idx], trailer=group_segments[ge_idx])
            transaction_segments = group_segments[gs_idx + 1:ge_idx]
            ts_cursor = 0
            while ts_cursor < len(transaction_segments):
                st_idx = self._find_next_segment('ST', transaction_segments, ts_cursor)
                if st_idx == -1: break
                se_idx = self._find_next_segment('SE', transaction_segments, st_idx)
                if se_idx == -1:
                    interchange.errors.append(CdmValidationError(message=f"Unclosed transaction set at line {transaction_segments[st_idx].line_number}."))
                    break
                single_transaction_block = transaction_segments[st_idx : se_idx + 1]
                cdm_transaction = self._parse_transaction_set(single_transaction_block)
                func_group.transactions.append(cdm_transaction)
                ts_cursor = se_idx + 1
            interchange.functional_groups.append(func_group)
            cursor = ge_idx + 1
        return interchange
    