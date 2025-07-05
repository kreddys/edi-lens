import re
from typing import List, Optional
import logging
from src.api.schemas import EdiSegment, EdiElement

logger = logging.getLogger(__name__)

class ParseEdiResult:
    def __init__(self, segments: List[EdiSegment], delimiters: dict, error: Optional[str] = None):
        self.segments = segments
        self.delimiters = delimiters
        self.error = error

def parse_edi(raw_edi_string: str) -> ParseEdiResult:
    """
    Parses a raw X12 EDI string into a list of segments and detects delimiters.
    """
    logger.info("Using robust EDI parser v2 to parse EDI data.")
    
    if not raw_edi_string or not raw_edi_string.strip():
        logger.warning("EDI string is empty.")
        return ParseEdiResult(segments=[], delimiters={}, error="EDI string is empty.")

    edi_content = raw_edi_string.replace('\r\n', '\n').replace('\r', '\n')

    element_delimiter = '*'
    segment_delimiter = '~'
    if edi_content.startswith('ISA') and len(edi_content) >= 106:
        logger.debug("Found ISA segment, detecting delimiters from standard location.")
        element_delimiter = edi_content[3]
        segment_delimiter = edi_content[105]
    else:
        logger.debug("ISA segment not found or too short. Using default delimiters.")

    segment_delimiter_display = '\\n' if segment_delimiter == '\n' else segment_delimiter
    logger.debug(f"Using Delimiters - Element: '{element_delimiter}', Segment: '{segment_delimiter_display}'")

    if segment_delimiter != '\n':
        edi_content = edi_content.replace(segment_delimiter, '\n')
    
    segment_strings = edi_content.split('\n')
    logger.debug(f"Found {len(segment_strings)} potential segment strings after normalization.")

    segments: List[EdiSegment] = []
    segment_id_regex = re.compile(r'^[A-Z0-9]{2,3}$')

    for i, raw_segment in enumerate(segment_strings):
        line_number = i + 1 
        trimmed_segment = raw_segment.strip()
        
        if not trimmed_segment:
            continue

        parts = trimmed_segment.split(element_delimiter)
        segment_id = parts[0]

        if not segment_id_regex.match(segment_id):
            logger.debug(f"Invalid or non-standard segment ID '{segment_id}' found at line {line_number}. Skipping.")
            continue
        
        logger.debug(f"Identified segment {segment_id} (Line {line_number})")
        elements = [EdiElement(value=val) for val in parts[1:]]
        
        segments.append(
            EdiSegment(id=segment_id, elements=elements, line_number=line_number)
        )

    if not segments:
        logger.warning("No valid segments found after parsing EDI string.")
        return ParseEdiResult(segments=[], delimiters={}, error="No valid segments found after parsing.")

    logger.info(f"Successfully parsed {len(segments)} total segments.")

    return ParseEdiResult(
        segments=segments,
        delimiters={ "element": element_delimiter, "segment": segment_delimiter },
        error=None
    )