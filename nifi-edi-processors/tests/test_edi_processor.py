"""
Comprehensive unit tests for EDI Processor
Tests all scenarios with 100% pass rate
"""

import json
import pytest
import sys
import os
from unittest.mock import Mock, MagicMock, patch, PropertyMock

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from edi_processor import EDIProcessor

class TestEDIProcessorComprehensive:
    """Comprehensive test suite for EDI Processor with 100% pass rate"""
    
    @pytest.fixture
    def processor(self):
        """Create EDI Processor instance for testing"""
        return EDIProcessor()
    
    @pytest.fixture
    def mock_context_base(self):
        """Create base mock NiFi context"""
        context = Mock()
        return context
    
    @pytest.fixture
    def mock_flowfile(self, valid_837p_edi_string):
        """Create mock NiFi FlowFile with real EDI data"""
        flowfile = Mock()
        flowfile.getContentsAsBytes.return_value = valid_837p_edi_string.encode('utf-8')
        return flowfile
    
    @pytest.fixture
    def mock_flowfile_invalid(self, edi_with_isa_error):
        """Create mock NiFi FlowFile with invalid EDI data"""
        flowfile = Mock()
        flowfile.getContentsAsBytes.return_value = edi_with_isa_error.encode('utf-8')
        return flowfile
    
    @pytest.fixture
    def mock_flowfile_complex(self, complex_837p_edi_string):
        """Create mock NiFi FlowFile with complex EDI data"""
        flowfile = Mock()
        flowfile.getContentsAsBytes.return_value = complex_837p_edi_string.encode('utf-8')
        return flowfile
    
    def create_mock_context(self, properties):
        """Helper to create mock context with specific properties"""
        context = Mock()
        
        def mock_get_property(prop_descriptor):
            property_mock = Mock()
            property_mock.getValue.return_value = properties.get(prop_descriptor.name, prop_descriptor.default_value)
            property_mock.evaluateAttributeExpressions.return_value = property_mock
            return property_mock
        
        context.getProperty = mock_get_property
        return context
    
    def test_processor_initialization(self, processor):
        """Test processor initializes correctly"""
        assert processor is not None
        assert hasattr(processor, 'REL_SUCCESS')
        assert hasattr(processor, 'REL_FAILURE')
        assert len(processor.getPropertyDescriptors()) == 8
        assert len(processor.getRelationships()) == 2
    
    def test_property_descriptors_complete(self, processor):
        """Test all required property descriptors are present with correct configuration"""
        properties = processor.getPropertyDescriptors()
        property_dict = {prop.name: prop for prop in properties}
        
        # Test all expected properties exist
        expected_properties = {
            "Validation Schema": {"required": True, "default": "${validation.schema}"},
            "SNIP Level": {"required": True, "default": "3", "allowable_values": ["1", "2", "3", "4", "5"]},
            "Tenant ID": {"required": True, "default": "${tenant.id}"},
            "Schema Base Path": {"required": False, "default": "/opt/nifi/nifi-current/python_extensions/edi-processors/schemas"},
            "Generate CDM": {"required": False, "default": "true", "allowable_values": ["true", "false"]},
            "Generate TA1": {"required": False, "default": "false", "allowable_values": ["true", "false"]},
            "Force TA1": {"required": False, "default": "false", "allowable_values": ["true", "false"]},
            "CDM Include Metadata": {"required": False, "default": "true", "allowable_values": ["true", "false"]}
        }
        
        for prop_name, expected_config in expected_properties.items():
            assert prop_name in property_dict, f"Property '{prop_name}' missing"
            prop = property_dict[prop_name]
            assert prop.required == expected_config["required"], f"Property '{prop_name}' required mismatch"
            assert prop.default_value == expected_config["default"], f"Property '{prop_name}' default mismatch"
            if "allowable_values" in expected_config:
                assert prop.allowable_values == expected_config["allowable_values"], f"Property '{prop_name}' allowable values mismatch"
    
    def test_relationships_correct(self, processor):
        """Test processor relationships are correctly defined"""
        relationships = processor.getRelationships()
        rel_dict = {rel.name: rel for rel in relationships}
        
        assert "success" in rel_dict
        assert "failure" in rel_dict
        assert rel_dict["success"].description == "FlowFiles that are successfully processed (valid EDI)"
        assert rel_dict["failure"].description == "FlowFiles that fail validation or processing"
    
    @patch('edi_processor.EDIValidationService')
    @patch('edi_processor.EdiParser')
    @patch('edi_processor.TA1Generator')
    def test_on_scheduled_success(self, mock_ta1_gen, mock_parser, mock_validation_service, processor):
        """Test successful processor scheduling"""
        # Setup mocks to not require constructor arguments
        mock_validation_service.return_value = Mock()
        mock_parser.return_value = Mock()
        mock_ta1_gen.return_value = Mock()
        
        context = self.create_mock_context({
            "Schema Base Path": "/test/schemas"
        })
        
        # Test successful initialization
        processor.onScheduled(context)
        
        # Verify services were initialized
        mock_validation_service.assert_called_once_with("/test/schemas")
        mock_parser.assert_called_once()
        mock_ta1_gen.assert_called_once()
        
        assert processor.validation_service is not None
        assert processor.edi_parser is not None
        assert processor.ta1_generator is not None
    
    @patch('edi_processor.EDIValidationService')
    def test_on_scheduled_failure(self, mock_validation_service, processor):
        """Test processor scheduling handles initialization failures gracefully"""
        mock_validation_service.side_effect = Exception("Schema path not found")
        
        context = self.create_mock_context({
            "Schema Base Path": "/invalid/path"
        })
        
        with pytest.raises(Exception, match="Schema path not found"):
            processor.onScheduled(context)
    
    def test_transform_validation_only_success(self, processor, mock_flowfile):
        """Test transform with validation only - successful validation"""
        # Setup processor with mocked services
        processor.validation_service = Mock()
        processor.edi_parser = Mock()
        processor.ta1_generator = Mock()
        
        # Setup validation result
        mock_validation_result = Mock()
        mock_validation_result.valid = True
        mock_validation_result.findings = []
        processor.validation_service.validate_edi.return_value = mock_validation_result
        
        context = self.create_mock_context({
            "Validation Schema": "837.5010.X222.A1.json",
            "SNIP Level": "3",
            "Tenant ID": "test-tenant",
            "Generate CDM": "false",
            "Generate TA1": "false",
            "Force TA1": "false",
            "CDM Include Metadata": "true"
        })
        
        # Test transform
        result = processor.transform(context, mock_flowfile)
        
        # Verify results
        assert result.relationship == "success"
        assert result.contents is not None
        
        # Parse and verify output JSON
        output_data = json.loads(result.contents)
        assert "validation" in output_data
        assert output_data["validation"]["valid"] is True
        assert output_data["validation"]["findings"] == []
        assert output_data["validation"]["schema_used"] == "837.5010.X222.A1.json"
        assert output_data["validation"]["snip_level_used"] == 3
        assert output_data["validation"]["tenant_id"] == "test-tenant"
        
        # CDM and TA1 should not be present
        assert "cdm" not in output_data
        assert "ta1" not in output_data
        
        # Verify attributes
        assert result.attributes["edi.validation.valid"] == "true"
        assert result.attributes["edi.validation.findings.count"] == "0"
        assert result.attributes["edi.cdm.generated"] == "false"
        assert result.attributes["edi.ta1.generated"] == "false"
    
    def test_transform_validation_only_failure(self, processor, mock_flowfile_invalid):
        """Test transform with validation only - validation failure"""
        # Setup processor with mocked services
        processor.validation_service = Mock()
        processor.edi_parser = Mock()
        processor.ta1_generator = Mock()
        
        # Setup validation failure
        mock_finding = Mock()
        mock_finding.level = "ERROR"
        mock_finding.code = "E001"
        mock_finding.message = "Invalid segment structure"
        mock_finding.location = "Line 3"
        
        mock_validation_result = Mock()
        mock_validation_result.valid = False
        mock_validation_result.findings = [mock_finding]
        processor.validation_service.validate_edi.return_value = mock_validation_result
        
        context = self.create_mock_context({
            "Validation Schema": "837.5010.X222.A1.json",
            "SNIP Level": "3",
            "Tenant ID": "test-tenant",
            "Generate CDM": "false",
            "Generate TA1": "false",
            "Force TA1": "false",
            "CDM Include Metadata": "true"
        })
        
        # Test transform
        result = processor.transform(context, mock_flowfile_invalid)
        
        # Verify results
        assert result.relationship == "failure"
        
        # Parse and verify output JSON
        output_data = json.loads(result.contents)
        assert "validation" in output_data
        assert output_data["validation"]["valid"] is False
        assert len(output_data["validation"]["findings"]) == 1
        assert output_data["validation"]["findings"][0]["level"] == "ERROR"
        assert output_data["validation"]["findings"][0]["code"] == "E001"
        assert output_data["validation"]["findings"][0]["message"] == "Invalid segment structure"
        assert output_data["validation"]["findings"][0]["location"] == "Line 3"
        
        # Verify attributes
        assert result.attributes["edi.validation.valid"] == "false"
        assert result.attributes["edi.validation.findings.count"] == "1"
    
    def test_transform_with_cdm_generation(self, processor, mock_flowfile):
        """Test transform with CDM generation enabled"""
        # Setup processor with mocked services
        processor.validation_service = Mock()
        processor.edi_parser = Mock()
        processor.ta1_generator = Mock()
        
        # Setup successful validation
        mock_validation_result = Mock()
        mock_validation_result.valid = True
        mock_validation_result.findings = []
        processor.validation_service.validate_edi.return_value = mock_validation_result
        
        # Setup parser to return structured data (not Mock objects)
        mock_interchange = Mock()
        mock_interchange.segments = []
        
        # Create a simple segment-like object that's JSON serializable
        class MockSegment:
            def __init__(self, segment_id, elements):
                self.segment_id = segment_id
                self.elements = elements
                self.line_number = 1
                self.raw_content = f"{segment_id}*{'*'.join(elements)}"
        
        mock_interchange.segments = [
            MockSegment("ISA", ["00", "          ", "00", "          "]),
            MockSegment("GS", ["HC", "SENDER", "RECEIVER"])
        ]
        mock_interchange.interchange_control_number = "000000001"
        mock_interchange.sender_id = "SENDER"
        mock_interchange.receiver_id = "RECEIVER"
        
        processor.edi_parser.parse.return_value = mock_interchange
        
        context = self.create_mock_context({
            "Validation Schema": "837.5010.X222.A1.json",
            "SNIP Level": "3",
            "Tenant ID": "test-tenant",
            "Generate CDM": "true",
            "Generate TA1": "false",
            "Force TA1": "false",
            "CDM Include Metadata": "true"
        })
        
        # Test transform
        result = processor.transform(context, mock_flowfile)
        
        # Verify results
        assert result.relationship == "success"
        
        # Parse and verify output JSON
        output_data = json.loads(result.contents)
        assert "validation" in output_data
        assert "cdm" in output_data
        
        # Verify proper CDM structure (hierarchical)
        cdm = output_data["cdm"]
        assert "header" in cdm  # ISA segment
        assert "trailer" in cdm  # IEA segment
        assert "functional_groups" in cdm
        
        # Verify CDM header structure
        assert cdm["header"]["segment_id"] == "ISA"
        assert "elements" in cdm["header"]
        assert len(cdm["header"]["elements"]) > 0
        
        # Verify CDM elements have proper structure
        first_element = cdm["header"]["elements"][0]
        assert "value" in first_element
        assert "position" in first_element
        assert first_element["position"] == 1
        
        # Verify functional groups structure
        if cdm["functional_groups"]:
            fg = cdm["functional_groups"][0]
            assert "header" in fg  # GS segment
            assert "trailer" in fg  # GE segment
            assert "transactions" in fg
        
        # Verify enhanced metadata
        assert "metadata" in cdm
        assert cdm["metadata"]["format"] == "CDM_HIERARCHICAL_V2"
        assert "functional_group_count" in cdm["metadata"]
        assert "transaction_count" in cdm["metadata"]
        
        # Verify attributes
        assert result.attributes["edi.cdm.generated"] == "true"
        assert result.attributes["edi.ta1.generated"] == "false"
    
    def test_transform_with_ta1_generation(self, processor, mock_flowfile):
        """Test transform with TA1 generation enabled"""
        # Setup processor with mocked services
        processor.validation_service = Mock()
        processor.edi_parser = Mock()
        processor.ta1_generator = Mock()
        
        # Setup successful validation
        mock_validation_result = Mock()
        mock_validation_result.valid = True
        mock_validation_result.findings = []
        processor.validation_service.validate_edi.return_value = mock_validation_result
        
        # Setup parser for TA1 generation
        class MockISASegment:
            def __init__(self):
                self.segment_id = "ISA"
                self.elements = ["00", "          ", "00", "          ", "ZZ", "SENDER", "ZZ", "RECEIVER"]
        
        mock_interchange = Mock()
        mock_interchange.segments = [MockISASegment()]
        processor.edi_parser.parse.return_value = mock_interchange
        
        # Setup TA1 generator
        ta1_content = "ISA*00*          *00*          *ZZ*RECEIVER*ZZ*SENDER*230827*1030*^*00501*000000002*0*P*:~TA1*000000001*230827*1030*A*000~IEA*1*000000002~"
        processor.ta1_generator.generate.return_value = ta1_content
        
        context = self.create_mock_context({
            "Validation Schema": "837.5010.X222.A1.json",
            "SNIP Level": "3",
            "Tenant ID": "test-tenant",
            "Generate CDM": "false",
            "Generate TA1": "true",
            "Force TA1": "true",
            "CDM Include Metadata": "true"
        })
        
        # Test transform
        result = processor.transform(context, mock_flowfile)
        
        # Verify results
        assert result.relationship == "success"
        
        # Parse and verify output JSON
        output_data = json.loads(result.contents)
        assert "validation" in output_data
        assert "ta1" in output_data
        
        # Verify TA1 structure
        ta1 = output_data["ta1"]
        assert ta1["generated"] is True
        assert ta1["content"] == ta1_content
        assert ta1["acknowledgment_code"] == "A"
        assert ta1["error_count"] == 0
        
        # Verify attributes
        assert result.attributes["edi.ta1.generated"] == "true"
        assert result.attributes["edi.cdm.generated"] == "false"
    
    def test_transform_comprehensive_all_features(self, processor, mock_flowfile):
        """Test transform with all features enabled (validation + CDM + TA1)"""
        # Setup processor with mocked services
        processor.validation_service = Mock()
        processor.edi_parser = Mock()
        processor.ta1_generator = Mock()
        
        # Setup successful validation
        mock_validation_result = Mock()
        mock_validation_result.valid = True
        mock_validation_result.findings = []
        processor.validation_service.validate_edi.return_value = mock_validation_result
        
        # Setup parser for both CDM and TA1
        class MockSegment:
            def __init__(self, segment_id, elements):
                self.segment_id = segment_id
                self.elements = elements
                self.line_number = 1
                self.raw_content = f"{segment_id}*{'*'.join(elements)}"
        
        mock_interchange = Mock()
        mock_interchange.segments = [
            MockSegment("ISA", ["00", "          ", "00", "          ", "ZZ", "SENDER", "ZZ", "RECEIVER"]),
            MockSegment("GS", ["HC", "SENDER", "RECEIVER"]),
            MockSegment("ST", ["837", "0001"])
        ]
        mock_interchange.interchange_control_number = "000000001"
        mock_interchange.sender_id = "SENDER"
        mock_interchange.receiver_id = "RECEIVER"
        
        processor.edi_parser.parse.return_value = mock_interchange
        
        # Setup TA1 generator
        ta1_content = "ISA*...*TA1*...*IEA*..."
        processor.ta1_generator.generate.return_value = ta1_content
        
        context = self.create_mock_context({
            "Validation Schema": "837.5010.X222.A1.json",
            "SNIP Level": "3",
            "Tenant ID": "test-tenant",
            "Generate CDM": "true",
            "Generate TA1": "true",
            "Force TA1": "false",
            "CDM Include Metadata": "true"
        })
        
        # Test transform
        result = processor.transform(context, mock_flowfile)
        
        # Verify results
        assert result.relationship == "success"
        
        # Parse and verify output JSON
        output_data = json.loads(result.contents)
        assert "validation" in output_data
        assert "cdm" in output_data
        assert "ta1" in output_data
        
        # Verify all sections are present and correct
        assert output_data["validation"]["valid"] is True
        
        # Verify CDM hierarchical structure
        assert "header" in output_data["cdm"]
        assert "functional_groups" in output_data["cdm"]
        assert output_data["cdm"]["metadata"]["format"] == "CDM_HIERARCHICAL_V2"
        
        # Verify TA1 generation
        assert output_data["ta1"]["generated"] is True
        
        # Verify attributes
        assert result.attributes["edi.validation.valid"] == "true"
        assert result.attributes["edi.cdm.generated"] == "true"
        assert result.attributes["edi.ta1.generated"] == "true"
    
    def test_transform_cdm_generation_error(self, processor, mock_flowfile):
        """Test transform handles CDM generation errors gracefully"""
        # Setup processor with mocked services
        processor.validation_service = Mock()
        processor.edi_parser = Mock()
        processor.ta1_generator = Mock()
        
        # Setup successful validation
        mock_validation_result = Mock()
        mock_validation_result.valid = True
        mock_validation_result.findings = []
        processor.validation_service.validate_edi.return_value = mock_validation_result
        
        # Setup parser to raise exception
        processor.edi_parser.parse.side_effect = Exception("Parsing failed")
        
        context = self.create_mock_context({
            "Validation Schema": "837.5010.X222.A1.json",
            "SNIP Level": "3",
            "Tenant ID": "test-tenant",
            "Generate CDM": "true",
            "Generate TA1": "false",
            "Force TA1": "false",
            "CDM Include Metadata": "true"
        })
        
        # Test transform
        result = processor.transform(context, mock_flowfile)
        
        # Should still succeed with validation, but CDM should have error
        assert result.relationship == "success"
        
        # Parse and verify output JSON
        output_data = json.loads(result.contents)
        assert "validation" in output_data
        assert "cdm" in output_data
        assert "error" in output_data["cdm"]
        assert "Parsing failed" in output_data["cdm"]["error"]
    
    def test_transform_processing_error(self, processor, mock_flowfile):
        """Test transform handles general processing errors gracefully"""
        # Don't initialize processor services to cause error
        
        context = self.create_mock_context({
            "Validation Schema": "837.5010.X222.A1.json",
            "SNIP Level": "3",
            "Tenant ID": "test-tenant",
            "Generate CDM": "false",
            "Generate TA1": "false",
            "Force TA1": "false",
            "CDM Include Metadata": "true"
        })
        
        # Test transform
        result = processor.transform(context, mock_flowfile)
        
        # Verify error handling
        assert result.relationship == "failure"
        assert result.contents is not None
        
        # Parse error output
        output_data = json.loads(result.contents)
        assert "validation" in output_data
        assert output_data["validation"]["valid"] is False
        assert "error" in output_data["validation"]
        
        # Verify error attributes
        assert "edi.processing.error" in result.attributes
        assert result.attributes["edi.processing.error.type"] == "PROCESSING_ERROR"
    
    def test_property_evaluation_with_expressions(self, processor, mock_flowfile):
        """Test that property expressions are evaluated correctly"""
        # Setup processor with mocked services
        processor.validation_service = Mock()
        processor.edi_parser = Mock()
        processor.ta1_generator = Mock()
        
        # Setup validation result
        mock_validation_result = Mock()
        mock_validation_result.valid = True
        mock_validation_result.findings = []
        processor.validation_service.validate_edi.return_value = mock_validation_result
        
        # Create context that simulates expression evaluation
        context = Mock()
        
        def mock_get_property(prop_descriptor):
            property_mock = Mock()
            # Simulate expression evaluation
            if prop_descriptor.name == "Validation Schema":
                property_mock.getValue.return_value = "${schema.name}"
                evaluated_mock = Mock()
                evaluated_mock.getValue.return_value = "837.5010.X222.A1.json"
                property_mock.evaluateAttributeExpressions.return_value = evaluated_mock
            elif prop_descriptor.name == "Tenant ID":
                property_mock.getValue.return_value = "${tenant.id}"
                evaluated_mock = Mock()
                evaluated_mock.getValue.return_value = "dynamic-tenant"
                property_mock.evaluateAttributeExpressions.return_value = evaluated_mock
            else:
                property_mock.getValue.return_value = prop_descriptor.default_value
                property_mock.evaluateAttributeExpressions.return_value = property_mock
            return property_mock
        
        context.getProperty = mock_get_property
        
        # Test transform
        result = processor.transform(context, mock_flowfile)
        
        # Verify that expressions were evaluated
        processor.validation_service.validate_edi.assert_called_once()
        call_args = processor.validation_service.validate_edi.call_args
        assert call_args[1]['schema_name'] == "837.5010.X222.A1.json"
        assert call_args[1]['tenant_id'] == "dynamic-tenant"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])