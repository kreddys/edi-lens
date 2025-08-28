"""
EDI Processor for Apache NiFi

Consolidated processor that handles:
1. EDI Validation against schemas
2. CDM JSON generation 
3. TA1 acknowledgment generation (configurable)
4. Future: 999 generation, conditional processing

Single, comprehensive EDI processing solution.
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional

# NiFi processor imports (these would be available in NiFi environment)
try:
    from nifiapi.flowfiletransform import FlowFileTransform, FlowFileTransformResult
    from nifiapi.properties import PropertyDescriptor, StandardValidators, ExpressionLanguageScope
    from nifiapi.relationship import Relationship
except ImportError:
    # Fallback for development/testing
    class FlowFileTransform:
        def __init__(self, **kwargs):
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
            
        def _get_object_id(self):
            return f"rel_{self.name}_{id(self)}"

# Import our EDI common modules
from validation_service import EDIValidationService, ValidationResult
from edi_parser import EdiParser
from ta1_generator import TA1Generator
from cdm import CdmInterchange, CdmFunctionalGroup, CdmTransaction, CdmSegment, CdmElement, CdmLoop, CdmValidationError

logger = logging.getLogger(__name__)

class EDIProcessor(FlowFileTransform):
    """
    Comprehensive NiFi processor for EDI processing.
    
    This processor consolidates validation, CDM generation, and TA1 acknowledgments
    into a single processor that handles all EDI processing needs.
    """
    
    class Java:
        implements = ['org.apache.nifi.python.processor.FlowFileTransform']
    
    class ProcessorDetails:
        version = '2.0.0'
        description = """EDI processor that validates EDI content, generates CDM JSON output, 
        and optionally creates TA1 acknowledgments. Single processor for all EDI processing needs."""
        tags = ['edi', 'validation', 'cdm', 'ta1', 'x12', 'healthcare']
        dependencies = ['pydantic>=2.0.0', 'typing-extensions>=4.0.0']
    
    # Relationships
    REL_SUCCESS = None
    REL_FAILURE = None
    
    def __init__(self, **kwargs):
        filtered_kwargs = {k: v for k, v in kwargs.items() if k not in ['jvm']}
        super().__init__(**filtered_kwargs)
        
        # Initialize relationships
        if self.REL_SUCCESS is None:
            self.REL_SUCCESS = Relationship(
                name="success",
                description="FlowFiles that are successfully processed (valid EDI)"
            )
        
        if self.REL_FAILURE is None:
            self.REL_FAILURE = Relationship(
                name="failure", 
                description="FlowFiles that fail validation or processing"
            )
        
        # Define property descriptors
        self.VALIDATION_SCHEMA = PropertyDescriptor(
            name="Validation Schema",
            description="EDI schema file to validate against (e.g., '837.5010.X222.A1.json')",
            required=True,
            default_value="${validation.schema}",
            expression_language_scope=ExpressionLanguageScope.FLOWFILE_ATTRIBUTES
        )
        
        self.SNIP_LEVEL = PropertyDescriptor(
            name="SNIP Level",
            description="Validation strictness level (1-5, where 5 is most strict)",
            required=True,
            default_value="3",
            allowable_values=["1", "2", "3", "4", "5"],
            expression_language_scope=ExpressionLanguageScope.FLOWFILE_ATTRIBUTES
        )
        
        self.TENANT_ID = PropertyDescriptor(
            name="Tenant ID",
            description="Tenant identifier for multi-tenant schema support",
            required=True,
            default_value="${tenant.id}",
            expression_language_scope=ExpressionLanguageScope.FLOWFILE_ATTRIBUTES
        )
        
        self.SCHEMA_BASE_PATH = PropertyDescriptor(
            name="Schema Base Path",
            description="Base directory containing EDI schema files",
            required=False,
            default_value="/opt/nifi/nifi-current/python_extensions/edi-processors/schemas"
        )
        
        self.GENERATE_CDM = PropertyDescriptor(
            name="Generate CDM",
            description="Generate CDM JSON output from EDI content",
            required=False,
            default_value="true",
            allowable_values=["true", "false"]
        )
        
        self.GENERATE_TA1 = PropertyDescriptor(
            name="Generate TA1",
            description="Generate TA1 acknowledgment when appropriate",
            required=False,
            default_value="false",
            allowable_values=["true", "false"]
        )
        
        self.FORCE_TA1 = PropertyDescriptor(
            name="Force TA1",
            description="Force TA1 generation even if not requested in ISA14",
            required=False,
            default_value="false",
            allowable_values=["true", "false"]
        )
        
        self.CDM_INCLUDE_METADATA = PropertyDescriptor(
            name="CDM Include Metadata",
            description="Include metadata in CDM JSON output",
            required=False,
            default_value="true",
            allowable_values=["true", "false"]
        )
        
        self.property_descriptors = [
            self.VALIDATION_SCHEMA,
            self.SNIP_LEVEL,
            self.TENANT_ID,
            self.SCHEMA_BASE_PATH,
            self.GENERATE_CDM,
            self.GENERATE_TA1,
            self.FORCE_TA1,
            self.CDM_INCLUDE_METADATA
        ]
        
        self.validation_service = None
        self.edi_parser = None
        self.ta1_generator = None
    
    def getPropertyDescriptors(self):
        return self.property_descriptors
    
    def getRelationships(self):
        return [self.REL_SUCCESS, self.REL_FAILURE]
    
    def onScheduled(self, context):
        """Initialize services when processor is scheduled."""
        try:
            schema_base_path = context.getProperty(self.SCHEMA_BASE_PATH).getValue()
            
            # Initialize services
            self.validation_service = EDIValidationService(schema_base_path)
            # Note: EdiParser will be initialized per-flowfile since it needs edi_string and schema
            self.ta1_generator = TA1Generator()
            
            logger.info(f"EDI Processor scheduled with schema path: {schema_base_path}")
        except Exception as e:
            logger.error(f"Failed to initialize EDI Processor: {e}")
            raise
    
    def transform(self, context, flowFile):
        """
        Transform the FlowFile by performing comprehensive EDI processing.
        
        Args:
            context: ProcessContext
            flowFile: FlowFile containing EDI content
            
        Returns:
            FlowFileTransformResult with comprehensive processing results
        """
        try:
            # Get processor properties
            schema_name = context.getProperty(self.VALIDATION_SCHEMA).evaluateAttributeExpressions(flowFile).getValue()
            snip_level = int(context.getProperty(self.SNIP_LEVEL).evaluateAttributeExpressions(flowFile).getValue())
            tenant_id = context.getProperty(self.TENANT_ID).evaluateAttributeExpressions(flowFile).getValue()
            
            generate_cdm = context.getProperty(self.GENERATE_CDM).getValue().lower() == "true"
            generate_ta1 = context.getProperty(self.GENERATE_TA1).getValue().lower() == "true"
            force_ta1 = context.getProperty(self.FORCE_TA1).getValue().lower() == "true"
            include_metadata = context.getProperty(self.CDM_INCLUDE_METADATA).getValue().lower() == "true"
            
            # Get EDI content from FlowFile
            edi_content = flowFile.getContentsAsBytes().decode('utf-8')
            
            logger.info(f"Processing EDI for tenant {tenant_id} with schema {schema_name}, SNIP level {snip_level}")
            logger.info(f"Options: CDM={generate_cdm}, TA1={generate_ta1}, Force TA1={force_ta1}")
            
            # Step 1: Validate EDI
            validation_result = self.validation_service.validate_edi(
                edi_content=edi_content,
                schema_name=schema_name,
                tenant_id=tenant_id,
                snip_level=snip_level
            )
            
            # Step 2: Generate CDM if requested
            cdm_data = None
            if generate_cdm:
                try:
                    # Get schema for parsing
                    schema = self.validation_service.schema_manager.get_schema(schema_name, tenant_id)
                    if not schema:
                        raise ValueError(f"Schema not found: {schema_name}")
                    
                    # Parse EDI content to get proper CDM structure
                    edi_parser = EdiParser(edi_content, schema)
                    parsed_interchange = edi_parser.parse()
                    
                    # Convert the parsed interchange to proper CDM JSON format
                    # This should use the CdmInterchange structure from cdm.py
                    cdm_data = self._convert_to_cdm_json(parsed_interchange, include_metadata)
                    
                    # Count total segments across all functional groups and transactions
                    total_segments = 2  # ISA + IEA
                    for fg in parsed_interchange.functional_groups:
                        total_segments += 2  # GS + GE
                        for transaction in fg.transactions:
                            total_segments += 2  # ST + SE
                            total_segments += len(transaction.body.segments)
                    
                    logger.info(f"Generated proper CDM structure with {total_segments} segments")
                except Exception as e:
                    logger.warning(f"CDM generation failed: {e}")
                    cdm_data = {"error": f"CDM generation failed: {str(e)}"}
            
            # Step 3: Generate TA1 if requested
            ta1_data = None
            if generate_ta1:
                try:
                    # Get schema for parsing
                    schema = self.validation_service.schema_manager.get_schema(schema_name, tenant_id)
                    if not schema:
                        raise ValueError(f"Schema not found: {schema_name}")
                    
                    # Parse to get ISA header for TA1 generation
                    edi_parser = EdiParser(edi_content, schema)
                    parsed_interchange = edi_parser.parse()
                    isa_segment = None
                    
                    # Get ISA segment from interchange header
                    isa_segment = parsed_interchange.header
                    
                    if isa_segment:
                        # Convert validation findings to interchange errors for TA1
                        interchange_errors = []
                        for finding in validation_result.findings:
                            if finding.level in ["ERROR", "FATAL"]:
                                # Convert to interchange error (simplified)
                                from ta1_defs import InterchangeError, TA1NoteCode
                                error = InterchangeError(
                                    code=finding.code,
                                    message=finding.message,
                                    note_code=TA1NoteCode.INVALID_INTERCHANGE_CONTROL_STRUCTURE
                                )
                                interchange_errors.append(error)
                        
                        ta1_content = self.ta1_generator.generate(
                            isa_header=isa_segment,
                            errors=interchange_errors,
                            force_generation=force_ta1
                        )
                        
                        ta1_data = {
                            "generated": ta1_content is not None,
                            "content": ta1_content,
                            "acknowledgment_code": "A" if validation_result.valid else "R",
                            "error_count": len(interchange_errors)
                        }
                        
                        logger.info(f"TA1 generation: {'successful' if ta1_content else 'not needed'}")
                    else:
                        logger.warning("No ISA segment found for TA1 generation")
                        ta1_data = {"generated": False, "error": "No ISA segment found"}
                        
                except Exception as e:
                    logger.warning(f"TA1 generation failed: {e}")
                    ta1_data = {"generated": False, "error": f"TA1 generation failed: {str(e)}"}
            
            # Step 4: Prepare comprehensive output
            result_attributes = {
                "edi.validation.valid": str(validation_result.valid).lower(),
                "edi.validation.findings.count": str(len(validation_result.findings)),
                "edi.validation.schema": schema_name,
                "edi.validation.snip.level": str(snip_level),
                "edi.validation.processed.at": datetime.now().isoformat(),
                "edi.validation.tenant.id": tenant_id,
                "edi.cdm.generated": str(generate_cdm and cdm_data is not None).lower(),
                "edi.ta1.generated": str(generate_ta1 and ta1_data and ta1_data.get("generated", False)).lower()
            }
            
            # Create comprehensive JSON output
            output_data = {
                "validation": {
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
            }
            
            # Add CDM data if generated
            if cdm_data:
                output_data["cdm"] = cdm_data
            
            # Add TA1 data if generated
            if ta1_data:
                output_data["ta1"] = ta1_data
            
            # Convert to JSON string
            json_output = json.dumps(output_data, indent=2)
            
            logger.info(f"EDI processing completed: valid={validation_result.valid}, "
                       f"findings={len(validation_result.findings)}, "
                       f"CDM={'generated' if cdm_data else 'skipped'}, "
                       f"TA1={'generated' if ta1_data and ta1_data.get('generated') else 'skipped'}")
            
            # Route based on validation result
            relationship = "success" if validation_result.valid else "failure"
            
            return FlowFileTransformResult(
                relationship=relationship,
                contents=json_output,
                attributes=result_attributes
            )
            
        except Exception as e:
            logger.error(f"EDI processing failed: {e}", exc_info=True)
            
            # Return error result
            error_attributes = {
                "edi.processing.error": str(e),
                "edi.processing.error.type": "PROCESSING_ERROR",
                "edi.processing.processed.at": datetime.now().isoformat()
            }
            
            error_data = {
                "validation": {
                    "valid": False,
                    "error": str(e),
                    "error_type": "PROCESSING_ERROR",
                    "processed_at": datetime.now().isoformat()
                }
            }
            
            return FlowFileTransformResult(
                relationship="failure",
                contents=json.dumps(error_data, indent=2),
                attributes=error_attributes
            )
    
    def _convert_to_cdm_json(self, parsed_interchange, include_metadata=True):
        """
        Convert parsed interchange to proper CDM JSON format using the CdmInterchange structure.
        
        This method converts the EdiParser output to the proper hierarchical CDM structure
        defined in cdm.py with CdmInterchange, CdmFunctionalGroup, CdmTransaction, etc.
        """
        try:
            # Convert the parsed interchange to proper CDM structure
            cdm_interchange = self._build_cdm_interchange(parsed_interchange)
            
            # Convert to JSON-serializable dictionary
            cdm_dict = cdm_interchange.model_dump()
            
            if include_metadata:
                cdm_dict["metadata"] = {
                    "segment_count": self._count_total_segments(cdm_interchange),
                    "interchange_control_number": cdm_interchange.header.get_element(13) if cdm_interchange.header else None,
                    "sender_id": cdm_interchange.header.get_element(6) if cdm_interchange.header else None,
                    "receiver_id": cdm_interchange.header.get_element(8) if cdm_interchange.header else None,
                    "functional_group_count": len(cdm_interchange.functional_groups),
                    "transaction_count": sum(len(fg.transactions) for fg in cdm_interchange.functional_groups),
                    "parsed_at": datetime.now().isoformat(),
                    "format": "CDM_HIERARCHICAL_V2"
                }
            
            return cdm_dict
            
        except Exception as e:
            logger.error(f"CDM conversion failed: {e}", exc_info=True)
            return {"error": f"CDM conversion failed: {str(e)}"}
    
    def _build_cdm_interchange(self, parsed_interchange):
        """
        Build a proper CdmInterchange from the parsed EDI data.
        The parsed_interchange is already a CdmInterchange, so we just return it.
        """
        # The parsed_interchange is already a proper CdmInterchange structure
        return parsed_interchange
    
    def _convert_segment_to_cdm_segment(self, segment):
        """
        Convert a parsed segment to a CdmSegment with proper CdmElement objects.
        """
        if not segment:
            return CdmSegment(segment_id="UNKNOWN", elements=[], line_number=0, raw_segment="")
        
        # Convert elements to CdmElement objects
        cdm_elements = []
        elements = getattr(segment, 'elements', [])
        for i, element_value in enumerate(elements):
            cdm_element = CdmElement(
                value=str(element_value) if element_value is not None else "",
                position=i + 1
            )
            cdm_elements.append(cdm_element)
        
        return CdmSegment(
            segment_id=getattr(segment, 'segment_id', 'UNKNOWN'),
            elements=cdm_elements,
            line_number=getattr(segment, 'line_number', 0),
            raw_segment=getattr(segment, 'raw_segment', getattr(segment, 'raw_content', ''))
        )
    
    def _count_total_segments(self, cdm_interchange):
        """
        Count total segments in the CDM interchange.
        """
        count = 2  # ISA + IEA
        for fg in cdm_interchange.functional_groups:
            count += 2  # GS + GE
            for transaction in fg.transactions:
                count += 2  # ST + SE
                count += len(transaction.body.segments)
                # Also count segments in nested loops
                def count_loop_segments(loop):
                    segment_count = len(loop.segments)
                    for loop_list in loop.loops.values():
                        for nested_loop in loop_list:
                            segment_count += count_loop_segments(nested_loop)
                    return segment_count
                
                count += count_loop_segments(transaction.body)
        return count