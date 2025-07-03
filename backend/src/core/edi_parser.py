import re
from typing import List, Optional

# Import the Pydantic models we defined for our API
from src.api.schemas import EdiSegment, EdiElement

class ParseEdiResult:
    """A simple class to hold the result of the parsing operation."""
    def __init__(self, segments: List[EdiSegment], delimiters: dict, error: Optional[str] = None):
        self.segments = segments
        self.delimiters = delimiters
        self.error = error

def parse_edi(raw_edi_string: str) -> ParseEdiResult:
    """
    Parses a raw X12 EDI string into a list of segments and detects delimiters.
    This version uses a more robust normalization strategy.
    """
    # <<< THIS IS OUR PROOF THAT THE NEW CODE IS RUNNING >>>
    print("\n\n--- RUNNING LATEST ROBUST PARSER (v2) ---\n\n")
    
    print("[PARSE] Starting EDI document parsing")

    if not raw_edi_string or not raw_edi_string.strip():
        print("[PARSE] Input string is empty")
        return ParseEdiResult(segments=[], delimiters={}, error="EDI string is empty.")

    # --- Step 1: Basic Normalization (line endings) ---
    edi_content = raw_edi_string.replace('\r\n', '\n').replace('\r', '\n')

    # --- Step 2: Detect Delimiters ---
    element_delimiter = '*'
    segment_delimiter = '~'
    if edi_content.startswith('ISA') and len(edi_content) >= 106:
        print("[PARSE] Found ISA segment, detecting delimiters.")
        element_delimiter = edi_content[3]
        segment_delimiter = edi_content[105]
    else:
        print("[PARSE] ISA segment not found or too short. Using default delimiters.")

    segment_delimiter_display = '\\n' if segment_delimiter == '\n' else segment_delimiter
    print(f"[PARSE] Using Delimiters - Element: '{element_delimiter}', Segment: '{segment_delimiter_display}'")

    # --- Step 3: Robust Segment Splitting ---
    # Replace the detected segment delimiter with a newline, UNLESS it's already a newline.
    if segment_delimiter != '\n':
        edi_content = edi_content.replace(segment_delimiter, '\n')
    
    # Now, the entire document is consistently delimited by newlines. We can safely split by it.
    segment_strings = edi_content.split('\n')
    
    print(f"[PARSE] Found {len(segment_strings)} potential segment strings after normalization")

    # --- Step 4: Process each segment string ---
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
            print(f"[PARSE] Invalid or non-standard segment ID '{segment_id}' found at line {line_number}. Skipping.")
            continue
        
        print(f"[PARSE-VALID] Identified segment {segment_id} (Line {line_number})")

        elements = [EdiElement(value=val) for val in parts[1:]]
        
        segments.append(
            EdiSegment(
                id=segment_id,
                elements=elements,
                line_number=line_number,
            )
        )

    if not segments:
        return ParseEdiResult(segments=[], delimiters={}, error="No valid segments found after parsing.")

    print(f"[PARSE] Successfully parsed {len(segments)} total segments")

    return ParseEdiResult(
        segments=segments,
        delimiters={ "element": element_delimiter, "segment": segment_delimiter },
        error=None
    )