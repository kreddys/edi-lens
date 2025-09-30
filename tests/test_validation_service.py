"""
Unit tests for the EDI validation service.
"""

import pytest
import sys
import os
from unittest.mock import patch, MagicMock

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from validation_service import EDIValidationService, ValidationResult

pytestmark = pytest.mark.unit

class TestEDIValidationService:
    """Test cases for EDI validation service."""

    def setup_method(self):
        """Set up test fixtures."""
        self.validation_service = EDIValidationService("/tmp/test_schemas")

    def test_validation_service_init(self):
        """Test validation service initialization."""
        assert self.validation_service is not None
        assert self.validation_service.schema_manager is not None

    def test_validation_with_invalid_schema(self):
        """Test validation with non-existent schema."""
        edi_content = "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *210101*1000*^*00501*000000001*0*P*>~"

        with patch.object(self.validation_service.schema_manager, 'get_base_schema', return_value=None):
            result = self.validation_service.validate_edi(
                edi_content=edi_content,
                schema_name="nonexistent.json",
                snip_level=3
            )

            assert isinstance(result, ValidationResult)
            assert not result.valid
            assert len(result.findings) > 0
            assert "Schema not found" in result.findings[0].message

    def test_validation_with_empty_content(self):
        """Test validation with empty EDI content."""
        with patch.object(self.validation_service.schema_manager, 'get_base_schema', return_value=MagicMock()):
            result = self.validation_service.validate_edi(
                edi_content="",
                schema_name="test.json",
                snip_level=3
            )

            assert isinstance(result, ValidationResult)
            assert not result.valid
            assert len(result.findings) > 0

    def test_validation_success_with_valid_edi(self):
        """Test successful validation with valid EDI content."""
        edi_content = """ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *210101*1000*^*00501*000000001*0*P*>~
GS*HC*SENDER*RECEIVER*20210101*1000*1*X*005010X222A1~
ST*837*0001*005010X222A1~
BHT*0019*00*1234*20210101*1000*CH~
NM1*41*2*PREMIER BILLING*****46*SUBMITTER1~
PER*IC*JOHN DOE*TE*8005551212~
NM1*40*2*PAYER A*****46*RECEIVER1~
HL*1**20*1~
NM1*85*2*BILLING PROVIDER*****XX*1234567890~
N3*123 MAIN ST~
N4*ANYTOWN*CA*90210~
REF*EI*123456789~
HL*2*1*22*0~
SBR*P*18*GRP123******CI~
NM1*IL*1*DOE*JOHN****MI*SUBID123~
NM1*PR*2*PAYER A*****PI*PAYERID123~
CLM*PATCTRL123*500***11>B>1*Y*A*Y*Y~
DTP*431*D8*20210101~
PWK*OZ*BM***AC*CONTROL123~
HI*BK>87340~
LX*1~
SV1*HC>99213*125*UN*1***1**Y~
DTP*472*D8*20210101~
SE*25*0001~
GE*1*1~
IEA*1*000000001~"""

        # Mock schema and parser
        mock_schema = MagicMock()
        mock_parser = MagicMock()
        mock_interchange = MagicMock()
        mock_interchange.errors = []

        with patch.object(self.validation_service.schema_manager, 'get_base_schema', return_value=mock_schema), \
             patch('validation_service.EdiParser', return_value=mock_parser):
            mock_parser.parse.return_value = mock_interchange
            mock_parser._collect_all_errors.return_value = []

            result = self.validation_service.validate_edi(
                edi_content=edi_content,
                schema_name="837p.json",
                
                snip_level=3
            )

            assert isinstance(result, ValidationResult)
            assert result.valid
            assert len(result.findings) == 0

    def test_validation_with_findings(self):
        """Test validation that produces findings."""
        edi_content = "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *210101*1000*^*00501*000000001*0*P*>~"

        # Mock schema and parser with errors
        mock_schema = MagicMock()
        mock_parser = MagicMock()
        mock_interchange = MagicMock()
        mock_error = MagicMock()
        mock_error.element_xid = "ISA01"
        mock_error.message = "Invalid element value"
        mock_error.segment_id = "ISA"
        mock_error.line_number = 1

        with patch.object(self.validation_service.schema_manager, 'get_base_schema', return_value=mock_schema), \
             patch('validation_service.EdiParser', return_value=mock_parser):
            mock_parser.parse.return_value = mock_interchange
            mock_parser._collect_all_errors.return_value = [("ISA Segment", mock_error)]

            result = self.validation_service.validate_edi(
                edi_content=edi_content,
                schema_name="837p.json",
                
                snip_level=3
            )

            assert isinstance(result, ValidationResult)
            assert not result.valid
            assert len(result.findings) == 1
            assert result.findings[0].level == "error"
            assert result.findings[0].code == "ISA01"
            assert result.findings[0].message == "Invalid element value"

    def test_validation_exception_handling(self):
        """Test that exceptions during validation are handled properly."""
        edi_content = "invalid edi content"

        with patch.object(self.validation_service.schema_manager, 'get_base_schema', side_effect=Exception("Schema loading failed")):
            result = self.validation_service.validate_edi(
                edi_content=edi_content,
                schema_name="837p.json",
                
                snip_level=3
            )

            assert isinstance(result, ValidationResult)
            assert not result.valid
            assert len(result.findings) == 1
            assert "Schema loading failed" in result.findings[0].message
            assert result.findings[0].level == "error"
            assert result.findings[0].code == "VALIDATION_ERROR"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])