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
async def test_partner_crud_with_live_superuser_token():
    """
    Tests the full CRUD lifecycle for trading partners using a real superuser
    token from Keycloak, ensuring permissions and logic are correct.
    """
    token = await get_user_token("superuser@edilens.com")
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": "tenant-a"
    }
    base_url = f"http://{settings.BACKEND_HOST}:8000/api/v1/trading-partners"
    partner_name = f"Integration Test Partner {uuid.uuid4()}"
    partner_id = None

    async with httpx.AsyncClient() as client:
        # 1. CREATE
        create_data = {"name": partner_name, "description": "Live test", "profiles": []}
        response = await client.post(base_url, headers=headers, json=create_data)
        assert response.status_code == 201, f"CREATE failed: {response.text}"
        partner_id = response.json()["id"]
        assert partner_id is not None

        # 2. READ (One)
        response = await client.get(f"{base_url}/{partner_id}", headers=headers)
        assert response.status_code == 200
        assert response.json()["name"] == partner_name

        # 3. UPDATE
        update_data = {"name": partner_name, "description": "Updated live", "profiles": []}
        response = await client.put(f"{base_url}/{partner_id}", headers=headers, json=update_data)
        assert response.status_code == 200
        assert response.json()["description"] == "Updated live"

        # 4. DELETE (and cleanup)
        response = await client.delete(f"{base_url}/{partner_id}", headers=headers)
        assert response.status_code == 204

        # 5. Verify Deletion
        response = await client.get(f"{base_url}/{partner_id}", headers=headers)
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_partner_creation_denied_for_viewer_with_live_token():
    """
    Verifies that a user with a valid token but insufficient permissions
    (viewer.b@edilens.com lacks 'trading-partners:create') is rejected.
    """
    # viewer.b@edilens.com is in group 'tenant-b' and has role 'tenant-viewer'
    token = await get_user_token("viewer.b@edilens.com")
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": "tenant-b" # The user is in this tenant
    }
    base_url = f"http://{settings.BACKEND_HOST}:8000/api/v1/trading-partners"
    create_data = {"name": "Unauthorized Partner", "description": "Should fail", "profiles": []}

    async with httpx.AsyncClient() as client:
        response = await client.post(base_url, headers=headers, json=create_data)
    
    # We expect a 403 Forbidden because the role 'trading-partners:create' is missing.
    assert response.status_code == 403
    # --- THIS IS THE FIX ---
    assert "Permission 'trading-partners:create' required" in response.text

@pytest.mark.asyncio
async def test_tenant_isolation_with_live_tokens():
    """
    Ensures a user from one tenant cannot access resources from another tenant.
    """
    superuser_token = await get_user_token("superuser@edilens.com")
    tenant_a_user_token = await get_user_token("admin.a@edilens.com")
    partner_name = f"Tenant B Partner {uuid.uuid4()}"
    base_url = f"http://{settings.BACKEND_HOST}:8000/api/v1/trading-partners"
    partner_id = None

    # 1. As superuser, create a resource in tenant-b
    async with httpx.AsyncClient() as client:
        headers = {"Authorization": f"Bearer {superuser_token}", "X-Tenant-ID": "tenant-b"}
        create_data = {"name": partner_name, "profiles": []}
        response = await client.post(base_url, headers=headers, json=create_data)
        assert response.status_code == 201
        partner_id = response.json()["id"]

    # 2. As a user from tenant-a, try to access the resource in tenant-b
    async with httpx.AsyncClient() as client:
        headers = {"Authorization": f"Bearer {tenant_a_user_token}", "X-Tenant-ID": "tenant-a"}
        response = await client.get(f"{base_url}/{partner_id}", headers=headers)
        # It must be "Not Found" from their perspective. A 403 would leak information.
        assert response.status_code == 404

@pytest.mark.asyncio
async def test_audit_log_with_live_token(db_session: AsyncSession):
    """
    Verifies that creating a resource with a live token creates an audit log
    with the correct user details from the token's claims.
    """
    token = await get_user_token("admin.a@edilens.com")
    claims = jwt.get_unverified_claims(token)
    partner_name = f"Audited Partner {uuid.uuid4()}"
    headers = {"Authorization": f"Bearer {token}", "X-Tenant-ID": "tenant-a"}
    base_url = f"http://{settings.BACKEND_HOST}:8000/api/v1/trading-partners"

    # 1. Create a resource via the API
    async with httpx.AsyncClient() as client:
        create_data = {"name": partner_name, "profiles": []}
        response = await client.post(base_url, headers=headers, json=create_data)
        assert response.status_code == 201
        partner_id = response.json()["id"]

    