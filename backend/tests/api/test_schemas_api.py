import pytest
import pytest_asyncio
import json
import uuid

from httpx import AsyncClient
from src.main import app
from src.core.auth import User, RealmAccess, get_current_user
from src.core.storage import storage_client

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]

@pytest.fixture
def mock_get_current_user():
    """Provides a superuser for schema management tests."""
    mock_user = User(
        sub="schema-manager-user-123",
        preferred_username="schema_manager",
        groups=["tenant-a"],
        realm_access=RealmAccess(roles=["superuser", "trading-partners:read", "trading-partners:update", "trading-partners:create"])
    )
    app.dependency_overrides[get_current_user] = lambda: mock_user
    yield
    del app.dependency_overrides[get_current_user]

@pytest_asyncio.fixture(scope="function", autouse=True)
async def clean_minio_bucket_for_api():
    """Cleans up specialized schemas after each API test."""
    yield
    # Basic cleanup: find and delete objects created in tenant-a
    prefix = "tenant-a/schemas/"
    keys_to_delete = storage_client.list_objects(prefix=prefix)
    for key in keys_to_delete:
        storage_client.s3_client.delete_object(Bucket=storage_client.bucket_name, Key=key)

async def test_list_schemas_combines_base_and_specialized(async_client: AsyncClient, mock_get_current_user):
    """Verify GET /schemas returns both base schemas and tenant-specific specialized schemas."""
    # Arrange: Upload a specialized schema for our tenant
    tenant_id = "tenant-a"
    specialized_schema_name = "test_specialized.json"
    s3_key = f"{tenant_id}/schemas/{specialized_schema_name}"
    storage_client.upload(b'{"transactionName": "Specialized"}', key=s3_key)
    
    headers = {"X-Tenant-ID": tenant_id}

    # Act
    response = await async_client.get("/api/v1/schemas", headers=headers)

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert "base_schemas" in data
    assert "specialized_schemas" in data
    assert "837.5010.X222.A1.json" in data["base_schemas"]
    assert specialized_schema_name in data["specialized_schemas"]

async def test_copy_schema_creates_specialized_version(async_client: AsyncClient, mock_get_current_user):
    """Verify POST /schemas/{name}/copy creates a new file in object storage."""
    # Arrange
    tenant_id = "tenant-a"
    base_schema_name = "837.5010.X222.A1.json"
    new_schema_name = f"copied_schema_{uuid.uuid4()}.json"
    headers = {"X-Tenant-ID": tenant_id}
    payload = {"new_name": new_schema_name}

    # Act
    response = await async_client.post(f"/api/v1/schemas/{base_schema_name}/copy", headers=headers, json=payload)

    # Assert
    assert response.status_code == 201
    assert response.json()["new_schema_name"] == new_schema_name

    # Verify the file now exists in storage
    s3_key = f"{tenant_id}/schemas/{new_schema_name}"
    downloaded_content = storage_client.download(key=s3_key)
    assert downloaded_content is not None
    assert b"HIPAA Health Care Claim: Professional" in downloaded_content

async def test_update_specialized_schema_succeeds(async_client: AsyncClient, mock_get_current_user):
    """Verify PUT /schemas/{name} can update a specialized schema."""
    # Arrange
    tenant_id = "tenant-a"
    schema_name = "updatable.json"
    s3_key = f"{tenant_id}/schemas/{schema_name}"
    original_content = {"transactionName": "Version 1", "version": "v1", "description": "d1", "structure": []}
    storage_client.upload(json.dumps(original_content).encode('utf-8'), key=s3_key)
    
    headers = {"X-Tenant-ID": tenant_id}
    updated_content = {"transactionName": "Version 2", "version": "v2", "description": "d2", "structure": []}

    # Act
    response = await async_client.put(f"/api/v1/schemas/{schema_name}", headers=headers, json=updated_content)

    # Assert
    assert response.status_code == 200
    downloaded_content = storage_client.download(key=s3_key)
    assert downloaded_content is not None
    assert json.loads(downloaded_content)["transactionName"] == "Version 2"

async def test_update_base_schema_fails(async_client: AsyncClient, mock_get_current_user):
    """Verify PUT /schemas/{name} returns 403 Forbidden when trying to edit a base schema."""
    # Arrange
    tenant_id = "tenant-a"
    base_schema_name = "837.5010.X222.A1.json"
    headers = {"X-Tenant-ID": tenant_id}
    payload = {"transactionName": "Attempted Update"}

    # Act
    response = await async_client.put(f"/api/v1/schemas/{base_schema_name}", headers=headers, json=payload)

    # Assert
    assert response.status_code == 403
    assert "Base schemas cannot be modified" in response.json()["detail"]