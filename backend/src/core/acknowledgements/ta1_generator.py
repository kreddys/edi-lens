import logging # <-- Add logging import
from typing import Optional, List
from src.core.cdm import CdmSegment
from .ta1_defs import InterchangeError, TA1AcknowledgementCode, TA1NoteCode

logger = logging.getLogger(__name__) # <-- Add logger instance

class TA1Generator:
    def generate(
        self,
        isa_header: CdmSegment,
        errors: List[InterchangeError]
    ) -> Optional[str]:
        """
        Generates a TA1 segment string if required.
        Returns None if no TA1 should be generated (file is accepted and no ack was requested).
        """
        if not isa_header or not isa_header.elements or len(isa_header.elements) < 16:
            logger.debug("TA1 Gen: ISA header is malformed or missing. Cannot generate TA1.")
            return None

        # --- DEBUG LOGGING ---
        ack_requested_value = isa_header.get_element(14)
        logger.debug(f"TA1 Gen: Raw ISA14 value: '{ack_requested_value}' (type: {type(ack_requested_value)})")
        
        ack_requested = ack_requested_value.strip() == "1" if ack_requested_value else False
        has_errors = bool(errors)

        logger.debug(f"TA1 Gen: ack_requested evaluated to: {ack_requested}")
        logger.debug(f"TA1 Gen: has_errors evaluated to: {has_errors}")
        # --- END DEBUG LOGGING ---

        if not has_errors and not ack_requested:
            logger.debug("TA1 Gen: Condition met (no errors AND no ack requested). Returning None.")
            return None

        ack_code: TA1AcknowledgementCode
        note_code: TA1NoteCode

        if not has_errors:
            ack_code = TA1AcknowledgementCode.ACCEPTED
            note_code = TA1NoteCode.NO_ERROR
        else:
            ack_code = TA1AcknowledgementCode.REJECTED
            note_code = errors[0].note_code
        
        icn = isa_header.get_element(13).strip().zfill(9)
        date_str = isa_header.get_element(9)
        time_str = isa_header.get_element(10)
        
        date = date_str[2:] if len(date_str) == 8 else date_str
        time = time_str

        ta1_segment = (
            f"TA1*{icn}*{date}*{time}*"
            f"{ack_code.value}*{note_code.value}"
        )
        
        logger.debug(f"TA1 Gen: Successfully generated TA1 segment: {ta1_segment}")
        return ta1_segment