# FILE: backend/src/services/edi_validation_service.py

from typing import List, Optional
import time
import logging

from src.api.schemas import ValidationFinding
from src.core.schema_manager import SchemaManager
from src.core.acknowledgements.ta1_generator import TA1Generator

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
        snip_level: int = 3
    ) -> ValidationResult:
        """
        Validate EDI content against specified schema.
        
        Args:
            edi_content: The EDI document content
            schema_name: Name of the schema to validate against
            snip_level: SNIP validation level (1-5)
            
        Returns:
            ValidationResult containing validation status and findings
        """
        try:
            logger.info(f"Starting EDI validation with schema: {schema_name}, SNIP level: {snip_level}")
            
            # Load validation schema
            schema = await self.schema_manager.get_schema(schema_name)
            if not schema:
                raise ValueError(f"Schema not found: {schema_name}")
            
            # Parse EDI content
            segments = self._parse_edi_content(edi_content)
            
            # Perform validation
            findings = await self._validate_segments(segments, schema, snip_level)
            
            # Determine if document is valid (no errors, warnings are ok)
            errors = [f for f in findings if f.level == "error"]
            is_valid = len(errors) == 0
            
            logger.info(f"Validation completed: valid={is_valid}, findings={len(findings)}")
            
            return ValidationResult(valid=is_valid, findings=findings)
            
        except Exception as e:
            logger.error(f"EDI validation failed: {e}", exc_info=True)
            
            # Return error as validation finding
            error_finding = ValidationFinding(
                level="error",
                code="VALIDATION_ERROR",
                message=f"Validation failed: {str(e)}",
                location={"segment": "DOCUMENT", "element": 1}
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
            
            # Generate TA1
            ta1_content = await self.ta1_generator.generate_ta1(
                isa_info=isa_info,
                ack_code=ack_code,
                error_code=error_code
            )
            
            logger.info(f"TA1 generation completed with ack_code: {ack_code}")
            return ta1_content
            
        except Exception as e:
            logger.error(f"TA1 generation failed: {e}", exc_info=True)
            return None
    
    def _parse_edi_content(self, edi_content: str) -> List[dict]:
        """Parse EDI content into segments."""
        # Simplified EDI parsing - in production, use proper EDI parser
        segments = []
        lines = edi_content.strip().split('\n')
        
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue
                
            # Split by segment terminator
            if line.endswith('~'):
                line = line[:-1]
            
            # Split elements by delimiter
            elements = line.split('*')
            if elements:
                segments.append({
                    'id': elements[0],
                    'elements': elements[1:] if len(elements) > 1 else [],
                    'line_number': line_num
                })
        
        return segments
    
    async def _validate_segments(
        self,
        segments: List[dict],
        schema: dict,
        snip_level: int
    ) -> List[ValidationFinding]:
        """Validate parsed segments against schema."""
        findings = []
        
        # Basic validation logic - in production, implement full EDI validation
        try:
            # Check for required ISA header
            if not segments or segments[0]['id'] != 'ISA':
                findings.append(ValidationFinding(
                    level="error",
                    code="MISSING_ISA",
                    message="ISA header segment is required",
                    location={"segment": "ISA", "element": 1}
                ))
            
            # Check ISA element count
            if segments and segments[0]['id'] == 'ISA':
                isa_elements = segments[0]['elements']
                if len(isa_elements) < 16:
                    findings.append(ValidationFinding(
                        level="error",
                        code="ISA_ELEMENT_COUNT",
                        message=f"ISA segment requires 16 elements, found {len(isa_elements)}",
                        location={"segment": "ISA", "element": len(isa_elements) + 1}
                    ))
            
            # Additional validations would go here based on schema and SNIP level
            logger.debug(f"Segment validation completed with {len(findings)} findings")
            
        except Exception as e:
            logger.error(f"Segment validation error: {e}", exc_info=True)
            findings.append(ValidationFinding(
                level="error",
                code="VALIDATION_ERROR",
                message=f"Validation error: {str(e)}",
                location={"segment": "UNKNOWN", "element": 1}
            ))
        
        return findings
    
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