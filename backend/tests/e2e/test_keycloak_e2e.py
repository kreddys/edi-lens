import pytest
import httpx
import json
import uuid
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from jose import jwt

from src.core.config import settings
from src.models.audit_log import AuditLog
from tests.e2e.e2e_utils import get_user_token

pytestmark = [pytest.mark.asyncio, pytest.mark.e2e]

# --- Test Cases ---

@pytest.mark.asyncio
async def test_users_me_with_live_token():
    """Verifies that the basic /users/me endpoint works with a live token."""
    token = await get_user_token("superuser@edilens.com")
    headers = {"Authorization": f"Bearer {token}"}
    backend_url = f"http://{settings.BACKEND_HOST}:8000/api/v1/users/me"

    async with httpx.AsyncClient() as client:
        response = await client.get(backend_url, headers=headers)
    
    assert response.status_code == 200, f"API call failed: {response.text}"
    data = response.json()
    assert data["preferred_username"] == "superuser@edilens.com"


@pytest.mark.asyncio
async def test_schema_management_with_live_superuser_token():
    """
    Tests schema management using a real superuser token from Keycloak,
    ensuring permissions and logic are correct.
    """
    token = await get_user_token("superuser@edilens.com")
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": "tenant-a"
    }
    
    # Test schema listing
    list_url = f"http://{settings.BACKEND_HOST}:8000/api/v1/schemas"
    async with httpx.AsyncClient() as client:
        response = await client.get(list_url, headers=headers)
        assert response.status_code == 200, f"Schema listing failed: {response.text}"
        
        result = response.json()
        assert "base_schemas" in result
        assert "specialized_schemas" in result
        assert "837.5010.X222.A1.json" in result["base_schemas"]
        
        # Test schema retrieval
        schema_url = f"http://{settings.BACKEND_HOST}:8000/api/v1/schemas/837.5010.X222.A1.json"
        response = await client.get(schema_url, headers=headers)
        assert response.status_code == 200, f"Schema retrieval failed: {response.text}"
        
        schema_data = response.json()
        assert "transactionName" in schema_data
        assert "version" in schema_data


@pytest.mark.asyncio
async def test_schema_access_denied_for_viewer_with_live_token():
    """
    Verifies that a user with a valid token but insufficient permissions
    (viewer.b@edilens.com lacks 'schemas:create') is rejected.
    """
    # viewer.b@edilens.com is in group 'tenant-b' and has role 'tenant-viewer'
    token = await get_user_token("viewer.b@edilens.com")
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": "tenant-b" # The user is in this tenant
    }
    base_url = f"http://{settings.BACKEND_HOST}:8000/api/v1/schemas/837.5010.X222.A1.json/copy"
    create_data = {"new_name": "unauthorized_schema.json"}

    async with httpx.AsyncClient() as client:
        response = await client.post(base_url, headers=headers, json=create_data)
    
    # We expect a 403 Forbidden because the role 'schemas:create' is missing.
    assert response.status_code == 403
    assert "Permission 'schemas:create' required" in response.text

@pytest.mark.asyncio
async def test_tenant_isolation_with_live_tokens():
    """
    Ensures a user from one tenant cannot access specialized schemas from another tenant.
    """
    superuser_token = await get_user_token("superuser@edilens.com")
    tenant_a_user_token = await get_user_token("admin.a@edilens.com")
    schema_name = f"tenant_b_schema_{uuid.uuid4()}.json"
    
    # 1. As superuser, create a specialized schema in tenant-b
    async with httpx.AsyncClient() as client:
        headers = {"Authorization": f"Bearer {superuser_token}", "X-Tenant-ID": "tenant-b"}
        base_url = f"http://{settings.BACKEND_HOST}:8000/api/v1/schemas/837.5010.X222.A1.json/copy"
        create_data = {"new_name": schema_name}
        response = await client.post(base_url, headers=headers, json=create_data)
        assert response.status_code == 201

    # 2. As a user from tenant-a, try to access schemas (should not see tenant-b's schema)
    async with httpx.AsyncClient() as client:
        headers = {"Authorization": f"Bearer {tenant_a_user_token}", "X-Tenant-ID": "tenant-a"}
        list_url = f"http://{settings.BACKEND_HOST}:8000/api/v1/schemas"
        response = await client.get(list_url, headers=headers)
        assert response.status_code == 200
        
        # The tenant-a user should not see the tenant-b schema
        data = response.json()
        assert schema_name not in data.get("specialized_schemas", [])

@pytest.mark.asyncio 
async def test_audit_log_with_live_token(db_session: AsyncSession):
    """
    Verifies that creating a schema with a live token creates an audit log
    with the correct user details from the token's claims.
    """
    token = await get_user_token("admin.a@edilens.com")
    claims = jwt.get_unverified_claims(token)
    headers = {"Authorization": f"Bearer {token}", "X-Tenant-ID": "tenant-a"}
    
    schema_name = f"audit_test_schema_{uuid.uuid4()}.json"
    base_url = f"http://{settings.BACKEND_HOST}:8000/api/v1/schemas/837.5010.X222.A1.json/copy"

    # 1. Create a schema via the API (this should create audit logs)
    async with httpx.AsyncClient() as client:
        create_data = {"new_name": schema_name}
        response = await client.post(base_url, headers=headers, json=create_data)
        assert response.status_code == 201

    # 2. Check that audit log was created with correct user information
    result = await db_session.execute(
        select(AuditLog).order_by(AuditLog.timestamp_utc.desc()).limit(1)
    )
    audit_log = result.scalar_one_or_none()
    
    # Verify the audit log contains the expected user information from the JWT token
    assert audit_log is not None, "No audit log was created"
    assert audit_log.user_id == claims["sub"]
    assert audit_log.username == claims["preferred_username"]
    assert audit_log.tenant_id == "tenant-a"