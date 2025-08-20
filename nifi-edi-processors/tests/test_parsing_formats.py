"""
Format validation tests for the EDI Parsing Processor.
Tests JSON, XML, and CSV output formats for correctness and compliance.
"""

import pytest
import sys
import os
import json
import csv
import io
from xml.etree import ElementTree as ET

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from edi_common.edi_parser import EdiParser
from processors.edi_parsing_processor import EDIParsingProcessor

@pytest.fixture
def parsing_formats_fixtures(standalone_schema):
    processor = EDIParsingProcessor()
    sample_edi = """ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *210101*1000*^*00501*000000001*1*P*>~GS*HC*SENDER*RECEIVER*20210101*1000*1*X*005010~ST*270*0001~BHT*0022*13*10001234*20210101*1000~HL*1**20*1~NM1*PR*2*ABC INSURANCE*****PI*12345~SE*6*0001~GE*1*1~IEA*1*000000001~"""
    parser = EdiParser(sample_edi, standalone_schema)
    interchange = parser.parse()
    metadata = {
        "parsed_at": "2024-01-15T10:30:00Z",
        "segment_count": 9,
        "has_errors": False,
        "interchange_control_number": "000000001",
        "sender_id": "SENDER         ",
        "receiver_id": "RECEIVER       ",
        "transaction_sets": [
            {
                "transaction_set_identifier": "270",
                "control_number": "0001",
                "segment_count": 8
            }
        ]
    }
    return processor, interchange, metadata

