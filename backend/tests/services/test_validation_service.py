import pytest
import pytest_asyncio
import uuid
from unittest.mock import MagicMock

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.services.validation_service import ValidationService, PrevalidationError
from src.models.validation_transaction import ValidationTransaction, ValidationStatus

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]

@pytest_asyncio.fixture
def mock_storage_client(mocker):
    """Mocks the storage_client to prevent real file uploads during tests."""
    mock_client = MagicMock()
    mock_client.upload = MagicMock()
    mocker.patch('src.services.validation_service.storage_client', mock_client)
    return mock_client

@pytest.mark.asyncio
async def test_process_edi_file_success_path(
    db_session: AsyncSession,
    mock_storage_client: MagicMock,
    valid_837p_edi_string: str
):
    """
    Tests the full workflow for a valid EDI file, ensuring DB records are
    created and updated correctly, and files are 'uploaded'.
    """
    # Arrange
    service = ValidationService(db_session)
    tenant_id = "test-tenant-1"
    
    # Act
    response = await service.process_edi_file(
        edi_data=valid_837p_edi_string,
        file_name="valid.edi",
        tenant_id=tenant_id,
        user_id="test-user",
        username="testuser"
    )

    # Assert
    assert response.status == "Validation Complete"
    assert response.ta1_acknowledgement is None

    # Assert Storage Calls
    assert mock_storage_client.upload.call_count == 1
    # Check that the first call was for the request file
    request_key_args = mock_storage_client.upload.call_args_list[0].args
    assert request_key_args[1].startswith(f"{tenant_id}/")
    assert request_key_args[1].endswith("/request.edi")

    # Assert Database State
    result = await db_session.execute(select(ValidationTransaction))
    db_record = result.scalars().first()
    
    assert db_record is not None
    assert db_record.tenant_id == tenant_id
    assert db_record.original_filename == "valid.edi"
    assert db_record.status == ValidationStatus.COMPLETE
    assert db_record.ta1_object_key is None
    assert db_record.response_999_object_key is None

@pytest.mark.asyncio
async def test_process_edi_file_ta1_rejection_path(
    db_session: AsyncSession,
    mock_storage_client: MagicMock,
    edi_with_isa_error: str
):
    """
    Tests the workflow for a file rejected at the TA1 level.
    """
    # Arrange
    service = ValidationService(db_session)
    tenant_id = "test-tenant-2"

    # Act
    response = await service.process_edi_file(
        edi_data=edi_with_isa_error,
        file_name="invalid_isa.edi",
        tenant_id=tenant_id,
        user_id="test-user",
        username="testuser"
    )

    # Assert
    assert response.status == "Rejected at Interchange Level"
    assert response.ta1_acknowledgement is not None

    # Assert Storage Calls (Request + TA1)
    assert mock_storage_client.upload.call_count == 2
    request_key = mock_storage_client.upload.call_args_list[0].args[1]
    ta1_key = mock_storage_client.upload.call_args_list[1].args[1]
    assert request_key.endswith("/request.edi")
    assert ta1_key.endswith("/ta1.edi")

    # Assert Database State
    result = await db_session.execute(select(ValidationTransaction))
    db_record = result.scalars().first()

    assert db_record is not None
    assert db_record.status == ValidationStatus.FAILED
    assert db_record.ta1_object_key is not None

@pytest.mark.asyncio
async def test_process_edi_file_prevalidation_failure(
    db_session: AsyncSession,
    mock_storage_client: MagicMock
):
    """
    Tests that a PrevalidationError is caught and handled correctly.
    Note: We don't need a full DB record for this, as it fails before DB interaction.
    """
    # Arrange
    service = ValidationService(db_session)
    invalid_edi = "this is not edi"
    
    # Act & Assert
    with pytest.raises(PrevalidationError) as exc_info:
        await service.process_edi_file(
            edi_data=invalid_edi,
            file_name="garbage.txt",
            tenant_id="test-tenant-3",
            user_id="test-user",
            username="testuser"
        )
    
    assert "Could not determine implementation guide version" in str(exc_info.value)
    
    # Assert that no files were uploaded and no DB record was created
    mock_storage_client.upload.assert_not_called()
    result = await db_session.execute(select(ValidationTransaction))
    assert result.scalars().first() is None