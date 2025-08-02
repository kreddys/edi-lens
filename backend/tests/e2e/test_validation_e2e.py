import pytest
import httpx
import uuid
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.core.config import settings
from src.core.storage import storage_client
from src.models.validation_transaction import ValidationTransaction, ValidationStatus
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

    # 3. Assert (API Response)
    assert response.status_code == 200, f"API call failed: {response.text}"
    data = response.json()
    assert data["status"] == "Validation Complete"
    assert data["ta1_acknowledgement"] is not None
    assert "*A*000~" in data["ta1_acknowledgement"]

    # 4. Assert (Database State)
    result = await db_session.execute(select(ValidationTransaction))
    db_record = result.scalars().first()

    assert db_record is not None, "ValidationTransaction record was not created."
    assert db_record.tenant_id == "tenant-a"
    assert db_record.original_filename == "e2e_success.x12"
    assert db_record.status == ValidationStatus.COMPLETE
    assert db_record.request_object_key is not None
    assert db_record.ta1_object_key is not None

    # 5. Assert (Object Storage State)
    original_file_content = storage_client.download(db_record.request_object_key)
    assert original_file_content is not None
    assert original_file_content.decode('utf-8') == edi_with_ack_requested
    ta1_file_content = storage_client.download(db_record.ta1_object_key)
    assert ta1_file_content is not None
    assert ta1_file_content.decode('utf-8') == data["ta1_acknowledgement"]

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

    # 3. Assert (API Response)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "Rejected at Interchange Level"
    assert data["ta1_acknowledgement"] is not None
    assert "*R*001~" in data["ta1_acknowledgement"]

    # 4. Assert (Database State)
    result = await db_session.execute(select(ValidationTransaction))
    db_record = result.scalars().first()

    assert db_record is not None
    assert db_record.tenant_id == "tenant-b"
    assert db_record.status == ValidationStatus.FAILED
    assert db_record.request_object_key is not None
    assert db_record.ta1_object_key is not None

    # 5. Assert (Object Storage State)
    original_file_content = storage_client.download(db_record.request_object_key)
    assert original_file_content is not None
    ta1_file_content = storage_client.download(db_record.ta1_object_key)
    assert ta1_file_content is not None