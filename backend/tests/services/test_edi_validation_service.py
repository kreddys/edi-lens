import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.services.edi_validation_service import EDIValidationService, ValidationResult
from src.core.models.edi_schema_models import ImplementationGuideSchema
from src.core.cdm import CdmValidationError

pytestmark = pytest.mark.unit

@pytest.fixture
def edi_validation_service(mock_schema_manager):
    """Fixture to create a new EDIValidationService for each test."""
    service = EDIValidationService()
    service.schema_manager = mock_schema_manager()
    return service

@pytest.fixture
def mock_schema_manager():
    """Fixture for a mocked SchemaManager."""
    with patch('src.services.edi_validation_service.SchemaManager') as mock:
        yield mock

@pytest.fixture
def mock_edi_parser():
    """Fixture for a mocked EdiParser."""
    with patch('src.services.edi_validation_service.EdiParser') as mock:
        yield mock

@pytest.mark.asyncio
async def test_validate_edi_success(
    edi_validation_service: EDIValidationService, mock_schema_manager, mock_edi_parser
):
    """Test successful validation of an EDI document."""
    # Arrange
    mock_schema = ImplementationGuideSchema.model_validate({
        'transactionName': 'test',
        'version': '1',
        'description': 'test',
        'structure': []
    })
    mock_schema_manager.return_value.get_schema.return_value = mock_schema
    mock_edi_parser.return_value.errors = []

    # Act
    result = await edi_validation_service.validate_edi("test_content", "test_schema", "test_tenant")

    # Assert
    assert result.valid is True
    assert len(result.findings) == 0
    edi_validation_service.schema_manager.get_schema.assert_called_once_with("test_schema", "test_tenant")
    mock_edi_parser.assert_called_once_with("test_content", mock_schema)

@pytest.mark.asyncio
async def test_validate_edi_schema_not_found(
    edi_validation_service: EDIValidationService
):
    """Test that a ValueError is raised when the schema is not found."""
    # Arrange
    edi_validation_service.schema_manager.get_schema.return_value = None

    # Act
    result = await edi_validation_service.validate_edi("test_content", "test_schema", "test_tenant")

    # Assert
    assert result.valid is False
    assert len(result.findings) == 1
    assert "Schema not found" in result.findings[0].message
    edi_validation_service.schema_manager.get_schema.assert_called_once_with("test_schema", "test_tenant")

@pytest.mark.asyncio
async def test_validate_edi_with_findings(
    edi_validation_service: EDIValidationService, mock_schema_manager, mock_edi_parser
):
    """Test validation with findings."""
    # Arrange
    mock_schema = ImplementationGuideSchema.model_validate({
        'transactionName': 'test',
        'version': '1',
        'description': 'test',
        'structure': []
    })
    mock_schema_manager.return_value.get_schema.return_value = mock_schema

    mock_error = CdmValidationError(
        message="Test validation error",
        line_number=10,
        segment_id="CLM",
        error_code="E123"
    )
    mock_edi_parser.return_value.errors = [mock_error]

    # Act
    result = await edi_validation_service.validate_edi("test_content", "test_schema", "test_tenant")

    # Assert
    assert result.valid is False
    assert len(result.findings) == 1
    assert result.findings[0].message == "Test validation error"
    assert result.findings[0].location.line_number == 10

@pytest.mark.asyncio
async def test_validate_edi_exception_handling(
    edi_validation_service: EDIValidationService, mock_schema_manager
):
    """Test that an unexpected exception is caught and returned as a finding."""
    # Arrange
    mock_schema_manager.return_value.get_schema.side_effect = Exception("Unexpected Error")

    # Act
    result = await edi_validation_service.validate_edi("test_content", "test_schema", "test_tenant")

    # Assert
    assert result.valid is False
    assert len(result.findings) == 1
    assert "Unexpected Error" in result.findings[0].message
