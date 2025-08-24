"""
TA1 Generation Processor for Apache NiFi

Native Python processor that generates TA1 acknowledgments for EDI documents
based on validation results. Can be used standalone or integrated with the
EDI Validation Processor.
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, List

# NiFi processor imports (these would be available in NiFi environment)
try:
    from nifiapi.flowfiletransform import FlowFileTransform, FlowFileTransformResult
    from nifiapi.properties import PropertyDescriptor, StandardValidators, ExpressionLanguageScope
    from nifiapi.relationship import Relationship
except ImportError:
    # Fallback for development/testing
    class FlowFileTransform:
        pass
    class FlowFileTransformResult:
        def __init__(self, relationship: str, contents: str = None, attributes: Dict[str, str] = None):
            self.relationship = relationship
            self.contents = contents
            self.attributes = attributes or {}
    class PropertyDescriptor:
        def __init__(self, name: str, description: str, required: bool = False, 
                     default_value: str = None, allowable_values: list = None,
                     expression_language_scope: str = None):
            self.name = name
            self.description = description
            self.required = required
            self.default_value = default_value
            self.allowable_values = allowable_values
            self.expression_language_scope = expression_language_scope
    class StandardValidators:
        NON_EMPTY_VALIDATOR = "NON_EMPTY"
        POSITIVE_INTEGER_VALIDATOR = "POSITIVE_INTEGER"
    class ExpressionLanguageScope:
        FLOWFILE_ATTRIBUTES = "FLOWFILE_ATTRIBUTES"
    class Relationship:
        def __init__(self, name: str, description: str, auto_terminated: bool = False):
            self.name = name
            self.description = description
            self.auto_terminated = auto_terminated

# Import our EDI common modules (using simple relative imports as per NiFi Python Dev Guide)
from ta1_generator import TA1Generator
from ta1_defs import InterchangeError, TA1NoteCode
from edi_parser import EdiParser
from cdm import CdmSegment

logger = logging.getLogger(__name__)

class TA1GenerationProcessor(FlowFileTransform):
    """
    NiFi processor for generating TA1 acknowledgments from EDI documents.
    
    This processor can work standalone or be integrated with the EDI Validation
    Processor to create complete validation → TA1 generation workflows.
    """
    
    class Java:
        implements = ['org.apache.nifi.python.processor.FlowFileTransform']
    
    class ProcessorDetails:
        version = '1.0.0'
        description = """Generates TA1 acknowledgments for EDI documents based on validation results.
        Supports forced generation and configurable response formats.
        Routes original and TA1 content to separate outputs."""
        tags = ['edi', 'ta1', 'acknowledgment', 'x12']
        dependencies = ['pydantic>=2.0.0', 'typing-extensions>=4.0.0']
    
    # Processor properties
    GENERATE_TA1 = PropertyDescriptor(
        name="Generate TA1",
        description="Enable/disable TA1 generation",
        required=True,
        default_value="true",
        allowable_values=["true", "false"],
        expression_language_scope=ExpressionLanguageScope.FLOWFILE_ATTRIBUTES
    )
    
    FORCE_GENERATION = PropertyDescriptor(
        name="Force Generation",
        description="Generate TA1 even if not requested in ISA14",
        required=False,
        default_value="false",
        allowable_values=["true", "false"],
        expression_language_scope=ExpressionLanguageScope.FLOWFILE_ATTRIBUTES
    )
    
    VALIDATION_ERRORS_ATTRIBUTE = PropertyDescriptor(
        name="Validation Errors Attribute",
        description="FlowFile attribute containing validation errors (JSON format)",
        required=False,
        default_value="edi.validation.findings",
        expression_language_scope=ExpressionLanguageScope.FLOWFILE_ATTRIBUTES
    )
    
    INCLUDE_METADATA = PropertyDescriptor(
        name="Include Metadata",
        description="Include generation metadata in output",
        required=False,
        default_value="true",
        allowable_values=["true", "false"]
    )
    
    TENANT_ID = PropertyDescriptor(
        name="Tenant ID",
        description="Tenant identifier for multi-tenant support",
        required=False,
        default_value="${tenant.id}",
        expression_language_scope=ExpressionLanguageScope.FLOWFILE_ATTRIBUTES
    )
    
    # Relationships
    REL_TA1 = Relationship(
        name="ta1",
        description="Generated TA1 acknowledgment documents",
        auto_terminated=False
    )
    REL_ORIGINAL = Relationship(
        name="original",
        description="Original EDI documents that were processed",
        auto_terminated=False
    )
    REL_FAILURE = Relationship(
        name="failure", 
        description="FlowFiles that fail TA1 generation",
        auto_terminated=False
    )
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.ta1_generator = None
    
    def getPropertyDescriptors(self):
        return [
            self.GENERATE_TA1,
            self.FORCE_GENERATION,
            self.VALIDATION_ERRORS_ATTRIBUTE,
            self.INCLUDE_METADATA,
            self.TENANT_ID
        ]
    
    def getRelationships(self):
        return [self.REL_TA1, self.REL_ORIGINAL, self.REL_FAILURE]
    
    def onScheduled(self, context):
        """Initialize the TA1 generator when processor is scheduled."""
        try:
            self.ta1_generator = TA1Generator()
            logger.info("TA1 Generation Processor scheduled successfully")
        except Exception as e:
            logger.error(f"Failed to initialize TA1 generator: {e}")
            raise
    
    def _convert_validation_findings_to_errors(self, findings_json: str) -> List[InterchangeError]:
        """Convert validation findings JSON to InterchangeError objects."""
        try:
            findings = json.loads(findings_json) if findings_json else []
            errors = []
            
            for finding in findings:
                if finding.get('level') == 'error':
                    # Map finding codes to TA1 note codes (simplified mapping)
                    note_code = self._map_error_to_note_code(finding.get('code', ''))
                    
                    error = InterchangeError(
                        note_code=note_code,
                        details=finding.get('message', '')
                    )
                    errors.append(error)
            
            return errors
            
        except Exception as e:
            logger.warning(f"Failed to parse validation findings: {e}")
            return []
    
    def _map_error_to_note_code(self, error_code: str) -> TA1NoteCode:
        """Map validation error codes to TA1 note codes."""
        # Simplified mapping - in production, this would be more comprehensive
        error_mapping = {
            'SCHEMA_ERROR': TA1NoteCode.INVALID_INTERCHANGE_CONTENT,
            'VALIDATION_ERROR': TA1NoteCode.INVALID_INTERCHANGE_CONTENT,
            'SEGMENT_ERROR': TA1NoteCode.INVALID_CONTROL_STRUCTURE,
            'ELEMENT_ERROR': TA1NoteCode.INVALID_INTERCHANGE_CONTENT
        }
        
        return error_mapping.get(error_code, TA1NoteCode.INVALID_INTERCHANGE_CONTENT)
    
    def _extract_isa_header(self, edi_content: str) -> CdmSegment:
        """Extract ISA header from EDI content."""
        try:
            parser = EdiParser(edi_content)
            # Just parse enough to get the ISA segment
            segments = parser._segmentize(edi_content)
            
            # Find ISA segment
            for segment in segments:
                if segment.segment_id == 'ISA':
                    return segment
            
            raise ValueError("ISA segment not found in EDI content")
            
        except Exception as e:
            logger.error(f"Failed to extract ISA header: {e}")
            raise
    
    def transform(self, context, flowFile):
        """
        Transform the FlowFile by generating TA1 acknowledgments.
        
        Args:
            context: ProcessContext
            flowFile: FlowFile containing EDI content
            
        Returns:
            FlowFileTransformResult with TA1 or original content
        """
        try:
            # Get processor properties
            generate_ta1 = context.getProperty(self.GENERATE_TA1).evaluateAttributeExpressions(flowFile).getValue().lower() == "true"
            force_generation = context.getProperty(self.FORCE_GENERATION).evaluateAttributeExpressions(flowFile).getValue().lower() == "true"
            validation_errors_attr = context.getProperty(self.VALIDATION_ERRORS_ATTRIBUTE).evaluateAttributeExpressions(flowFile).getValue()
            include_metadata = context.getProperty(self.INCLUDE_METADATA).getValue().lower() == "true"
            tenant_id = context.getProperty(self.TENANT_ID).evaluateAttributeExpressions(flowFile).getValue()
            
            # Get EDI content from FlowFile
            edi_content = flowFile.getContentsAsBytes().decode('utf-8')
            
            if not generate_ta1:
                logger.info("TA1 generation disabled, routing to original")
                return self._route_original(edi_content, "generation_disabled", include_metadata, tenant_id)
            
            # Get validation errors from FlowFile attributes
            validation_errors_json = flowFile.getAttribute(validation_errors_attr) or "[]"
            interchange_errors = self._convert_validation_findings_to_errors(validation_errors_json)
            
            # Extract ISA header
            isa_header = self._extract_isa_header(edi_content)
            
            logger.info(f"Generating TA1 for tenant {tenant_id}, force_generation={force_generation}, errors={len(interchange_errors)}")
            
            # Generate TA1
            ta1_content = self.ta1_generator.generate(
                isa_header=isa_header,
                errors=interchange_errors,
                force_generation=force_generation
            )
            
            if ta1_content:
                return self._route_ta1(ta1_content, edi_content, interchange_errors, include_metadata, tenant_id)
            else:
                return self._route_original(edi_content, "not_requested", include_metadata, tenant_id)
                
        except Exception as e:
            logger.error(f"TA1 generation processing failed: {e}", exc_info=True)
            
            # Return error result
            error_attributes = {
                "ta1.error": str(e),
                "ta1.error.type": "GENERATION_ERROR",
                "ta1.processed.at": datetime.now().isoformat()
            }
            
            error_data = {
                "ta1_generated": False,
                "error": str(e),
                "error_type": "GENERATION_ERROR",
                "processed_at": datetime.now().isoformat()
            }
            
            return FlowFileTransformResult(
                relationship=self.REL_FAILURE,
                contents=json.dumps(error_data, indent=2),
                attributes=error_attributes
            )
    
    def _route_ta1(self, ta1_content: str, original_content: str, errors: List[InterchangeError], 
                   include_metadata: bool, tenant_id: str) -> FlowFileTransformResult:
        """Route to TA1 relationship with generated acknowledgment."""
        
        # Prepare TA1 attributes
        ta1_attributes = {
            "ta1.generated": "true",
            "ta1.content": ta1_content,
            "ta1.generated.at": datetime.now().isoformat(),
            "ta1.error.count": str(len(errors)),
            "ta1.acknowledgment.code": "R" if errors else "A"
        }
        
        if tenant_id:
            ta1_attributes["ta1.tenant.id"] = tenant_id
        
        # Create output data
        output_data = {
            "ta1_generated": True,
            "ta1_content": ta1_content,
            "original_content": original_content,
        }
        
        if include_metadata:
            output_data["metadata"] = {
                "generated_at": datetime.now().isoformat(),
                "acknowledgment_code": "R" if errors else "A",
                "error_count": len(errors),
                "tenant_id": tenant_id
            }
        
        logger.info(f"TA1 generated successfully with {len(errors)} errors")
        
        return FlowFileTransformResult(
            relationship=self.REL_TA1,
            contents=json.dumps(output_data, indent=2),
            attributes=ta1_attributes
        )
    
    def _route_original(self, original_content: str, reason: str, 
                       include_metadata: bool, tenant_id: str) -> FlowFileTransformResult:
        """Route to original relationship when no TA1 is needed."""
        
        # Prepare original attributes
        original_attributes = {
            "ta1.generated": "false",
            "ta1.reason": reason,
            "ta1.processed.at": datetime.now().isoformat()
        }
        
        if tenant_id:
            original_attributes["ta1.tenant.id"] = tenant_id
        
        # Create output data
        output_data = {
            "ta1_generated": False,
            "reason": reason,
            "original_content": original_content,
        }
        
        if include_metadata:
            output_data["processed_at"] = datetime.now().isoformat()
            output_data["tenant_id"] = tenant_id
        
        logger.info(f"TA1 not generated, reason: {reason}")
        
        return FlowFileTransformResult(
            relationship=self.REL_ORIGINAL,
            contents=json.dumps(output_data, indent=2),
            attributes=original_attributes
        )