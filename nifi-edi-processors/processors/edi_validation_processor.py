"""
EDI Validation Processor for Apache NiFi

Native Python processor that validates EDI documents against schemas without requiring
external API calls. Replaces the backend API-based validation with direct processing.
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any

# NiFi processor imports (these would be available in NiFi environment)
try:
    from nifiapi.flowfiletransform import FlowFileTransform, FlowFileTransformResult
    from nifiapi.properties import PropertyDescriptor, StandardValidators, ExpressionLanguageScope
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

# Import our EDI common modules
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from edi_common.validation_service import EDIValidationService, ValidationResult

logger = logging.getLogger(__name__)

class EDIValidationProcessor(FlowFileTransform):
    """
    NiFi processor for validating EDI documents against implementation guide schemas.
    
    This processor replaces HTTP API calls to the backend validation service with
    native EDI processing capabilities within NiFi.
    """
    
    class Java:
        implements = ['org.apache.nifi.python.processor.FlowFileTransform']
    
    class ProcessorDetails:
        version = '1.0.0'
        description = """Validates EDI content against specified schemas using native Python processing.
        Supports tenant-specific schemas and configurable SNIP validation levels.
        Outputs validation results as FlowFile attributes and JSON content."""
        tags = ['edi', 'validation', 'x12', 'healthcare']
    
    # Processor properties
    VALIDATION_SCHEMA = PropertyDescriptor(
        name="Validation Schema",
        description="EDI schema file to validate against (e.g., '270.5010.X279.A1.json')",
        required=True,
        default_value="${validation.schema}",
        expression_language_scope=ExpressionLanguageScope.FLOWFILE_ATTRIBUTES
    )
    
    SNIP_LEVEL = PropertyDescriptor(
        name="SNIP Level", 
        description="Validation strictness level (1-5, where 5 is most strict)",
        required=True,
        default_value="3",
        allowable_values=["1", "2", "3", "4", "5"],
        expression_language_scope=ExpressionLanguageScope.FLOWFILE_ATTRIBUTES
    )
    
    TENANT_ID = PropertyDescriptor(
        name="Tenant ID",
        description="Tenant identifier for multi-tenant schema support",
        required=True,
        default_value="${tenant.id}",
        expression_language_scope=ExpressionLanguageScope.FLOWFILE_ATTRIBUTES
    )
    
    SCHEMA_BASE_PATH = PropertyDescriptor(
        name="Schema Base Path",
        description="Base directory containing EDI schema files",
        required=False,
        default_value="/opt/nifi/schemas"
    )
    
    CACHE_SCHEMAS = PropertyDescriptor(
        name="Cache Schemas",
        description="Enable schema caching for improved performance",
        required=False,
        default_value="true",
        allowable_values=["true", "false"]
    )
    
    # Relationships
    REL_SUCCESS = "success"
    REL_FAILURE = "failure"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.validation_service = None
    
    def getPropertyDescriptors(self):
        return [
            self.VALIDATION_SCHEMA,
            self.SNIP_LEVEL, 
            self.TENANT_ID,
            self.SCHEMA_BASE_PATH,
            self.CACHE_SCHEMAS
        ]
    
    def getRelationships(self):
        return [self.REL_SUCCESS, self.REL_FAILURE]
    
    def onScheduled(self, context):
        """Initialize the validation service when processor is scheduled."""
        try:
            schema_base_path = context.getProperty(self.SCHEMA_BASE_PATH).getValue()
            self.validation_service = EDIValidationService(schema_base_path)
            logger.info(f"EDI Validation Processor scheduled with schema path: {schema_base_path}")
        except Exception as e:
            logger.error(f"Failed to initialize validation service: {e}")
            raise
    
    def transform(self, context, flowFile):
        """
        Transform the FlowFile by validating its EDI content.
        
        Args:
            context: ProcessContext
            flowFile: FlowFile containing EDI content
            
        Returns:
            FlowFileTransformResult with validation results
        """
        try:
            # Get processor properties
            schema_name = context.getProperty(self.VALIDATION_SCHEMA).evaluateAttributeExpressions(flowFile).getValue()
            snip_level = int(context.getProperty(self.SNIP_LEVEL).evaluateAttributeExpressions(flowFile).getValue())
            tenant_id = context.getProperty(self.TENANT_ID).evaluateAttributeExpressions(flowFile).getValue()
            
            # Get EDI content from FlowFile
            edi_content = flowFile.getContentsAsBytes().decode('utf-8')
            
            logger.info(f"Validating EDI for tenant {tenant_id} with schema {schema_name}, SNIP level {snip_level}")
            
            # Perform validation
            validation_result = self.validation_service.validate_edi(
                edi_content=edi_content,
                schema_name=schema_name,
                tenant_id=tenant_id,
                snip_level=snip_level
            )
            
            # Prepare result attributes
            result_attributes = {
                "edi.validation.valid": str(validation_result.valid).lower(),
                "edi.validation.findings.count": str(len(validation_result.findings)),
                "edi.validation.schema": schema_name,
                "edi.validation.snip.level": str(snip_level),
                "edi.validation.processed.at": datetime.now().isoformat(),
                "edi.validation.tenant.id": tenant_id
            }
            
            # Create JSON output with validation results
            output_data = {
                "valid": validation_result.valid,
                "findings": [
                    {
                        "level": finding.level,
                        "code": finding.code,
                        "message": finding.message,
                        "location": finding.location
                    }
                    for finding in validation_result.findings
                ],
                "schema_used": schema_name,
                "snip_level_used": snip_level,
                "processed_at": datetime.now().isoformat(),
                "tenant_id": tenant_id
            }
            
            # Convert to JSON string
            json_output = json.dumps(output_data, indent=2)
            
            logger.info(f"Validation completed: valid={validation_result.valid}, findings={len(validation_result.findings)}")
            
            return FlowFileTransformResult(
                relationship=self.REL_SUCCESS,
                contents=json_output,
                attributes=result_attributes
            )
            
        except Exception as e:
            logger.error(f"EDI validation processing failed: {e}", exc_info=True)
            
            # Return error result
            error_attributes = {
                "edi.validation.error": str(e),
                "edi.validation.error.type": "PROCESSING_ERROR",
                "edi.validation.processed.at": datetime.now().isoformat()
            }
            
            error_data = {
                "valid": False,
                "error": str(e),
                "error_type": "PROCESSING_ERROR",
                "processed_at": datetime.now().isoformat()
            }
            
            return FlowFileTransformResult(
                relationship=self.REL_FAILURE,
                contents=json.dumps(error_data, indent=2),
                attributes=error_attributes
            )