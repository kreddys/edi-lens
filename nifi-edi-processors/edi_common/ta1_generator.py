# Ported from backend/src/core/acknowledgements/ta1_generator.py
import logging
from datetime import datetime
from typing import Optional, List
from cdm import CdmSegment
from ta1_defs import InterchangeError, TA1AcknowledgementCode, TA1NoteCode

logger = logging.getLogger(__name__)

class TA1Generator:
    """
    Generates TA1 acknowledgments for EDI interchanges.
    Ported from backend for use in NiFi processors.
    """
    
    def generate(
        self,
        isa_header: CdmSegment,
        errors: List[InterchangeError],
        force_generation: bool = False
    ) -> Optional[str]:
        """
        Generates a complete TA1 EDI interchange (ISA + TA1 + IEA) if required.
        Returns None if no TA1 should be generated (file is accepted and no ack was requested).
        
        Args:
            isa_header: The ISA segment from the original interchange
            errors: List of interchange errors
            force_generation: Generate TA1 even if not requested
            
        Returns:
            Complete TA1 interchange string or None
        """
        if not isa_header or not isa_header.elements or len(isa_header.elements) < 16:
            logger.debug("TA1 Gen: ISA header is malformed or missing. Cannot generate TA1.")
            return None

        # Check if acknowledgment was requested (ISA14)
        ack_requested_value = isa_header.get_element(14)
        logger.debug(f"TA1 Gen: Raw ISA14 value: '{ack_requested_value}' (type: {type(ack_requested_value)})")
        
        ack_requested = ack_requested_value.strip() == "1" if ack_requested_value else False
        has_errors = bool(errors)

        logger.debug(f"TA1 Gen: ack_requested evaluated to: {ack_requested}")
        logger.debug(f"TA1 Gen: has_errors evaluated to: {has_errors}")

        # Don't generate TA1 if no errors and no acknowledgment requested (unless forced)
        if not has_errors and not ack_requested and not force_generation:
            logger.debug("TA1 Gen: Condition met (no errors AND no ack requested). Returning None.")
            return None

        # Determine acknowledgment and note codes
        if not has_errors:
            ack_code = TA1AcknowledgementCode.ACCEPTED
            note_code = TA1NoteCode.NO_ERROR
        else:
            ack_code = TA1AcknowledgementCode.REJECTED
            note_code = errors[0].note_code
        
        # Extract data from original ISA header
        original_icn = isa_header.get_element(13).strip().zfill(9)
        original_date_str = isa_header.get_element(9)
        original_time_str = isa_header.get_element(10)
        
        # Prepare TA1 segment data
        ta1_date = original_date_str[2:] if len(original_date_str) == 8 else original_date_str
        ta1_time = original_time_str

        # Generate current timestamp for response ISA
        now = datetime.now()
        response_date = now.strftime("%y%m%d")  # YYMMDD format
        response_time = now.strftime("%H%M")    # HHMM format
        
        # Generate unique interchange control number for response
        response_icn = now.strftime("%y%m%d%H%M").zfill(9)
        
        # Extract original sender/receiver info (swap for response)
        original_auth_qual = isa_header.get_element(1) or "00"
        original_auth_info = isa_header.get_element(2) or " " * 10
        original_security_qual = isa_header.get_element(3) or "00" 
        original_security_info = isa_header.get_element(4) or " " * 10
        original_sender_qual = isa_header.get_element(5) or "ZZ"
        original_sender_id = isa_header.get_element(6) or " " * 15
        original_receiver_qual = isa_header.get_element(7) or "ZZ"
        original_receiver_id = isa_header.get_element(8) or " " * 15
        original_standards_id = isa_header.get_element(11) or "^"
        original_version = isa_header.get_element(12) or "00501"
        original_test_indicator = isa_header.get_element(15) or "P"
        original_component_separator = isa_header.get_element(16) or ">"
        
        # Create TA1 segment
        ta1_segment = (
            f"TA1*{original_icn}*{ta1_date}*{ta1_time}*"
            f"{ack_code.value}*{note_code.value}"
        )
        
        # Create ISA header for TA1 response (sender/receiver swapped)
        isa_response = (
            f"ISA*{original_auth_qual}*{original_auth_info}*"
            f"{original_security_qual}*{original_security_info}*"
            f"{original_receiver_qual}*{original_receiver_id}*"  # Swapped: original receiver becomes sender
            f"{original_sender_qual}*{original_sender_id}*"      # Swapped: original sender becomes receiver
            f"{response_date}*{response_time}*{original_standards_id}*"
            f"{original_version}*{response_icn}*0*{original_test_indicator}*{original_component_separator}~"
        )
        
        # Create IEA trailer
        iea_response = f"IEA*1*{response_icn}~"
        
        # Create complete TA1 interchange following official specification:
        # ISA + TA1 + IEA (no GS/GE envelope structure)
        ta1_interchange = f"{isa_response}{ta1_segment}~{iea_response}"
        
        logger.debug(f"TA1 Gen: Successfully generated TA1 interchange: {ta1_interchange}")
        return ta1_interchange