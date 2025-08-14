import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from src.services.ta1_generation_service import TA1GenerationService
from src.api.schemas import TA1GenerationRequest
from src.core.acknowledgements.ta1_generator import TA1Generator
from src.core.cdm import CdmSegment, CdmElement


pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


@pytest.fixture
def valid_isa_content():
    """Valid ISA segment content for testing."""
    return "ISA*00*          *00*          *ZZ*SENDERID       *ZZ*RECEIVERID     *240715*1200*^*00501*000000001*0*P*>~"


@pytest.fixture
def ta1_request_accept(valid_isa_content):
    """TA1 generation request for acceptance."""
    return TA1GenerationRequest(
        edi_content=valid_isa_content,
        tenant_id="tenant-a",
        workflow_id="ta1-accept-001",
        acknowledgment_code="A"
    )


@pytest.fixture
def ta1_request_reject(valid_isa_content):
    """TA1 generation request for rejection."""
    return TA1GenerationRequest(
        edi_content=valid_isa_content,
        tenant_id="tenant-a",
        workflow_id="ta1-reject-001",
        acknowledgment_code="R",
        error_code="IK901",
        error_note="Interchange rejected due to syntax errors"
    )


@pytest.fixture
def ta1_request_error(valid_isa_content):
    """TA1 generation request for error acknowledgment."""
    return TA1GenerationRequest(
        edi_content=valid_isa_content,
        tenant_id="tenant-a",
        workflow_id="ta1-error-001",
        acknowledgment_code="E",
        error_code="IK903",
        error_note="Interchange control number mismatch"
    )


class TestTA1GenerationService:
    """Test suite for TA1GenerationService."""

    def test_extract_isa_segment_valid(self, ta1_request_accept):
        """Test successful ISA segment extraction."""
        service = TA1GenerationService()
        isa_segment = service._extract_isa_segment(ta1_request_accept.edi_content)
        
        assert isa_segment is not None
        assert isa_segment.segment_id == "ISA"
        assert len(isa_segment.elements) >= 16
        # Check that ISA14 was forced to "1" for TA1 generation
        assert isa_segment.elements[13].value == "1"  # 0-based index for 14th element

    def test_extract_isa_segment_invalid_content(self):
        """Test ISA extraction with invalid content."""
        service = TA1GenerationService()
        isa_segment = service._extract_isa_segment("INVALID CONTENT")
        
        assert isa_segment is None

    def test_extract_isa_segment_empty_content(self):
        """Test ISA extraction with empty content."""
        service = TA1GenerationService()
        isa_segment = service._extract_isa_segment("")
        
        assert isa_segment is None

    def test_create_interchange_errors_accept(self):
        """Test creating interchange errors for acceptance."""
        service = TA1GenerationService()
        errors = service._create_interchange_errors(acknowledgment_code="A")
        
        assert len(errors) == 0

    def test_create_interchange_errors_reject(self):
        """Test creating interchange errors for rejection."""
        service = TA1GenerationService()
        errors = service._create_interchange_errors(
            acknowledgment_code="R",
            error_code="IK901",
            error_note="Test rejection"
        )
        
        assert len(errors) == 1
        assert errors[0].details == "Test rejection"

    def test_create_interchange_errors_error(self):
        """Test creating interchange errors for error acknowledgment."""
        service = TA1GenerationService()
        errors = service._create_interchange_errors(
            acknowledgment_code="E",
            error_code="IK903",
            error_note="Test error"
        )
        
        assert len(errors) == 1
        assert errors[0].details == "Test error"

    def test_extract_ta1_control_number_valid(self):
        """Test extracting control number from valid TA1 content."""
        service = TA1GenerationService()
        ta1_content = "ISA*00*          *00*          *ZZ*RECEIVERID     *ZZ*SENDERID       *240715*1200*^*00501*000000001*0*P*>~\nTA1*000000001*240715*1200*A*000~\nIEA*1*000000001~"
        control_number = service._extract_ta1_control_number(ta1_content)
        
        assert control_number == "000000001"

    def test_extract_ta1_control_number_invalid(self):
        """Test extracting control number from invalid TA1 content."""
        service = TA1GenerationService()
        control_number = service._extract_ta1_control_number("INVALID TA1 CONTENT")
        
        assert control_number == "UNKNOWN"

    def test_extract_ta1_control_number_empty(self):
        """Test extracting control number from empty TA1 content."""
        service = TA1GenerationService()
        control_number = service._extract_ta1_control_number("")
        
        assert control_number == "UNKNOWN"

    @patch('src.services.ta1_generation_service.TA1Generator')
    async def test_generate_ta1_success(self, mock_ta1_generator_class, ta1_request_accept):
        """Test successful TA1 generation."""
        # Mock the TA1Generator
        mock_ta1_generator = Mock()
        mock_ta1_generator.generate.return_value = "ISA*00*          *00*          *ZZ*RECEIVERID     *ZZ*SENDERID       *240715*1200*^*00501*000000001*0*P*>~\nTA1*000000001*240715*1200*A*000~\nIEA*1*000000001~"
        mock_ta1_generator_class.return_value = mock_ta1_generator
        
        service = TA1GenerationService()
        result = await service.generate_ta1(ta1_request_accept)
        
        assert result is not None
        assert result.acknowledgment_code == "A"
        assert result.workflow_id == "ta1-accept-001"
        assert result.control_number == "000000001"
        assert "TA1*000000001*240715*1200*A*000" in result.ta1_content
        assert isinstance(result.generated_at, datetime)
        assert isinstance(result.processing_time_ms, int)

    @patch('src.services.ta1_generation_service.TA1Generator')
    async def test_generate_ta1_with_errors(self, mock_ta1_generator_class, ta1_request_reject):
        """Test TA1 generation with errors."""
        # Mock the TA1Generator
        mock_ta1_generator = Mock()
        mock_ta1_generator.generate.return_value = "ISA*00*          *00*          *ZZ*RECEIVERID     *ZZ*SENDERID       *240715*1200*^*00501*000000001*0*P*>~\nTA1*000000001*240715*1200*R*001~\nIEA*1*000000001~"
        mock_ta1_generator_class.return_value = mock_ta1_generator
        
        service = TA1GenerationService()
        result = await service.generate_ta1(ta1_request_reject)
        
        assert result is not None
        assert result.acknowledgment_code == "R"
        assert result.workflow_id == "ta1-reject-001"
        assert result.control_number == "000000001"

    async def test_generate_ta1_invalid_edi_content(self, ta1_request_accept):
        """Test TA1 generation with invalid EDI content."""
        # Modify request with invalid content
        ta1_request_accept.edi_content = "INVALID EDI CONTENT"
        
        service = TA1GenerationService()
        
        with pytest.raises(ValueError, match="Invalid EDI content: ISA segment not found or malformed"):
            await service.generate_ta1(ta1_request_accept)

    @patch('src.services.ta1_generation_service.TA1Generator')
    async def test_generate_ta1_generator_returns_none(self, mock_ta1_generator_class, ta1_request_accept):
        """Test TA1 generation when generator returns None."""
        # Mock the TA1Generator to return None
        mock_ta1_generator = Mock()
        mock_ta1_generator.generate.return_value = None
        mock_ta1_generator_class.return_value = mock_ta1_generator
        
        service = TA1GenerationService()
        
        with pytest.raises(ValueError, match="TA1 generation failed: generator returned None"):
            await service.generate_ta1(ta1_request_accept)