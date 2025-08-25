"""
EDI Parsing Processor for Apache NiFi

Native Python processor that parses EDI documents into structured formats
(JSON, XML, CSV) without requiring external API calls. Enables format-agnostic
downstream processing and data extraction.
"""

import json
import logging
import csv
import io
from datetime import datetime
from typing import Dict, Any, List
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom

# NiFi processor imports (these would be available in NiFi environment)
try:
    from nifiapi.flowfiletransform import FlowFileTransform, FlowFileTransformResult
    from nifiapi.properties import PropertyDescriptor, StandardValidators, ExpressionLanguageScope
    from nifiapi.relationship import Relationship
except ImportError:
    # Fallback for development/testing
    class FlowFileTransform:
        def __init__(self, **kwargs):
            # Accept any kwargs to be compatible with NiFi
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
            # Provide a dummy object ID for compatibility
            return f"rel_{self.name}_{id(self)}"

# Import our EDI common modules (using simple relative imports as per NiFi Python Dev Guide)
from edi_parser import EdiParser
from schema_manager import SchemaManager

logger = logging.getLogger(__name__)

class EDIParsingProcessor(FlowFileTransform):
    """
    NiFi processor for parsing EDI documents into structured formats.
    
    This processor replaces HTTP API calls to the backend parsing service with
    native EDI processing capabilities within NiFi. Supports multiple output formats
    for downstream processing flexibility.
    """
    
    class Java:
        implements = ['org.apache.nifi.python.processor.FlowFileTransform']
    
    class ProcessorDetails:
        version = '1.0.0'
        description = """Parses EDI content into structured formats (JSON, XML, CSV).
        Supports segment filtering, metadata extraction, and configurable output formats.
        Enables format-agnostic downstream processing."""
        tags = ['edi', 'parsing', 'x12', 'json', 'xml', 'csv']
        dependencies = ['pydantic>=2.0.0', 'typing-extensions>=4.0.0']
    
    # Processor properties
    OUTPUT_FORMAT = PropertyDescriptor(
        name="Output Format",
        description="Format for parsed EDI output",
        required=True,
        default_value="JSON",
        allowable_values=["JSON", "XML", "CSV"],
        expression_language_scope=ExpressionLanguageScope.FLOWFILE_ATTRIBUTES
    )
    
    INCLUDE_METADATA = PropertyDescriptor(
        name="Include Metadata",
        description="Include parsing metadata in output",
        required=False,
        default_value="true",
        allowable_values=["true", "false"]
    )
    
    SCHEMA_NAME = PropertyDescriptor(
        name="Schema Name",
        description="EDI schema for enhanced parsing (optional)",
        required=False,
        default_value="${edi.schema.name}",
        expression_language_scope=ExpressionLanguageScope.FLOWFILE_ATTRIBUTES
    )
    
    SEGMENT_FILTER = PropertyDescriptor(
        name="Segment Filter",
        description="Comma-separated list of segments to include (empty = all)",
        required=False,
        default_value="",
        expression_language_scope=ExpressionLanguageScope.FLOWFILE_ATTRIBUTES
    )
    
    TENANT_ID = PropertyDescriptor(
        name="Tenant ID",
        description="Tenant identifier for multi-tenant support",
        required=False,
        default_value="${tenant.id}",
        expression_language_scope=ExpressionLanguageScope.FLOWFILE_ATTRIBUTES
    )
    
    SCHEMA_BASE_PATH = PropertyDescriptor(
        name="Schema Base Path",
        description="Base directory containing EDI schema files",
        required=False,
        default_value="/opt/nifi/schemas"
    )
    
    # Relationships - Define as class variables to be initialized properly
    REL_SUCCESS = None
    REL_FAILURE = None
    
    def __init__(self, **kwargs):
        # Filter out NiFi-specific kwargs that FlowFileTransform doesn't accept
        filtered_kwargs = {k: v for k, v in kwargs.items() if k not in ['jvm']}
        super().__init__(**filtered_kwargs)
        
        # Initialize relationships - use our fallback class that has _get_object_id
        if self.REL_SUCCESS is None:
            self.REL_SUCCESS = Relationship(
                name="success",
                description="FlowFiles that are successfully parsed"
            )
        
        if self.REL_FAILURE is None:
            self.REL_FAILURE = Relationship(
                name="failure",
                description="FlowFiles that fail parsing"
            )
        
        self.schema_manager = None
    
    def getPropertyDescriptors(self):
        return [
            self.OUTPUT_FORMAT,
            self.INCLUDE_METADATA,
            self.SCHEMA_NAME,
            self.SEGMENT_FILTER,
            self.TENANT_ID,
            self.SCHEMA_BASE_PATH
        ]
    
    def getRelationships(self):
        return [self.REL_SUCCESS, self.REL_FAILURE]
    
    def onScheduled(self, context):
        """Initialize the schema manager when processor is scheduled."""
        try:
            schema_base_path = context.getProperty(self.SCHEMA_BASE_PATH).getValue()
            self.schema_manager = SchemaManager(schema_base_path)
            logger.info(f"EDI Parsing Processor scheduled with schema path: {schema_base_path}")
        except Exception as e:
            logger.error(f"Failed to initialize schema manager: {e}")
            raise
    
    def _format_as_json(self, interchange, include_metadata: bool, metadata: Dict[str, Any]) -> str:
        """Format parsed EDI as JSON."""
        
        segments = []
        
        # Add ISA header
        segments.append({
            "segment_id": interchange.header.segment_id,
            "elements": [element.value for element in interchange.header.elements],
            "line_number": interchange.header.line_number,
            "raw_content": interchange.header.raw_segment
        })
        
        # Process functional groups
        for group in interchange.functional_groups:
            # Add GS header
            segments.append({
                "segment_id": group.header.segment_id,
                "elements": [element.value for element in group.header.elements],
                "line_number": group.header.line_number,
                "raw_content": group.header.raw_segment
            })
            
            # Process transactions
            for transaction in group.transactions:
                # Add ST header
                segments.append({
                    "segment_id": transaction.header.segment_id,
                    "elements": [element.value for element in transaction.header.elements],
                    "line_number": transaction.header.line_number,
                    "raw_content": transaction.header.raw_segment
                })
                
                # Add body segments
                for segment in transaction.body.segments:
                    segments.append({
                        "segment_id": segment.segment_id,
                        "elements": [element.value for element in segment.elements],
                        "line_number": segment.line_number,
                        "raw_content": segment.raw_segment
                    })
                
                # Add SE trailer
                segments.append({
                    "segment_id": transaction.trailer.segment_id,
                    "elements": [element.value for element in transaction.trailer.elements],
                    "line_number": transaction.trailer.line_number,
                    "raw_content": transaction.trailer.raw_segment
                })
            
            # Add GE trailer
            segments.append({
                "segment_id": group.trailer.segment_id,
                "elements": [element.value for element in group.trailer.elements],
                "line_number": group.trailer.line_number,
                "raw_content": group.trailer.raw_segment
            })
        
        # Add IEA trailer
        segments.append({
            "segment_id": interchange.trailer.segment_id,
            "elements": [element.value for element in interchange.trailer.elements],
            "line_number": interchange.trailer.line_number,
            "raw_content": interchange.trailer.raw_segment
        })
        
        result = {"segments": segments}
        
        if include_metadata:
            result["metadata"] = metadata
        
        return json.dumps(result, indent=2)
    
    def _format_as_xml(self, interchange, include_metadata: bool, metadata: Dict[str, Any]) -> str:
        """Format parsed EDI as XML."""
        
        root = Element("edi_document")
        
        if include_metadata:
            metadata_elem = SubElement(root, "metadata")
            for key, value in metadata.items():
                elem = SubElement(metadata_elem, key)
                elem.text = str(value)
        
        segments_elem = SubElement(root, "segments")
        
        # Add ISA header
        self._add_segment_to_xml(segments_elem, interchange.header)
        
        # Process functional groups
        for group in interchange.functional_groups:
            # Add GS header
            self._add_segment_to_xml(segments_elem, group.header)
            
            # Process transactions
            for transaction in group.transactions:
                # Add ST header
                self._add_segment_to_xml(segments_elem, transaction.header)
                
                # Add body segments
                for segment in transaction.body.segments:
                    self._add_segment_to_xml(segments_elem, segment)
                
                # Add SE trailer
                self._add_segment_to_xml(segments_elem, transaction.trailer)
            
            # Add GE trailer
            self._add_segment_to_xml(segments_elem, group.trailer)
        
        # Add IEA trailer
        self._add_segment_to_xml(segments_elem, interchange.trailer)
        
        # Pretty print XML
        rough_string = tostring(root, 'unicode')
        reparsed = minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent="  ")
    
    def _add_segment_to_xml(self, parent, segment):
        """Add a segment to XML structure."""
        segment_elem = SubElement(parent, "segment")
        segment_elem.set("id", segment.segment_id)
        segment_elem.set("line", str(segment.line_number))
        
        for i, element in enumerate(segment.elements):
            element_elem = SubElement(segment_elem, "element")
            element_elem.set("position", str(i + 1))
            element_elem.text = element.value
    
    def _format_as_csv(self, interchange, include_metadata: bool, metadata: Dict[str, Any]) -> str:
        """Format parsed EDI as CSV."""
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header row
        headers = ["segment_id", "line_number", "element_1", "element_2", "element_3", 
                  "element_4", "element_5", "element_6", "element_7", "element_8",
                  "element_9", "element_10", "element_11", "element_12", "element_13",
                  "element_14", "element_15", "element_16", "raw_content"]
        writer.writerow(headers)
        
        # Helper function to write segment as CSV row
        def write_segment(segment):
            elements = [element.value for element in segment.elements]
            # Pad or truncate to 16 elements
            while len(elements) < 16:
                elements.append("")
            elements = elements[:16]
            
            row = [segment.segment_id, segment.line_number] + elements + [segment.raw_segment]
            writer.writerow(row)
        
        # Write ISA header
        write_segment(interchange.header)
        
        # Process functional groups
        for group in interchange.functional_groups:
            write_segment(group.header)
            
            for transaction in group.transactions:
                write_segment(transaction.header)
                
                for segment in transaction.body.segments:
                    write_segment(segment)
                
                write_segment(transaction.trailer)
            
            write_segment(group.trailer)
        
        # Write IEA trailer
        write_segment(interchange.trailer)
        
        # Add metadata as comments if requested
        if include_metadata:
            output.write(f"\n# Metadata:\n")
            for key, value in metadata.items():
                output.write(f"# {key}: {value}\n")
        
        return output.getvalue()
    
    def _apply_segment_filter(self, segments: List, segment_filter: str) -> List:
        """Filter segments based on segment filter list."""
        if not segment_filter.strip():
            return segments
        
        allowed_segments = [s.strip().upper() for s in segment_filter.split(',')]
        return [seg for seg in segments if seg.get('segment_id', '').upper() in allowed_segments]
    
    def _extract_metadata(self, interchange, parsed_at: str, tenant_id: str) -> Dict[str, Any]:
        """Extract metadata from parsed interchange."""
        
        metadata = {
            "parsed_at": parsed_at,
            "segment_count": 0,
            "has_errors": False,
            "tenant_id": tenant_id
        }
        
        # Count all segments
        segment_count = 2  # ISA + IEA
        
        for group in interchange.functional_groups:
            segment_count += 2  # GS + GE
            
            for transaction in group.transactions:
                segment_count += 2  # ST + SE
                segment_count += len(transaction.body.segments)
        
        metadata["segment_count"] = segment_count
        
        # Extract interchange info
        if interchange.header and len(interchange.header.elements) >= 13:
            metadata["interchange_control_number"] = interchange.header.get_element(13)
            metadata["sender_id"] = interchange.header.get_element(6)
            metadata["receiver_id"] = interchange.header.get_element(8)
        
        # Extract transaction set info
        transaction_sets = []
        for group in interchange.functional_groups:
            for transaction in group.transactions:
                if transaction.header and len(transaction.header.elements) >= 2:
                    tx_info = {
                        "transaction_set_identifier": transaction.header.get_element(1),
                        "control_number": transaction.header.get_element(2),
                        "segment_count": len(transaction.body.segments) + 2  # +2 for ST/SE
                    }
                    transaction_sets.append(tx_info)
        
        metadata["transaction_sets"] = transaction_sets
        
        return metadata
    
    def transform(self, context, flowFile):
        """
        Transform the FlowFile by parsing its EDI content.
        
        Args:
            context: ProcessContext
            flowFile: FlowFile containing EDI content
            
        Returns:
            FlowFileTransformResult with parsed content
        """
        try:
            # Get processor properties
            output_format = context.getProperty(self.OUTPUT_FORMAT).evaluateAttributeExpressions(flowFile).getValue()
            include_metadata = context.getProperty(self.INCLUDE_METADATA).getValue().lower() == "true"
            schema_name = context.getProperty(self.SCHEMA_NAME).evaluateAttributeExpressions(flowFile).getValue()
            segment_filter = context.getProperty(self.SEGMENT_FILTER).evaluateAttributeExpressions(flowFile).getValue()
            tenant_id = context.getProperty(self.TENANT_ID).evaluateAttributeExpressions(flowFile).getValue()
            
            # Get EDI content from FlowFile
            edi_content = flowFile.getContentsAsBytes().decode('utf-8')
            
            logger.info(f"Parsing EDI for tenant {tenant_id}, format: {output_format}, schema: {schema_name}")
            
            # Load schema if specified
            schema = None
            if schema_name and schema_name.strip():
                schema = self.schema_manager.get_schema(schema_name, tenant_id or "default")
                if not schema:
                    logger.warning(f"Schema not found: {schema_name}, proceeding without schema")
            
            # Parse EDI content
            parser = EdiParser(edi_content, schema)
            interchange = parser.parse()
            
            # Extract metadata
            parsed_at = datetime.now().isoformat()
            metadata = self._extract_metadata(interchange, parsed_at, tenant_id)
            
            # Check for parsing errors
            all_errors = parser._collect_all_errors(interchange)
            metadata["has_errors"] = len(all_errors) > 0
            metadata["error_count"] = len(all_errors)
            
            # Format output based on requested format
            if output_format.upper() == "JSON":
                formatted_output = self._format_as_json(interchange, include_metadata, metadata)
            elif output_format.upper() == "XML":
                formatted_output = self._format_as_xml(interchange, include_metadata, metadata)
            elif output_format.upper() == "CSV":
                formatted_output = self._format_as_csv(interchange, include_metadata, metadata)
            else:
                raise ValueError(f"Unsupported output format: {output_format}")
            
            # Prepare result attributes
            result_attributes = {
                "edi.parsing.format": output_format.upper(),
                "edi.parsing.segments.count": str(metadata["segment_count"]),
                "edi.parsing.processed.at": parsed_at,
                "edi.parsing.has.errors": str(metadata["has_errors"]).lower(),
                "edi.parsing.error.count": str(metadata["error_count"])
            }
            
            if schema_name and schema_name.strip():
                result_attributes["edi.parsing.schema"] = schema_name
            
            if metadata.get("interchange_control_number"):
                result_attributes["edi.parsing.interchange.control.number"] = metadata["interchange_control_number"]
            
            if metadata.get("sender_id"):
                result_attributes["edi.parsing.sender.id"] = metadata["sender_id"]
            
            if metadata.get("receiver_id"):
                result_attributes["edi.parsing.receiver.id"] = metadata["receiver_id"]
            
            if tenant_id:
                result_attributes["edi.parsing.tenant.id"] = tenant_id
            
            logger.info(f"Parsing completed: format={output_format}, segments={metadata['segment_count']}, errors={metadata['error_count']}")
            
            return FlowFileTransformResult(
                relationship=self.REL_SUCCESS,
                contents=formatted_output,
                attributes=result_attributes
            )
            
        except Exception as e:
            logger.error(f"EDI parsing processing failed: {e}", exc_info=True)
            
            # Return error result
            error_attributes = {
                "edi.parsing.error": str(e),
                "edi.parsing.error.type": "PARSING_ERROR",
                "edi.parsing.processed.at": datetime.now().isoformat()
            }
            
            error_data = {
                "parsing_successful": False,
                "error": str(e),
                "error_type": "PARSING_ERROR",
                "processed_at": datetime.now().isoformat()
            }
            
            return FlowFileTransformResult(
                relationship=self.REL_FAILURE,
                contents=json.dumps(error_data, indent=2),
                attributes=error_attributes
            )