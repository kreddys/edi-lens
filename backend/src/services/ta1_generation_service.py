# FILE: backend/src/services/ta1_generation_service.py

import logging
import time
from datetime import datetime
from typing import Optional

from src.core.acknowledgements.ta1_generator import TA1Generator
from src.core.acknowledgements.ta1_defs import InterchangeError, TA1NoteCode
from src.core.cdm import CdmSegment, CdmElement
from src.api.schemas import TA1GenerationRequest, TA1GenerationResponse

logger = logging.getLogger(__name__)

class TA1GenerationService:
    """Service for generating TA1 acknowledgments."""
    
    def __init__(self):
        self.ta1_generator = TA1Generator()
    
    async def generate_ta1(self, request: TA1GenerationRequest) -> TA1GenerationResponse:
        """
        Generate TA1 acknowledgment based on request parameters.
        
        Args:
            request: TA1 generation request
            
        Returns:
            TA1GenerationResponse containing generated acknowledgment
        """
        start_time = time.time()
        
        try:
            logger.info(f"Generating TA1 for workflow: {request.workflow_id}, ack_code: {request.acknowledgment_code}")
            
            # Extract ISA header from EDI content
            isa_segment = self._extract_isa_segment(request.edi_content)
            if not isa_segment:
                raise ValueError("Invalid EDI content: ISA segment not found or malformed")
            
            # Create interchange errors based on request
            interchange_errors = self._create_interchange_errors(
                acknowledgment_code=request.acknowledgment_code,
                error_code=request.error_code,
                error_note=request.error_note
            )
            
            # Generate TA1 using existing robust infrastructure
            ta1_content = self.ta1_generator.generate(
                isa_header=isa_segment,
                errors=interchange_errors
            )
            
            # Handle case where TA1Generator returns None
            if ta1_content is None:
                logger.error(f"TA1Generator returned None - this should not happen with forced acknowledgment")
                raise ValueError("TA1 generation failed: generator returned None")
            
            # Extract control number from generated TA1
            control_number = self._extract_ta1_control_number(ta1_content)
            
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            logger.info(f"TA1 generated successfully: control_number={control_number}, processing_time={processing_time_ms}ms")
            
            return TA1GenerationResponse(
                ta1_content=ta1_content,
                control_number=control_number,
                acknowledgment_code=request.acknowledgment_code,
                workflow_id=request.workflow_id,
                generated_at=datetime.utcnow(),
                processing_time_ms=processing_time_ms
            )
            
        except Exception as e:
            logger.error(f"TA1 generation failed for workflow {request.workflow_id}: {e}", exc_info=True)
            raise
    
    def _extract_isa_segment(self, edi_content: str) -> Optional[CdmSegment]:
        """Extract ISA header as CdmSegment from EDI content."""
        try:
            lines = edi_content.strip().split('\n')
            if not lines:
                logger.error("EDI content is empty")
                return None
                
            first_line = lines[0].strip()
            if not first_line.startswith('ISA'):
                logger.error(f"First line does not start with ISA: {first_line[:20]}...")
                return None
            
            # Store raw segment for debugging
            raw_segment = first_line
            
            # Remove segment terminator if present
            if first_line.endswith('~'):
                first_line = first_line[:-1]
            
            # Split ISA elements
            elements = first_line.split('*')
            if len(elements) < 17:  # ISA + 16 elements
                logger.error(f"ISA segment incomplete: expected 17 parts, got {len(elements)}")
                return None
            
            # Create CDM elements (skip segment ID)
            cdm_elements = []
            for i, element_value in enumerate(elements[1:], 1):
                # For TA1 generation API, we always want to force acknowledgment
                # by setting ISA14 to "1" if we're at position 14
                if i == 14:
                    element_value = "1"  # Force acknowledgment requested
                    logger.debug(f"Forcing ISA14 to '1' for TA1 generation")
                
                cdm_elements.append(CdmElement(
                    element_id=f"ISA{i:02d}",
                    value=element_value,
                    position=i
                ))
            
            logger.debug(f"Successfully extracted ISA segment with {len(cdm_elements)} elements")
            
            return CdmSegment(
                segment_id="ISA",
                elements=cdm_elements,
                line_number=1,
                raw_segment=raw_segment
            )
            
        except Exception as e:
            logger.error(f"ISA segment extraction failed: {e}", exc_info=True)
            return None
    
    def _create_interchange_errors(
        self, 
        acknowledgment_code: str,
        error_code: Optional[str] = None,
        error_note: Optional[str] = None
    ) -> list:
        """Create interchange errors based on acknowledgment parameters."""
        # For acceptance (A), return empty error list
        if acknowledgment_code == "A":
            logger.debug("Creating TA1 for acceptance - no errors")
            return []
        
        # For rejection (R) or error (E), create appropriate error
        errors = []
        
        if acknowledgment_code in ["R", "E"]:
            # Map common error codes to TA1NoteCode
            note_code_mapping = {
                "IK901": TA1NoteCode.INVALID_INTERCHANGE_CONTENT,
                "IK902": TA1NoteCode.INVALID_INTERCHANGE_CONTROL_NUMBER,
                "IK903": TA1NoteCode.ICN_MISMATCH_IN_HEADER_TRAILER,
                "IK904": TA1NoteCode.INVALID_INTERCHANGE_DATE,
                "IK905": TA1NoteCode.INVALID_INTERCHANGE_TIME
            }
            
            # Use provided error code or default
            note_code = note_code_mapping.get(error_code, TA1NoteCode.INVALID_INTERCHANGE_CONTENT)
            
            error = InterchangeError(
                note_code=note_code,
                details=error_note or "Interchange rejected"
            )
            errors.append(error)
            logger.debug(f"Created interchange error: note_code={note_code}, details={error.details}")
        
        return errors
    
    def _extract_ta1_control_number(self, ta1_content: str) -> str:
        """Extract control number from generated TA1."""
        try:
            if not ta1_content:
                logger.warning("TA1 content is None or empty")
                return "UNKNOWN"
                
            # TA1 format: TA1*<control_number>*<ack_code>~
            lines = ta1_content.strip().split('\n')
            for line in lines:
                if line.startswith('TA1*'):
                    elements = line.split('*')
                    if len(elements) >= 2:
                        control_number = elements[1]
                        logger.debug(f"Extracted TA1 control number: {control_number}")
                        return control_number
            
            logger.warning("Could not extract control number from TA1 - checking for TA1 segment")
            logger.debug(f"TA1 content for debugging: {ta1_content[:200]}...")
            return "UNKNOWN"
            
        except Exception as e:
            logger.error(f"TA1 control number extraction failed: {e}")
            return "UNKNOWN"