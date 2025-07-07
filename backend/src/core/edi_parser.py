import logging
from typing import List, Optional, Tuple, Iterator
from itertools import tee

from src.edi_schemas.edi_guide import ImplementationGuideSchema, StructureLoopDefinition, StructureSegmentDefinition, StructureChild
from src.core.cdm import CdmTransaction, CdmLoop, CdmSegment, CdmElement

logger = logging.getLogger(__name__)

def get_guide_version_from_edi(edi_string: str) -> Optional[str]:
    """
    Quickly extracts the GS08 value (implementation guide version) from a raw EDI string.
    This version is robust against various line endings and whitespace.
    """
    element_delimiter = '*'
    segment_delimiter = '~'

    clean_edi = edi_string.strip()
    if clean_edi.startswith('ISA') and len(clean_edi) >= 106:
        element_delimiter = clean_edi[3]
        segment_delimiter = clean_edi[105]

    for segment in clean_edi.split(segment_delimiter):
        clean_segment = segment.strip()
        if clean_segment.startswith("GS" + element_delimiter):
            parts = clean_segment.split(element_delimiter)
            if len(parts) > 8:
                return parts[8]
    return None

class EdiParser:
    """
    A schema-driven EDI parser that transforms a raw EDI string into a
    structured Canonical Data Model (CDM).
    """
    def __init__(self, edi_string: str, schema: ImplementationGuideSchema):
        self.raw_edi: str = edi_string
        self.schema: ImplementationGuideSchema = schema
        self.element_delimiter: str = '*'
        self.segment_delimiter: str = '~'
        self._detect_delimiters()
        
        segments = self._segmentize(edi_string)
        self.segments: List[Tuple[int, str]] = segments
        self.segment_cursor: int = 0

    def _detect_delimiters(self):
        clean_edi = self.raw_edi.strip()
        if clean_edi.startswith('ISA') and len(clean_edi) >= 106:
            self.element_delimiter = clean_edi[3]
            self.segment_delimiter = clean_edi[105]

    def _segmentize(self, edi_string: str) -> List[Tuple[int, str]]:
        segments = []
        edi_content = edi_string.strip().replace('\r\n', '').replace('\n', '')
        raw_segments = edi_content.split(self.segment_delimiter)
        for i, seg_str in enumerate(raw_segments):
            if seg_str:
                segments.append((i + 1, seg_str))
        return segments

    def _parse_segment_string(self, line_number: int, raw_segment: str) -> CdmSegment:
        parts = raw_segment.split(self.element_delimiter)
        segment_id = parts[0]
        elements = [CdmElement(value=val, position=i + 1) for i, val in enumerate(parts[1:])]
        return CdmSegment(segment_id=segment_id, elements=elements, line_number=line_number, raw_segment=raw_segment)
        
    def _peek_segment_id(self) -> Optional[str]:
        """Looks at the ID of the next segment without advancing the cursor."""
        if self.segment_cursor < len(self.segments):
            _ , segment_str = self.segments[self.segment_cursor]
            return segment_str.split(self.element_delimiter)[0]
        return None

    def _consume_segment(self) -> CdmSegment:
        """Consumes and parses the next segment, advancing the cursor."""
        line_num, segment_str = self.segments[self.segment_cursor]
        self.segment_cursor += 1
        return self._parse_segment_string(line_num, segment_str)

    def parse(self) -> CdmTransaction:
        # Skip ISA, GS
        self.segment_cursor = 2
        
        # Consume ST
        st_segment = self._consume_segment()
        if st_segment.segment_id != 'ST':
             raise ValueError("ST segment not found or out of order.")

        # The schema for the transaction body starts within the ST_LOOP
        isa_loop_schema = self.schema.structure[0]
        gs_loop_schema = isa_loop_schema.children[1]
        st_loop_schema = gs_loop_schema.children[1]
        
        transaction_body_loop = CdmLoop(loop_id="body")
        self._parse_level(st_loop_schema.children, transaction_body_loop)

        # Consume SE
        se_segment = self._consume_segment()
        if se_segment.segment_id != 'SE':
             raise ValueError("SE segment not found at expected position.")

        return CdmTransaction(header=st_segment, trailer=se_segment, body=transaction_body_loop)

    def _parse_level(self, level_schema: List[StructureChild], parent_cdm_loop: CdmLoop):
        """
        Statefully parses one hierarchical level of the EDI structure.
        """
        for schema_node in level_schema:
            if isinstance(schema_node, StructureLoopDefinition):
                repeat_count_str = str(schema_node.repeat).replace('>', '')
                max_repeats = int(repeat_count_str) if repeat_count_str.isdigit() else 99999
                
                for _ in range(max_repeats):
                    next_segment_id = self._peek_segment_id()
                    if not next_segment_id: break
                    
                    loop_start_id = schema_node.children[0].xid
                    if next_segment_id == loop_start_id:
                        new_cdm_loop = CdmLoop(loop_id=schema_node.xid)
                        parent_cdm_loop.add_loop(new_cdm_loop)
                        self._parse_level(schema_node.children, new_cdm_loop)
                    else:
                        break # Done with repetitions of this loop
            
            elif isinstance(schema_node, StructureSegmentDefinition):
                for _ in range(schema_node.max_use):
                    next_segment_id = self._peek_segment_id()
                    if not next_segment_id: break

                    if next_segment_id == schema_node.xid:
                        parsed_segment = self._consume_segment()
                        parent_cdm_loop.segments.append(parsed_segment)
                    else:
                        break # Done with repetitions of this segment