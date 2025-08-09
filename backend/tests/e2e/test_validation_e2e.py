import pytest
import httpx
import uuid
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.core.config import settings
from src.core.storage import storage_client
from src.models.validation_transaction import ValidationTransaction, ValidationStatus
from src.models.processing_log import ProcessingLog
from tests.e2e.e2e_utils import get_user_token

pytestmark = [pytest.mark.asyncio, pytest.mark.e2e]


@pytest.mark.asyncio
async def test_validation_workflow_e2e_successful_ack_requested(
    edi_with_ack_requested: str,
    db_session: AsyncSession
):
    """
    Tests the entire validation workflow end-to-end for a successful file that requests an ack.
    """
    # 1. Arrange
    token = await get_user_token("superuser@edilens.com")
    headers = {"Authorization": f"Bearer {token}", "X-Tenant-ID": "tenant-a"}
    backend_url = f"http://{settings.BACKEND_HOST}:8000/api/v1/validate"
    payload = {"edi_data": edi_with_ack_requested, "file_name": "e2e_success.x12"}
    
    # 2. Act
    async with httpx.AsyncClient() as client:
        response = await client.post(backend_url, headers=headers, json=payload)

    # 3. Assert (Enhanced API Response)
    assert response.status_code == 200, f"API call failed: {response.text}"
    data = response.json()
    assert data["valid"] is True
    assert data["status"] == "Validation Complete"
    assert data["matched_profile"] == "default-fallback"
    assert data["detection_method"] == "fallback"
    assert data["ta1_content"] is not None  # TA1 generated for ack requested
    assert data["processing_time_ms"] is not None
    assert "*A*000~" in data["ta1_content"]
    # Legacy fields should still work
    assert data["ta1_acknowledgement"] is not None
    assert data["ta1_acknowledgement"] == data["ta1_content"]

    # 4. Assert (Database State - No ValidationTransaction for fallback profiles)
    result = await db_session.execute(select(ValidationTransaction))
    validation_record = result.scalars().first()
    assert validation_record is None, "ValidationTransaction should not be created for fallback profiles"

    # 5. Assert (ProcessingLog Database State - E2E with fresh connection for cross-process visibility)
    import asyncio
    from sqlalchemy.ext.asyncio import create_async_engine
    
    # Wait a moment for the API server to commit the ProcessingLog record
    await asyncio.sleep(0.3)
    
    # Use a direct connection to see committed records from the API server
    test_engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async with test_engine.begin() as conn:
        result = await conn.execute(select(ProcessingLog).filter_by(tenant_id="tenant-a"))
        processing_record = result.first()
    await test_engine.dispose()
    
    assert processing_record is not None, "ProcessingLog record was not created by API server."
    assert processing_record.tenant_id == "tenant-a"
    assert processing_record.source == "API"
    assert processing_record.file_name == "e2e_success.x12"
    assert processing_record.validation_result == "VALID"
    assert processing_record.ta1_generated is True
    assert processing_record.ta1_999_generated is False
    assert processing_record.original_content_path is not None
    assert processing_record.ta1_content_path is not None

    # 6. Assert (Object Storage State)
    original_file_content = storage_client.download(processing_record.original_content_path)
    assert original_file_content is not None
    assert original_file_content.decode('utf-8') == edi_with_ack_requested
    ta1_file_content = storage_client.download(processing_record.ta1_content_path)
    assert ta1_file_content is not None
    assert ta1_file_content.decode('utf-8') == data["ta1_content"]

@pytest.mark.asyncio
async def test_validation_workflow_e2e_rejected_file(
    edi_with_isa_error: str,
    db_session: AsyncSession
):
    """
    Tests the E2E workflow for a file that is rejected at the TA1 level.
    """
    # 1. Arrange
    token = await get_user_token("superuser@edilens.com")
    headers = {"Authorization": f"Bearer {token}", "X-Tenant-ID": "tenant-b"}
    backend_url = f"http://{settings.BACKEND_HOST}:8000/api/v1/validate"
    payload = {"edi_data": edi_with_isa_error, "file_name": "e2e_rejected.x12"}

    # 2. Act
    async with httpx.AsyncClient() as client:
        response = await client.post(backend_url, headers=headers, json=payload)

    # 3. Assert (Enhanced API Response)
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is False
    assert data["status"] == "Rejected at Interchange Level"
    assert data["matched_profile"] == "default-fallback"
    assert data["detection_method"] == "fallback"
    assert data["ta1_content"] is not None  # TA1 generated for errors
    assert data["processing_time_ms"] is not None
    assert "*R*001~" in data["ta1_content"]
    # Legacy fields should still work
    assert data["ta1_acknowledgement"] is not None
    assert data["ta1_acknowledgement"] == data["ta1_content"]

    # 4. Assert (Database State - No ValidationTransaction for fallback profiles)
    result = await db_session.execute(select(ValidationTransaction))
    validation_record = result.scalars().first()
    assert validation_record is None, "ValidationTransaction should not be created for fallback profiles"

    # 5. Assert (ProcessingLog Database State - E2E with fresh connection for cross-process visibility)
    import asyncio
    from sqlalchemy.ext.asyncio import create_async_engine
    
    # Wait a moment for the API server to commit the ProcessingLog record
    await asyncio.sleep(0.3)
    
    # Use a direct connection to see committed records from the API server
    test_engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async with test_engine.begin() as conn:
        result = await conn.execute(select(ProcessingLog).filter_by(tenant_id="tenant-b"))
        processing_record = result.first()
    await test_engine.dispose()
    
    assert processing_record is not None, "ProcessingLog record was not created by API server."
    assert processing_record.tenant_id == "tenant-b"
    assert processing_record.source == "API"
    assert processing_record.file_name == "e2e_rejected.x12"
    assert processing_record.validation_result == "INVALID"
    assert processing_record.ta1_generated is True
    assert processing_record.ta1_999_generated is False
    assert processing_record.original_content_path is not None
    assert processing_record.ta1_content_path is not None

    # 6. Assert (Object Storage State)
    original_file_content = storage_client.download(processing_record.original_content_path)
    assert original_file_content is not None
    ta1_file_content = storage_client.download(processing_record.ta1_content_path)
    assert ta1_file_content is not None