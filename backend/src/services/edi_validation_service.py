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
    
    