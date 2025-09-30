"""
Integration tests for validation → TA1 workflow.
Tests the complete flow from EDI validation through TA1 generation.
"""

import pytest
import sys
import os
import json
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from validation_service import EDIValidationService
from ta1_generator import TA1Generator
from edi_parser import EdiParser
from ta1_defs import InterchangeError, TA1NoteCode
from cdm import CdmSegment, CdmElement

pytestmark = pytest.mark.integration

class TestIntegratedWorkflow:
    """Test cases for integrated validation → TA1 workflow."""

    def setup_method(self):
        """Set up test fixtures."""
        self.validation_service = EDIValidationService("/tmp/test_schemas")
        self.ta1_generator = TA1Generator()

    def test_valid_edi_no_ta1_requested(self, standalone_schema):
        """Test valid EDI with no TA1 requested (ISA14=0)."""
        # Valid EDI with ISA14=0 (no ack requested)
        edi_content = """ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *210101*1000*^*00501*000000001*0*P*>~
GS*HC*SENDER*RECEIVER*20210101*1000*1*X*005010~
ST*270*0001~
BHT*0022*13*10001234*20210101*1000~
HL*1**20*1~
NM1*PR*2*ABC INSURANCE*****PI*12345~
SE*6*0001~
GE*1*1~
IEA*1*000000001~"""

        # Step 1: Validate EDI
        with patch.object(self.validation_service.schema_manager, 'get_base_schema', return_value=standalone_schema):
            validation_result = self.validation_service.validate_edi(
                edi_content=edi_content,
                schema_name="test.json",  # Will fail gracefully with schema not found
                
                snip_level=3
            )

        # Step 2: Extract ISA header and check TA1 generation
        parser = EdiParser(edi_content, standalone_schema)
        segments = parser._segmentize(edi_content)
        isa_segment = segments[0]  # First segment should be ISA

        # Step 3: Generate TA1 (should be None since no ack requested and no errors)
        ta1_result = self.ta1_generator.generate(isa_segment, [])

        # Assertions
        assert isa_segment.segment_id == "ISA"
        assert isa_segment.get_element(14) == "0"  # No ack requested
        assert ta1_result is None  # No TA1 should be generated

    def test_valid_edi_with_ta1_requested(self, standalone_schema):
        """Test valid EDI with TA1 requested (ISA14=1)."""
        # Valid EDI with ISA14=1 (ack requested)
        edi_content = """ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *210101*1000*^*00501*000000001*1*P*>~
GS*HC*SENDER*RECEIVER*20210101*1000*1*X*005010~
ST*270*0001~
BHT*0022*13*10001234*20210101*1000~
HL*1**20*1~
NM1*PR*2*ABC INSURANCE*****PI*12345~
SE*6*0001~
GE*1*1~
IEA*1*000000001~"""

        # Step 1: Validate EDI
        with patch.object(self.validation_service.schema_manager, 'get_base_schema', return_value=standalone_schema):
            validation_result = self.validation_service.validate_edi(
                edi_content=edi_content,
                schema_name="test.json",
                
                snip_level=3
            )

        # Step 2: Extract ISA header
        parser = EdiParser(edi_content, standalone_schema)
        segments = parser._segmentize(edi_content)
        isa_segment = segments[0]

        # Step 3: Generate TA1 (should generate acceptance since ack requested)
        ta1_result = self.ta1_generator.generate(isa_segment, [])

        # Assertions
        assert isa_segment.segment_id == "ISA"
        assert isa_segment.get_element(14) == "1"  # Ack requested
        assert ta1_result is not None  # TA1 should be generated
        assert "TA1*" in ta1_result  # Should contain TA1 segment
        assert "*A*" in ta1_result  # Should be acceptance (A)

    def test_invalid_edi_with_ta1_generation(self, standalone_schema):
        """Test invalid EDI that should generate rejection TA1."""
        # Create invalid EDI with ISA14=1
        edi_content = """ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *210101*1000*^*00501*000000001*1*P*>~
GS*HC*SENDER*RECEIVER*20210101*1000*1*X*005010~
ST*270*0001~
INVALID_SEGMENT~
SE*6*0001~
GE*1*1~
IEA*1*000000001~"""

        # Step 1: Extract ISA header
        parser = EdiParser(edi_content, standalone_schema)
        segments = parser._segmentize(edi_content)
        isa_segment = segments[0]

        # Step 2: Create sample interchange errors
        sample_errors = [
            InterchangeError(
                note_code=TA1NoteCode.INVALID_INTERCHANGE_CONTENT,
                details="Invalid segment structure"
            )
        ]

        # Step 3: Generate TA1 with errors
        ta1_result = self.ta1_generator.generate(isa_segment, sample_errors)

        # Assertions
        assert ta1_result is not None
        assert "TA1*" in ta1_result  # Should contain TA1 segment
        assert "*R*" in ta1_result  # Should be rejection (R)
        assert "024" in ta1_result  # Should contain error note code (without requiring asterisks)

    def test_forced_ta1_generation(self, standalone_schema):
        """Test forced TA1 generation regardless of ISA14."""
        # Valid EDI with ISA14=0 but forced generation
        edi_content = """ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *210101*1000*^*00501*000000001*0*P*>~
GS*HC*SENDER*RECEIVER*20210101*1000*1*X*005010~
ST*270*0001~
BHT*0022*13*10001234*20210101*1000~
HL*1**20*1~
NM1*PR*2*ABC INSURANCE*****PI*12345~
SE*6*0001~
GE*1*1~
IEA*1*000000001~"""

        # Step 1: Extract ISA header
        parser = EdiParser(edi_content, standalone_schema)
        segments = parser._segmentize(edi_content)
        isa_segment = segments[0]

        # Step 2: Generate TA1 with force_generation=True
        ta1_result = self.ta1_generator.generate(isa_segment, [], force_generation=True)

        # Assertions
        assert isa_segment.get_element(14) == "0"  # No ack requested
        assert ta1_result is not None  # TA1 should still be generated due to force
        assert "TA1*" in ta1_result
        assert "*A*" in ta1_result  # Should be acceptance

    def test_ta1_interchange_structure(self, standalone_schema):
        """Test that generated TA1 has correct interchange structure."""
        # Sample EDI with TA1 requested
        edi_content = """ISA*00*          *00*          *ZZ*SENDER123      *ZZ*RECEIVER456    *210101*1000*^*00501*000000001*1*P*>~
GS*HC*SENDER123*RECEIVER456*20210101*1000*1*X*005010~
ST*270*0001~
BHT*0022*13*10001234*20210101*1000~
HL*1**20*1~
NM1*PR*2*ABC INSURANCE*****PI*12345~
SE*6*0001~
GE*1*1~
IEA*1*000000001~"""

        # Extract ISA header
        parser = EdiParser(edi_content, standalone_schema)
        segments = parser._segmentize(edi_content)
        isa_segment = segments[0]

        # Generate TA1
        ta1_result = self.ta1_generator.generate(isa_segment, [])

        # Parse the generated TA1 to verify structure
        ta1_segments = ta1_result.split('~') if ta1_result else []

        # Should have ISA + TA1 + IEA structure
        assert len(ta1_segments) >= 3
        assert ta1_segments[0].startswith('ISA*')  # ISA header
        assert ta1_segments[1].startswith('TA1*')  # TA1 segment
        assert ta1_result and 'IEA*' in ta1_result  # IEA trailer

        # Verify ISA header has sender/receiver swapped
        isa_parts = ta1_segments[0].split('*')
        assert isa_parts[6] == 'RECEIVER456    '  # Original receiver becomes sender
        assert isa_parts[8] == 'SENDER123      '  # Original sender becomes receiver

        # Verify TA1 segment structure
        ta1_parts = ta1_segments[1].split('*')
        assert ta1_parts[0] == 'TA1'  # Segment ID
        assert ta1_parts[1] == '000000001'  # Original ICN
        assert ta1_parts[4] == 'A'  # Acceptance code
        assert ta1_parts[5] == '000'  # No error code

    def test_workflow_integration_simulation(self, standalone_schema):
        """Simulate the complete NiFi workflow integration."""

        # Simulate FlowFile data
        test_edi = """ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *210101*1000*^*00501*000000001*1*P*>~
GS*HC*SENDER*RECEIVER*20210101*1000*1*X*005010~
ST*270*0001~
BHT*0022*13*10001234*20210101*1000~
HL*1**20*1~
NM1*PR*2*ABC INSURANCE*****PI*12345~
SE*6*0001~
GE*1*1~
IEA*1*000000001~"""

        # Step 1: Simulate EDI Validation Processor
        with patch.object(self.validation_service.schema_manager, 'get_base_schema', return_value=standalone_schema):
            validation_result = self.validation_service.validate_edi(
                edi_content=test_edi,
                schema_name="test.json",
                
                snip_level=3
            )

        # Simulate FlowFile attributes that would be set by validation processor
        flowfile_attributes = {
            "edi.validation.valid": str(validation_result.valid).lower(),
            "edi.validation.findings.count": str(len(validation_result.findings)),
            "edi.validation.findings": json.dumps([
                {
                    "level": finding.level,
                    "code": finding.code,
                    "message": finding.message,
                    "location": finding.location
                } for finding in validation_result.findings
            ]),
            "tenant.id": "test-tenant"
        }

        # Step 2: Simulate TA1 Generation Processor
        # Extract ISA header
        parser = EdiParser(test_edi, standalone_schema)
        segments = parser._segmentize(test_edi)
        isa_segment = segments[0]

        # Convert validation findings to interchange errors (simplified)
        interchange_errors = []  # No errors for this valid EDI

        # Generate TA1
        ta1_result = self.ta1_generator.generate(isa_segment, interchange_errors)

        # Step 3: Verify integrated workflow results
        assert validation_result is not None
        assert ta1_result is not None  # TA1 should be generated (ISA14=1)

        # Verify FlowFile attributes would be set correctly
        assert flowfile_attributes["edi.validation.valid"] in ["true", "false"]
        assert flowfile_attributes["tenant.id"] == "test-tenant"

        # Verify TA1 structure
        assert "ISA*" in ta1_result  # Complete interchange
        assert "TA1*" in ta1_result  # TA1 segment
        assert "IEA*" in ta1_result  # IEA trailer

        print(f"Workflow integration test completed successfully")
        print(f"   Validation: {'VALID' if validation_result.valid else 'INVALID'}")
        print(f"   Findings: {len(validation_result.findings)}")
        print(f"   TA1 Generated: {ta1_result is not None}")
        print(f"   TA1 Length: {len(ta1_result) if ta1_result else 0} characters")

if __name__ == "__main__":
    pytest.main([__file__, "-v"])