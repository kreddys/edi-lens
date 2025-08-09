# FILE: backend/tests/services/test_validation_service.py

import pytest
import pytest_asyncio
import uuid
from unittest.mock import MagicMock, AsyncMock

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.services.validation_service import ValidationService, PrevalidationError
from src.models.validation_transaction import ValidationTransaction, ValidationStatus
from src.models.processing_log import ProcessingLog
# --- ADDED: Import the real models we need to create ---
from src.models.trading_partner import TradingPartner
from src.models.partner_profile import PartnerProfile

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]

@pytest_asyncio.fixture
def mock_storage_client(mocker):
    """Mocks the storage_client to prevent real file uploads during tests."""
    mock_client = MagicMock()
    mock_client.upload = MagicMock()
    mocker.patch('src.services.validation_service.storage_client', mock_client)
    return mock_client

@pytest_asyncio.fixture
async def setup_service_test_profile(db_session: AsyncSession) -> PartnerProfile:
    """Creates a real partner and profile in the DB for the ValidationService tests."""
    partner = TradingPartner(tenant_id="test-tenant", name="Service Test Partner")
    profile = PartnerProfile(
        partner=partner,
        tenant_id="test-tenant",
        name="Service Test Profile",
        validation_schema_name="837.5010.X222.A1.json", # <-- FIX (was correct, but confirming)
        snip_level="SNIP3",
        generate_ta1=True,
        generate_999=False
    )

@pytest.mark.asyncio
async def test_process_edi_file_success_path(
    db_session: AsyncSession,
    mock_storage_client: MagicMock,
    setup_service_test_profile: PartnerProfile, # <-- Use the new fixture
    valid_837p_edi_string: str
):
    """Tests the full workflow for a valid EDI file using an explicit profile."""
    # Arrange
    service = ValidationService(db_session)
    profile = setup_service_test_profile
    
    # Act
    response = await service.process_edi_file(
        edi_data=valid_837p_edi_string,
        file_name="valid.edi",
        tenant_id=profile.tenant_id,
        user_id="test-user",
        username="testuser",
        profile_name=profile.name
    )

    # Assert API Response
    assert response.valid is True
    assert response.matched_profile == profile.name
    
    # Assert Database State
    result = await db_session.execute(select(ValidationTransaction))
    validation_record = result.scalars().first()
    assert validation_record is not None
    assert validation_record.partner_profile_id == profile.id

    result = await db_session.execute(select(ProcessingLog))
    processing_record = result.scalars().first()
    assert processing_record is not None
    assert processing_record.profile_id == profile.id

@pytest.mark.asyncio
async def test_process_edi_file_ta1_rejection_path(
    db_session: AsyncSession,
    mock_storage_client: MagicMock,
    setup_service_test_profile: PartnerProfile, # <-- Use the new fixture
    edi_with_isa_error: str
):
    """Tests the workflow for a file rejected at the TA1 level."""
    # Arrange
    service = ValidationService(db_session)
    profile = setup_service_test_profile

    # Act
    response = await service.process_edi_file(
        edi_data=edi_with_isa_error,
        file_name="invalid_isa.edi",
        tenant_id=profile.tenant_id,
        user_id="test-user",
        username="testuser",
        profile_name=profile.name
    )

    # Assert API Response
    assert response.valid is False
    assert response.matched_profile == profile.name
    assert response.ta1_content is not None

@pytest.mark.asyncio
async def test_process_edi_file_prevalidation_failure(
    db_session: AsyncSession,
    mock_storage_client: MagicMock,
    setup_service_test_profile: PartnerProfile # <-- Use the new fixture
):
    """Tests that a PrevalidationError is caught and handled correctly."""
    # Arrange
    service = ValidationService(db_session)
    invalid_edi = "this is not edi"
    profile = setup_service_test_profile
    
    # Act & Assert
    with pytest.raises(PrevalidationError) as exc_info:
        await service.process_edi_file(
            edi_data=invalid_edi,
            file_name="garbage.txt",
            tenant_id=profile.tenant_id,
            user_id="test-user",
            username="testuser",
            profile_name=profile.name
        )
    
    assert "Could not determine implementation guide version" in str(exc_info.value)