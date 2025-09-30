# Ported from backend/src/services/edi_validation_service.py
from typing import List, Optional
import logging

from edi_parser import EdiParser
from schema_manager import SchemaManager

logger = logging.getLogger(__name__)

class ValidationFinding:
    """Container for validation findings (simplified for NiFi)."""
    def __init__(self, level: str, code: str, message: str, location: Optional[dict] = None):
        self.level = level
        self.code = code
        self.message = message
        self.location = location or {}

class ValidationResult:
    """Container for validation results."""
    def __init__(self, valid: bool, findings: List[ValidationFinding]):
        self.valid = valid
        self.findings = findings

class EDIValidationService:
    """Service for EDI document validation and acknowledgment generation."""
    
    def __init__(self, schema_base_path: str = "/opt/nifi/schemas"):
        self.schema_manager = SchemaManager(schema_base_path)
    
    def validate_edi(
        self,
        edi_content: str,
        schema_name: str,
        snip_level: int = 3
    ) -> ValidationResult:
        """
        Validate EDI content against specified schema using the robust EdiParser.
        
        Args:
            edi_content: The EDI document content
            schema_name: Name of the schema to validate against
            snip_level: SNIP validation level (1-5)
            
        Returns:
            ValidationResult containing validation status and findings
        """
        try:
            logger.info(f"Starting EDI validation with schema: {schema_name}, SNIP level: {snip_level}")
            
            # Load validation schema (use base schema directly)
            schema = self.schema_manager.get_base_schema(schema_name)
            if not schema:
                raise ValueError(f"Schema not found: {schema_name}")
            
            # Use the EdiParser for validation
            parser = EdiParser(edi_content, schema)
            
            # Parse and validate the EDI document
            interchange = parser.parse()
            
            # Collect all errors from the interchange
            all_errors = parser._collect_all_errors(interchange)
            
            # Convert CDM validation errors to ValidationFindings
            findings = []
            for location, error in all_errors:
                finding = ValidationFinding(
                    level="error",
                    code=error.element_xid or "VALIDATION_ERROR",
                    message=error.message,
                    location={
                        "context": location,
                        "segment_id": error.segment_id or "UNKNOWN",
                        "line_number": error.line_number or 1
                    }
                )
                findings.append(finding)
            
            # Determine if document is valid (no errors)
            is_valid = len(findings) == 0
            
            logger.info(f"Validation completed: valid={is_valid}, findings={len(findings)}")
            
            return ValidationResult(valid=is_valid, findings=findings)
            
        except Exception as e:
            logger.error(f"EDI validation failed: {e}", exc_info=True)
            
            # Return error as validation finding
            error_finding = ValidationFinding(
                level="error",
                code="VALIDATION_ERROR",
                message=f"Validation failed: {str(e)}",
                location={
                    "context": "DOCUMENT",
                    "segment_id": "DOCUMENT",
                    "line_number": 1
                }
            )
            
            return ValidationResult(valid=False, findings=[error_finding])