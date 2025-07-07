import logging
from typing import List, Optional, Tuple

from src.edi_schemas.edi_guide import ImplementationGuideSchema, StructureLoopDefinition, StructureSegmentDefinition, StructureChild
from src.core.cdm import CdmTransaction, CdmLoop, CdmSegment, CdmElement

logger = logging.getLogger(__name__)

def get_guide_version_from_edi(edi_string: str) -> Optional[str]:
    element_delimiter, segment_delimiter = '*', '~'
    clean_edi = edi_string.strip()
    if clean_edi.startswith('ISA') and len(clean_edi) >= 106:
        element_delimiter = clean_edi[3]
        segment_delimiter = clean_edi[105]
    for segment in clean_edi.split(segment_delimiter):
        clean_segment = segment.strip()
        if clean_segment.startswith("GS" + element_delimiter):
            parts = clean_segment.split(element_delimiter)
            if len(parts) > 8: return parts[8]
    return None

class EdiParser:
    def __init__(self, edi_string: str, schema: ImplementationGuideSchema):
        self.schema = schema
        self.segments: List[CdmSegment] = self._segmentize_and_parse(edi_string)
        logger.debug(f"Parser initialized with {len(self.segments)} segments.")

    def _segmentize_and_parse(self, edi_string: str) -> List[CdmSegment]:
        element_delimiter, segment_delimiter = self._detect_delimiters(edi_string)
        segments = []
        edi_content = edi_string.strip().replace('\r\n', '\n').replace('\r', '')
        raw_segments = edi_content.split(segment_delimiter)
        for i, seg_str in enumerate(raw_segments):
            if clean_seg := seg_str.strip():
                parts = clean_seg.split(element_delimiter)
                segments.append(CdmSegment(
                    segment_id=parts[0],
                    elements=[CdmElement(value=val, position=i + 1) for i, val in enumerate(parts[1:])],
                    line_number=i + 1,
                    raw_segment=clean_seg
                ))
        return segments

    def _detect_delimiters(self, edi_string: str) -> Tuple[str, str]:
        clean_edi = edi_string.strip()
        if clean_edi.startswith('ISA') and len(clean_edi) >= 106: return clean_edi[3], clean_edi[105]
        return '*', '~'
    
    def _find_schema_node_for_segment(self, schema_nodes: List[StructureChild], segment_id: str) -> Optional[StructureChild]:
        for node in schema_nodes:
            if isinstance(node, StructureSegmentDefinition) and node.xid == segment_id:
                return node
            if isinstance(node, StructureLoopDefinition) and node.children and node.children[0].xid == segment_id:
                return node
        return None

    def _build_tree(self, segments: List[CdmSegment], schema_nodes: List[StructureChild]) -> Tuple[CdmLoop, int]:
        cdm_loop = CdmLoop(loop_id="level_content")
        cursor = 0
        
        # Iterate through the schema rules for the current level
        for schema_node in schema_nodes:
            if cursor >= len(segments): break

            # Determine max repetitions for the current schema node
            max_repeats = 1
            if isinstance(schema_node, StructureLoopDefinition):
                repeat_str = str(schema_node.repeat).replace('>', '')
                max_repeats = int(repeat_str) if repeat_str.isdigit() else 99999
            elif isinstance(schema_node, StructureSegmentDefinition):
                max_repeats = schema_node.max_use

            # Process repetitions of the current schema node
            for i in range(max_repeats):
                if cursor >= len(segments): break
                
                current_segment = segments[cursor]
                logger.debug(f"  Cursor {cursor}: Segment '{current_segment.segment_id}'. Evaluating schema node '{schema_node.xid}' (Repetition {i+1}/{max_repeats})")

                if isinstance(schema_node, StructureSegmentDefinition) and current_segment.segment_id == schema_node.xid:
                    logger.debug(f"    -> MATCH (Segment): Consuming '{schema_node.xid}'")
                    cdm_loop.segments.append(current_segment)
                    cursor += 1
                elif isinstance(schema_node, StructureLoopDefinition) and schema_node.children and current_segment.segment_id == schema_node.children[0].xid:
                    logger.debug(f"    -> MATCH (Loop): Descending into '{schema_node.xid}'")
                    sub_loop, segments_consumed = self._build_tree(segments[cursor:], schema_node.children)
                    sub_loop.loop_id = schema_node.xid
                    cdm_loop.add_loop(sub_loop)
                    cursor += segments_consumed
                else:
                    # The current segment doesn't match this schema node, so stop trying to find repetitions
                    logger.debug(f"    -> NO MATCH. Moving to next schema node.")
                    break
        
        return cdm_loop, cursor

    def parse(self) -> CdmTransaction:
        logger.debug("--- PARSE START ---")
        st_idx = next((i for i, s in enumerate(self.segments) if s.segment_id == 'ST'), -1)
        se_idx = next((i for i, s in enumerate(self.segments) if s.segment_id == 'SE'), -1)
        if st_idx == -1: raise ValueError("ST segment not found.")
        if se_idx == -1: raise ValueError("SE segment not found at end of transaction.")

        st_segment = self.segments[st_idx]
        se_segment = self.segments[se_idx]
        
        transaction_segments = self.segments[st_idx + 1:se_idx]
        logger.debug(f"Found ST at index {st_idx}, SE at {se_idx}. Processing {len(transaction_segments)} segments.")
        
        isa_loop = next((n for n in self.schema.structure if isinstance(n, StructureLoopDefinition) and n.xid == 'ISA_LOOP'))
        gs_loop = next((n for n in isa_loop.children if isinstance(n, StructureLoopDefinition) and n.xid == 'GS_LOOP'))
        st_loop_schema = next((n for n in gs_loop.children if isinstance(n, StructureLoopDefinition) and n.xid == 'ST_LOOP'))
        
        body_loop, consumed_count = self._build_tree(transaction_segments, st_loop_schema.children)
        body_loop.loop_id = "ST_LOOP"

        logger.debug(f"--- PARSE COMPLETE. Total segments consumed in body: {consumed_count} ---")
        if consumed_count != len(transaction_segments):
             raise ValueError(f"Parsing finished unexpectedly. Consumed {consumed_count} of {len(transaction_segments)} segments.")

        return CdmTransaction(header=st_segment, trailer=se_segment, body=body_loop)