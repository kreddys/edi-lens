# FILE: backend/src/services/edi_validation_service.py

from typing import List, Optional
import time
import logging

from src.api.schemas import ValidationFinding, FindingLocation
from src.core.schema_manager import SchemaManager
from src.core.acknowledgements.ta1_generator import TA1Generator
from src.core.edi_parser import EdiParser
from src.core.cdm import CdmSegment, CdmElement

logger = logging.getLogger(__name__)

class ValidationResult:
    """Container for validation results."""
    def __init__(self, valid: bool, findings: List[ValidationFinding]):
        self.valid = valid
        self.findings = findings

class EDIValidationService:
    """Service for EDI document validation and acknowledgment generation."""
    
    def __init__(self):
        self.schema_manager = SchemaManager()
        self.ta1_generator = TA1Generator()
    
    async def validate_edi(
        self,
        edi_content: str,
        schema_name: str,
        tenant_id: str,
        snip_level: int = 3
    ) -> ValidationResult:
        """
        Validate EDI content against specified schema using the robust EdiParser.
        
        Args:
            edi_content: The EDI document content
            schema_name: Name of the schema to validate against
            tenant_id: Tenant identifier for schema access
            snip_level: SNIP validation level (1-5)
            
        Returns:
            ValidationResult containing validation status and findings
        """
        try:
            logger.info(f"Starting EDI validation with schema: {schema_name}, SNIP level: {snip_level}")
            
            # Load validation schema
            schema = self.schema_manager.get_schema(schema_name, tenant_id)
            if not schema:
                raise ValueError(f"Schema not found: {schema_name}")
            
            # Use the robust EdiParser for validation
            parser = EdiParser(edi_content, schema)
            
            # Parse and validate the EDI document
            interchange = parser.parse()
            
            # Convert CDM validation errors to ValidationFindings
            findings = []
            for error in parser.errors:
                finding = ValidationFinding(
                    level="error",
                    code=error.error_code if hasattr(error, 'error_code') else "VALIDATION_ERROR",
                    message=error.message,
                    location=FindingLocation(
                        segment_id=error.segment_id if hasattr(error, 'segment_id') else "UNKNOWN",
                        segment_instance=error.segment_instance if hasattr(error, 'segment_instance') else 1,
                        element_position=error.element_position if hasattr(error, 'element_position') else 1,
                        line_number=error.line_number if hasattr(error, 'line_number') else 1
                    )
                )
                findings.append(finding)
            
            # Determine if document is valid (no errors)
            is_valid = len(parser.errors) == 0
            
            logger.info(f"Validation completed: valid={is_valid}, findings={len(findings)}")
            
            return ValidationResult(valid=is_valid, findings=findings)
            
        except Exception as e:
            logger.error(f"EDI validation failed: {e}", exc_info=True)
            
            # Return error as validation finding
            error_finding = ValidationFinding(
                level="error",
                code="VALIDATION_ERROR",
                message=f"Validation failed: {str(e)}",
                location=FindingLocation(
                    segment_id="DOCUMENT",
                    segment_instance=1,
                    element_position=1,
                    line_number=1
                )
            )
            
            return ValidationResult(valid=False, findings=[error_finding])
    
    async def generate_ta1(
        self,
        edi_content: str,
        validation_errors: List[ValidationFinding] = None
    ) -> Optional[str]:
        """
        Generate TA1 acknowledgment for EDI document.
        
        Args:
            edi_content: Original EDI document content
            validation_errors: List of validation errors found
            
        Returns:
            TA1 acknowledgment content or None if generation fails
        """
        try:
            logger.info("Generating TA1 acknowledgment")
            
            # Extract ISA header information from EDI content
            isa_info = self._extract_isa_info(edi_content)
            
            # Determine acknowledgment code based on validation errors
            ack_code = "A"  # Accept
            error_code = None
            
            if validation_errors:
                errors = [f for f in validation_errors if f.level == "error"]
                if errors:
                    ack_code = "R"  # Reject
                    error_code = "001"  # Generic error code
            
            # Generate TA1 using your existing robust TA1Generator
            # Convert the EDI content to get ISA header as CdmSegment
            isa_segment = self._extract_isa_segment(edi_content)
            
            # Convert validation errors to InterchangeErrors (if needed)
            interchange_errors = []  # For now, simplified approach
            
            ta1_content = self.ta1_generator.generate(
                isa_header=isa_segment,
                errors=interchange_errors
            )
            
            logger.info(f"TA1 generation completed with ack_code: {ack_code}")
            return ta1_content
            
        except Exception as e:
            logger.error(f"TA1 generation failed: {e}", exc_info=True)
            return None
    
    # Removed old validation methods - now using robust EdiParser
    
    def _extract_isa_segment(self, edi_content: str) -> Optional[CdmSegment]:
        """Extract ISA header as CdmSegment for TA1 generation."""
        try:
            lines = edi_content.strip().split('\n')
            if lines:
                first_line = lines[0].strip()
                if first_line.startswith('ISA'):
                    # Remove trailing segment terminator if present
                    raw_segment = first_line
                    if first_line.endswith('~'):
                        first_line = first_line[:-1]
                    
                    # Split ISA elements
                    elements = first_line.split('*')
                    if len(elements) >= 16:
                        # Create CdmElement objects for each element
                        cdm_elements = []
                        for i, element_value in enumerate(elements[1:], 1):  # Skip the segment ID
                            cdm_elements.append(CdmElement(
                                element_id=f"ISA{i:02d}",
                                value=element_value,
                                position=i
                            ))
                        
                        # Create CdmSegment with proper fields
                        isa_segment = CdmSegment(
                            segment_id="ISA",
                            elements=cdm_elements,
                            line_number=1,
                            raw_segment=raw_segment
                        )
                        return isa_segment
            
            logger.error("Failed to extract valid ISA segment from EDI content")
            return None
            
        except Exception as e:
            logger.error(f"ISA segment extraction failed: {e}", exc_info=True)
            return None
    
    def _extract_isa_info(self, edi_content: str) -> dict:
        """Extract ISA header information for TA1 generation."""
        try:
            lines = edi_content.strip().split('\n')
            if lines:
                first_line = lines[0].strip()
                if first_line.startswith('ISA'):
                    # Remove trailing segment terminator if present
                    if first_line.endswith('~'):
                        first_line = first_line[:-1]
                    
                    # Split ISA elements
                    elements = first_line.split('*')
                    if len(elements) >= 16:
                        return {
                            'interchange_control_number': elements[13],
                            'sender_id': elements[6],
                            'receiver_id': elements[8],
                            'date': elements[9],
                            'time': elements[10]
                        }
            
            # Default values if parsing fails
            return {
                'interchange_control_number': '000000001',
                'sender_id': 'UNKNOWN',
                'receiver_id': 'UNKNOWN',
                'date': '250101',
                'time': '1200'
            }
            
        except Exception as e:
            logger.error(f"ISA info extraction failed: {e}", exc_info=True)
            # Return default values
            return {
                'interchange_control_number': '000000001',
                'sender_id': 'UNKNOWN',
                'receiver_id': 'UNKNOWN',
                'date': '250101',
                'time': '1200'
            }