class TestParsingFormats:
    """Test cases for multi-format EDI parsing output."""
    
    def test_json_output_format(self, parsing_formats_fixtures):
        """Test JSON output format compliance."""
        processor, interchange, metadata = parsing_formats_fixtures
        
        # Generate JSON output
        json_output = processor._format_as_json(
            interchange,
            include_metadata=True, 
            metadata=metadata
        )
        
        # Parse JSON to validate structure
        parsed_result = json.loads(json_output)
        
        # Validate top-level structure
        assert "segments" in parsed_result
        assert "metadata" in parsed_result
        assert isinstance(parsed_result["segments"], list)
        assert isinstance(parsed_result["metadata"], dict)
        
        # Validate segment structure
        segments = parsed_result["segments"]
        assert len(segments) > 0
        
        first_segment = segments[0]
        assert "segment_id" in first_segment
        assert "elements" in first_segment
        assert "line_number" in first_segment
        assert "raw_content" in first_segment
        
        # Validate segment content
        assert first_segment["segment_id"] == "ISA"
        assert isinstance(first_segment["elements"], list)
        assert isinstance(first_segment["line_number"], int)
        assert isinstance(first_segment["raw_content"], str)
        
        # Validate metadata structure
        metadata = parsed_result["metadata"]
        required_metadata_fields = [
            "parsed_at", "segment_count", "has_errors", 
            "interchange_control_number", "sender_id", "receiver_id"
        ]
        
        for field in required_metadata_fields:
            assert field in metadata
        
        assert metadata["segment_count"] == 9
        assert metadata["has_errors"] == False
        assert metadata["interchange_control_number"] == "000000001"
        
        print("✅ JSON format validation passed")
    
    def test_xml_output_format(self, parsing_formats_fixtures):
        """Test XML output format compliance."""
        processor, interchange, metadata = parsing_formats_fixtures
        
        # Generate XML output
        xml_output = processor._format_as_xml(
            interchange,
            include_metadata=True,
            metadata=metadata
        )
        
        # Parse XML and validate structure
        root = ET.fromstring(xml_output)
        assert root.tag == "edi_document"
        
        # Validate required elements
        metadata_elem = root.find("metadata")
        segments_elem = root.find("segments")
        
        assert metadata_elem is not None
        assert segments_elem is not None
        
        # Validate metadata elements
        parsed_at_elem = metadata_elem.find("parsed_at")
        segment_count_elem = metadata_elem.find("segment_count")
        has_errors_elem = metadata_elem.find("has_errors")
        
        assert parsed_at_elem is not None
        assert segment_count_elem is not None
        assert has_errors_elem is not None
        
        assert parsed_at_elem.text == "2024-01-15T10:30:00Z"
        assert segment_count_elem.text == "9"
        assert has_errors_elem.text == "False"
        
        # Validate segment structure
        segments = segments_elem.findall("segment")
        assert len(segments) > 0
        
        first_segment = segments[0]
        assert first_segment.get("id") == "ISA"
        assert first_segment.get("line") == "1"
        
        # Validate element structure
        elements = first_segment.findall("element")
        assert len(elements) > 0
        
        first_element = elements[0]
        assert first_element.get("position") == "1"
        assert first_element.text is not None
        
        print("✅ XML format validation passed")
    
    def test_csv_output_format(self, parsing_formats_fixtures):
        """Test CSV output format compliance."""
        processor, interchange, metadata = parsing_formats_fixtures
        
        # Generate CSV output
        csv_output = processor._format_as_csv(
            interchange,
            include_metadata=True,
            metadata=metadata
        )
        
        # Parse CSV and validate structure
        csv_reader = csv.reader(io.StringIO(csv_output))
        rows = list(csv_reader)
        
        # Validate header row
        assert len(rows) > 0
        header_row = rows[0]
        
        expected_headers = ["segment_id", "line_number", "element_1", "element_2", "element_3", 
                           "element_4", "element_5", "element_6", "element_7", "element_8",
                           "element_9", "element_10", "element_11", "element_12", "element_13",
                           "element_14", "element_15", "element_16", "raw_content"]
        
        assert header_row == expected_headers
        
        # Validate data rows
        data_rows = [row for row in rows[1:] if row and not row[0].startswith('#')]
        assert len(data_rows) > 0
        
        # Validate first data row (ISA segment)
        first_row = data_rows[0]
        assert first_row[0] == "ISA"  # segment_id
        assert first_row[1] == "1"    # line_number
        assert first_row[2] == "00"   # first element
        assert len(first_row) == 19   # All columns present
        
        # Validate metadata comments
        metadata_lines = [line for line in csv_output.split('\n') if line.startswith('#')]
        assert len(metadata_lines) > 0
        assert any("segment_count: 9" in line for line in metadata_lines)
        
        print("✅ CSV format validation passed")
    
    def test_json_output_without_metadata(self, parsing_formats_fixtures):
        """Test JSON output without metadata."""
        processor, interchange, metadata = parsing_formats_fixtures
        
        json_output = processor._format_as_json(
            interchange,
            include_metadata=False, 
            metadata=metadata
        )
        
        parsed_result = json.loads(json_output)
        
        # Should have segments but no metadata
        assert "segments" in parsed_result
        assert "metadata" not in parsed_result
        
        print("✅ JSON without metadata validation passed")
    
    def test_xml_output_without_metadata(self, parsing_formats_fixtures):
        """Test XML output without metadata."""
        processor, interchange, metadata = parsing_formats_fixtures
        
        xml_output = processor._format_as_xml(
            interchange,
            include_metadata=False,
            metadata=metadata
        )
        
        root = ET.fromstring(xml_output)
        
        # Should have segments but no metadata
        segments_elem = root.find("segments")
        metadata_elem = root.find("metadata")
        
        assert segments_elem is not None
        assert metadata_elem is None
        
        print("✅ XML without metadata validation passed")
    
    def test_csv_output_without_metadata(self, parsing_formats_fixtures):
        """Test CSV output without metadata."""
        processor, interchange, metadata = parsing_formats_fixtures
        
        csv_output = processor._format_as_csv(
            interchange,
            include_metadata=False,
            metadata=metadata
        )
        
        # Should not have metadata comments
        metadata_lines = [line for line in csv_output.split('\n') if line.startswith('#')]
        assert len(metadata_lines) == 0
        
        print("✅ CSV without metadata validation passed")
    
    def test_segment_content_accuracy(self, parsing_formats_fixtures):
        """Test that segment content is accurately represented across formats."""
        processor, interchange, metadata = parsing_formats_fixtures
        
        # Get all format outputs
        json_output = processor._format_as_json(interchange, False, {})
        xml_output = processor._format_as_xml(interchange, False, {})
        csv_output = processor._format_as_csv(interchange, False, {})
        
        # Parse JSON
        json_data = json.loads(json_output)
        json_segments = json_data["segments"]
        
        # Parse XML
        xml_root = ET.fromstring(xml_output)
        xml_segments = xml_root.find("segments").findall("segment")
        
        # Parse CSV
        csv_reader = csv.reader(io.StringIO(csv_output))
        csv_rows = list(csv_reader)
        csv_segments = csv_rows[1:]  # Skip header
        
        # Compare segment counts
        assert len(json_segments) == len(xml_segments)
        assert len(json_segments) == len(csv_segments)
        
        # Compare first segment (ISA) across formats
        json_isa = json_segments[0]
        xml_isa = xml_segments[0]
        csv_isa = csv_segments[0]
        
        # Verify segment IDs match
        assert json_isa["segment_id"] == "ISA"
        assert xml_isa.get("id") == "ISA"
        assert csv_isa[0] == "ISA"
        
        # Verify line numbers match
        assert json_isa["line_number"] == 1
        assert int(xml_isa.get("line")) == 1
        assert int(csv_isa[1]) == 1
        
        # Verify first few elements match
        json_elements = json_isa["elements"]
        xml_elements = xml_isa.findall("element")
        csv_elements = csv_isa[2:18]  # Elements 1-16
        
        assert json_elements[0] == "00"
        assert xml_elements[0].text == "00"
        assert csv_elements[0] == "00"
        
        print("✅ Cross-format content accuracy validation passed")
    
    def test_processor_interface(self):
        """Test processor interface methods."""
        processor = EDIParsingProcessor()
        
        # Test property descriptors
        properties = processor.getPropertyDescriptors()
        assert len(properties) == 6
        
        property_names = [prop.name for prop in properties]
        expected_properties = [
            "Output Format", "Include Metadata", "Schema Name", 
            "Segment Filter", "Tenant ID", "Schema Base Path"
        ]
        
        for expected_prop in expected_properties:
            assert expected_prop in property_names
        
        # Test relationships
        relationships = processor.getRelationships()
        assert len(relationships) == 2
        assert "success" in relationships
        assert "failure" in relationships
        
        print("✅ Processor interface validation passed")
    
    def test_metadata_extraction(self, parsing_formats_fixtures):
        """Test metadata extraction functionality."""
        processor, interchange, metadata = parsing_formats_fixtures
        
        metadata = processor._extract_metadata(
            interchange,
            "2024-01-15T10:30:00Z", 
            "test-tenant"
        )
        
        # Verify required metadata fields
        required_fields = [
            "parsed_at", "segment_count", "has_errors", "tenant_id"
        ]
        
        for field in required_fields:
            assert field in metadata
        
        # Verify metadata values
        assert metadata["parsed_at"] == "2024-01-15T10:30:00Z"
        assert metadata["tenant_id"] == "test-tenant"
        assert isinstance(metadata["segment_count"], int)
        assert isinstance(metadata["has_errors"], bool)
        
        # Verify interchange info
        if "interchange_control_number" in metadata:
            assert metadata["interchange_control_number"] == "000000001"
        
        # Verify transaction set info
        if "transaction_sets" in metadata:
            assert isinstance(metadata["transaction_sets"], list)
            if metadata["transaction_sets"]:
                tx_set = metadata["transaction_sets"][0]
                assert "transaction_set_identifier" in tx_set
                assert "control_number" in tx_set
                assert "segment_count" in tx_set
        
        print("✅ Metadata extraction validation passed")

if __name__ == "__main__":
    pytest.main([__file__, "-v"])