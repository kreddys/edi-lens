# FILE: backend/tests/api/test_api_workflows.py

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from src.main import app
from src.core.auth import User, RealmAccess, get_current_user
from src.models import TradingPartner, PartnerProfile
from src.core.schema_manager import schema_manager
from pathlib import Path
from src.core.config import settings
import json
import uuid

from src.core.storage import storage_client

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]

@pytest_asyncio.fixture(autouse=True)
async def setup_for_api_tests():
    """Ensures the schema manager is loaded before any test in this file runs."""
    if not schema_manager.list_base_schemas():
        schema_manager.load_base_schemas(Path(settings.EDI_SCHEMA_DIRECTORY))
    yield

@pytest.fixture
def api_user():
    """Provides a standard user with all necessary API permissions."""
    return User(
        sub="mock-api-user-123",
        preferred_username="api-tester",
        groups=["tenant-a"],
        realm_access=RealmAccess(roles=[
            "validation:run", 
            "trading-partners:create",
            "trading-partners:read",
            "trading-partners:update",
            "trading-partners:delete"
        ])
    )

@pytest.fixture
def mock_get_current_user(api_user):
    app.dependency_overrides[get_current_user] = lambda: api_user
    yield
    del app.dependency_overrides[get_current_user]

@pytest_asyncio.fixture
async def setup_partner_and_profile(db_session: AsyncSession) -> PartnerProfile:
    """Creates a partner and profile in the DB for tests to use."""
    partner = TradingPartner(tenant_id="tenant-a", name="API Test Partner")
    profile = PartnerProfile(
        partner=partner,
        tenant_id="tenant-a",
        name="API Test Profile",
        validation_schema_name="837.5010.X222.A1.json",
    )
    db_session.add(partner)
    await db_session.commit()
    return profile

# === Validation API Tests ===
class TestValidationApi:
    async def test_validate_endpoint_success(self, async_client: AsyncClient, mock_get_current_user, valid_837p_edi_string: str, setup_partner_and_profile):
        request_data = {
            "edi_data": valid_837p_edi_string,
            "profile_name": "API Test Profile"
        }
        headers = {"X-Tenant-ID": "tenant-a"}
        response = await async_client.post("/api/v1/validate", json=request_data, headers=headers)
        
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["valid"] is True
        assert data["matched_profile"] == "API Test Profile"

# === Trading Partner API Tests ===
class TestTradingPartnerApi:
    async def test_update_trading_partner(self, async_client: AsyncClient, mock_get_current_user, setup_partner_and_profile):
        partner_id = setup_partner_and_profile.partner_id
        profile_id = setup_partner_and_profile.id

        update_data = {
            "name": "API Test Partner Updated",
            "sftp_enabled": True,
            "sftp_username": "new-sftp-user",
            "profiles": [
                {
                    "id": profile_id,
                    "name": "API Test Profile Updated",
                    "validation_schema_name": "837.5010.X222.A1.json",
                    "file_name_patterns": '["*.edi"]'
                }
            ]
        }
        headers = {"X-Tenant-ID": "tenant-a"}
        response = await async_client.put(f"/api/v1/trading-partners/{partner_id}", json=update_data, headers=headers)

        assert response.status_code == 200, response.text
        data = response.json()
        assert data["name"] == "API Test Partner Updated"
        assert data["sftp_enabled"] is True
        assert data["profiles"][0]["name"] == "API Test Profile Updated"
        assert data["profiles"][0]["file_name_patterns"] == '["*.edi"]'

# === Schema API Tests ===
class TestSchemaApi:
    async def test_list_schemas_combines_base_and_specialized(self, async_client: AsyncClient, mock_get_current_user):
        # This test remains the same but now benefits from the autouse fixture
        tenant_id = "tenant-a"
        specialized_schema_name = "test_specialized.json"
        s3_key = f"{tenant_id}/schemas/{specialized_schema_name}"
        storage_client.upload(b'{"transactionName": "Specialized", "version": "v1", "description": "d1", "structure": []}', key=s3_key)
        
        headers = {"X-Tenant-ID": tenant_id}
        response = await async_client.get("/api/v1/schemas", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert "837.5010.X222.A1.json" in data["base_schemas"]
        assert specialized_schema_name in data["specialized_schemas"]