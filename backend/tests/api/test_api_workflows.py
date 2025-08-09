# FILE: backend/tests/api/test_validation_api.py

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession
from src.main import app
from src.core.auth import User, RealmAccess, get_current_user
from src.models import TradingPartner, PartnerProfile

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]

@pytest.fixture
def mock_user_with_validation_perm():
    """Provides a standard user with validation and partner creation permissions."""
    mock_user = User(
        sub="mock-validator-user-456",
        preferred_username="validator",
        groups=["tenant-a"],
        realm_access=RealmAccess(roles=["validation:run", "trading-partners:create"])
    )
    app.dependency_overrides[get_current_user] = lambda: mock_user
    yield
    del app.dependency_overrides[get_current_user]

async def create_test_profile_via_api(headers: dict) -> str:
    """Helper function to create a trading partner and profile using the API."""
    profile_name = "API E2E Test Profile"
    partner_data = {
        "name": "API E2E Validation Partner",
        "profiles": [{
            "name": profile_name,
            "implementation_guide": "837P",
            "generate_ta1": True,
            "validation_schema_name": "837.5010.X222.A1.json"
        }]
    }
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/trading-partners", json=partner_data, headers=headers)
        assert response.status_code == 201, f"API setup failed: Could not create test profile. Response: {response.text}"
    return profile_name

async def test_validate_endpoint_missing_profile_name(async_client: AsyncClient, mock_user_with_validation_perm, valid_837p_edi_string: str):
    """Tests that a 422 Unprocessable Entity error is returned if profile_name is missing."""
    request_data = {"edi_data": valid_837p_edi_string}
    headers = {"X-Tenant-ID": "tenant-a"}
    response = await async_client.post("/api/v1/validate", json=request_data, headers=headers)
    assert response.status_code == 422

async def test_validate_endpoint_invalid_profile_name(async_client: AsyncClient, mock_user_with_validation_perm, valid_837p_edi_string: str):
    """
    Tests that a 400 error is returned for a profile that doesn't exist.
    This test runs against a clean DB and ensures the error message is correct.
    """
    request_data = {
        "edi_data": valid_837p_edi_string,
        "profile_name": "non-existent-profile"
    }
    headers = {"X-Tenant-ID": "tenant-a"}
    response = await async_client.post("/api/v1/validate", json=request_data, headers=headers)
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "Profile 'non-existent-profile' not found" in detail
    # --- THIS IS THE FIX ---
    # With the service change, the error message will end with ": " for an empty list.
    assert "Available profiles: " in detail
    # --- END OF FIX ---

async def test_validate_endpoint_success_with_explicit_profile(async_client: AsyncClient, mock_user_with_validation_perm, valid_837p_edi_string: str):
    """
    Tests a successful validation by first creating the profile via API,
    then using it for validation in the same test.
    """
    headers = {"X-Tenant-ID": "tenant-a"}
    
    # 1. SETUP: Create the profile needed for this test via the API helper.
    profile_name = await create_test_profile_via_api(headers)
    
    # 2. ACT: Run the validation using the newly created profile
    request_data = {
        "edi_data": valid_837p_edi_string,
        "profile_name": profile_name
    }
    response = await async_client.post("/api/v1/validate", json=request_data, headers=headers)
    
    # 3. ASSERT: Verify the validation was successful
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["valid"] is True
    assert data["status"] == "Validation Complete"
    assert data["matched_profile"] == profile_name
    assert data["detection_method"] == "manual"