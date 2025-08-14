import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.services.edi_parsing_service import EdiParsingService
from src.core.models.edi_schema_models import ImplementationGuideSchema
from src.core.cdm import CdmInterchange, CdmLoop, CdmSegment, CdmElement

pytestmark = pytest.mark.unit

@pytest.fixture
def edi_parsing_service(mock_schema_manager):
    """Fixture to create a new EdiParsingService for each test."""
    service = EdiParsingService()
    service.schema_manager = mock_schema_manager()
    return service

@pytest.fixture
def mock_schema_manager():
    """Fixture for a mocked SchemaManager."""
    with patch('src.services.edi_parsing_service.SchemaManager') as mock:
        yield mock

@pytest.fixture
def mock_edi_parser():
    """Fixture for a mocked EdiParser."""
    with patch('src.services.edi_parsing_service.EdiParser') as mock:
        yield mock

@pytest.mark.asyncio
async def test_parse_edi_success(
    edi_parsing_service: EdiParsingService, mock_schema_manager, mock_edi_parser
):
    """Test successful parsing of an EDI document."""
    # Arrange
    mock_schema = ImplementationGuideSchema.model_validate({
        'transactionName': 'test',
        'version': '1',
        'description': 'test',
        'structure': []
    })
    mock_schema_manager.return_value.get_schema.return_value = mock_schema

    mock_interchange = CdmInterchange(
        header=CdmSegment(segment_id='ISA', elements=[CdmElement(value='123', position=1)], line_number=1, raw_segment=''),
        trailer=CdmSegment(segment_id='IEA', elements=[CdmElement(value='456', position=1)], line_number=3, raw_segment=''),
        functional_groups=[]
    )
    mock_edi_parser.return_value.parse.return_value = mock_interchange
    mock_edi_parser.return_value.errors = []

    # Act
    result = await edi_parsing_service.parse_edi("test_content", "test_schema", "test_tenant")

    # Assert
    assert len(result) == 2
    assert result[0].id == 'ISA'
    assert result[1].id == 'IEA'
    edi_parsing_service.schema_manager.get_schema.assert_called_once_with("test_schema", "test_tenant")
    mock_edi_parser.assert_called_once_with("test_content", mock_schema)

@pytest.mark.asyncio
async def test_parse_edi_schema_not_found(
    edi_parsing_service: EdiParsingService
):
    """Test that a ValueError is raised when the schema is not found."""
    # Arrange
    edi_parsing_service.schema_manager.get_schema.return_value = None

    # Act & Assert
    with pytest.raises(ValueError, match="Schema not found: test_schema"):
        await edi_parsing_service.parse_edi("test_content", "test_schema", "test_tenant")
    edi_parsing_service.schema_manager.get_schema.assert_called_once_with("test_schema", "test_tenant")

@pytest.mark.asyncio
async def test_parse_edi_with_parsing_errors(
    edi_parsing_service: EdiParsingService, mock_schema_manager, mock_edi_parser
):
    """Test that a ValueError is raised when the EDI document has parsing errors."""
    # Arrange
    mock_schema = ImplementationGuideSchema.model_validate({
        'transactionName': 'test',
        'version': '1',
        'description': 'test',
        'structure': []
    })
    mock_schema_manager.return_value.get_schema.return_value = mock_schema

    mock_error = MagicMock()
    mock_error.message = "Test parsing error"
    mock_edi_parser.return_value.errors = [mock_error]
    mock_edi_parser.return_value.parse.return_value = CdmInterchange(
        header=CdmSegment(segment_id='ISA', elements=[CdmElement(value='123', position=1)], line_number=1, raw_segment=''),
        trailer=CdmSegment(segment_id='IEA', elements=[CdmElement(value='456', position=1)], line_number=3, raw_segment=''),
        functional_groups=[]
    )

    # Act & Assert
    with pytest.raises(ValueError, match="EDI parsing completed with errors: \\['Test parsing error'\\]"):
        await edi_parsing_service.parse_edi("test_content", "test_schema", "test_tenant")
