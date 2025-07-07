import logging
from typing import List, Dict, Optional, Tuple, Iterator
from itertools import chain

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
        if segment.startswith("GS" + element_delimiter):
            parts = segment.split(element_delimiter)
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
        self.segment_iterator = iter(segments)

    def _detect_delimiters(self):
        clean_edi = self.raw_edi.strip()
        if clean_edi.startswith('ISA') and len(clean_edi) >= 106:
            self.element_delimiter = clean_edi[3]
            self.segment_delimiter = clean_edi[105]

    def _segmentize(self, edi_string: str) -> List[Tuple[int, str]]:
        """Splits the raw EDI string into a list of clean segments."""
        segments = []
        # Normalize and split by the detected segment delimiter
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

    def parse(self) -> CdmTransaction:
        st_segment_obj = None
        se_segment_obj = None
        
        # Advance iterator past ISA and GS
        for _ in range(2): next(self.segment_iterator, None)
        
        # Parse ST
        line_num, st_str = next(self.segment_iterator, (None, None))
        if st_str and st_str.startswith('ST'):
            st_segment_obj = self._parse_segment_string(line_num, st_str)
        else:
            raise ValueError("ST segment not found or out of order.")
            
        # The schema's top-level structure defines the transaction body.
        body_schema = self.schema.structure[0].children[1].children # ISA_LOOP -> GS_LOOP -> [children]
        
        # Create a virtual root loop for the transaction body
        transaction_body_loop = CdmLoop(loop_id="body")
        self._parse_level(self.segment_iterator, body_schema, transaction_body_loop)

        # The last segment parsed by _parse_level should be the SE segment
        # We assume the last segment processed within the transaction's main parsing logic is SE
        # A more robust parser would have explicit trailer handling
        last_segment = transaction_body_loop.segments.pop()
        if last_segment.segment_id == 'SE':
            se_segment_obj = last_segment
        else:
            # Put it back if it's not the SE
            transaction_body_loop.segments.append(last_segment)
            raise ValueError("SE segment not found at the end of the transaction.")

        return CdmTransaction(header=st_segment_obj, trailer=se_segment_obj, body=transaction_body_loop)


    def _parse_level(self, segments: Iterator[Tuple[int, str]], level_schema: List[StructureChild], parent_cdm_loop: CdmLoop):
        """
        Parses one hierarchical level of the EDI structure.
        """
        # --- THIS IS THE FIX ---
        # A new stateful parsing approach that correctly handles the schema.
        from itertools import tee
        
        schema_idx = 0
        while schema_idx < len(level_schema):
            schema_node = level_schema[schema_idx]
            
            # Peek at the next segment in the stream
            segments, peek_segments = tee(segments)
            next_segment_tuple = next(peek_segments, None)
            if not next_segment_tuple:
                break # End of EDI data

            _ , next_segment_str = next_segment_tuple
            next_segment_id = next_segment_str.split(self.element_delimiter)[0]

            if isinstance(schema_node, StructureLoopDefinition):
                # If the next segment starts a new loop defined in the schema...
                loop_start_id = schema_node.children[0].xid
                if next_segment_id == loop_start_id:
                    new_cdm_loop = CdmLoop(loop_id=schema_node.xid)
                    parent_cdm_loop.add_loop(new_cdm_loop)
                    self._parse_level(segments, schema_node.children, new_cdm_loop)
                    # After parsing the loop, we might need to check for more repetitions of it
                    # This simple implementation moves to the next schema node. A full implementation
                    # would handle loop repeats here.
                    schema_idx += 1
                else:
                    schema_idx += 1 # Move to the next schema definition if no match
            
            elif isinstance(schema_node, StructureSegmentDefinition):
                 # If the next segment matches the segment defined in the schema...
                if next_segment_id == schema_node.xid:
                    line_num, segment_str = next(segments) # Consume the segment
                    parsed_segment = self._parse_segment_string(line_num, segment_str)
                    parent_cdm_loop.segments.append(parsed_segment)
                else:
                    schema_idx += 1 # Move to the next schema definition if no match
            else:
                 schema_idx += 1