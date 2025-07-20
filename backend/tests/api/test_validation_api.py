# FILE: backend/tests/api/test_validation_api.py
import pytest
from httpx import AsyncClient

from src.main import app
# --- THIS IS THE FIX: Use a more complete EDI string that matches the new schema ---
from tests.core.test_edi_parser_837p import SIMPLE_837P_EDI as VALID_EDI_STRING
from src.core.auth import User, RealmAccess, get_current_user

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]

@pytest.fixture
def mock_user_with_validation_perm():
    # ... (fixture is unchanged)
    mock_user = User(
        sub="mock-validator-user-456",
        preferred_username="validator",
        groups=["tenant-a"],
        realm_access=RealmAccess(roles=["validation:run"])
    )
    app.dependency_overrides[get_current_user] = lambda: mock_user
    yield
    del app.dependency_overrides[get_current_user]

@pytest.fixture
def mock_user_without_validation_perm():
    # ... (fixture is unchanged)
    mock_user = User(
        sub="mock-no-perm-user-789",
        preferred_username="no-validator",
        groups=["tenant-a"],
        realm_access=RealmAccess(roles=["some-other-role"])
    )
    app.dependency_overrides[get_current_user] = lambda: mock_user
    yield
    del app.dependency_overrides[get_current_user]

async def test_validate_endpoint_unauthenticated(async_client: AsyncClient):
    # ... (test is unchanged)
    request_data = {"edi_data": VALID_EDI_STRING}
    headers = {"X-Tenant-ID": "tenant-a", "Authorization": "Bearer invalidtoken"}
    response = await async_client.post("/api/v1/validate", json=request_data, headers=headers)
    assert response.status_code == 401

async def test_validate_endpoint_lacks_permission(async_client: AsyncClient, mock_user_without_validation_perm):
    # ... (test is unchanged)
    request_data = {"edi_data": VALID_EDI_STRING}
    headers = {"X-Tenant-ID": "tenant-a"}
    response = await async_client.post("/api/v1/validate", json=request_data, headers=headers)
    assert response.status_code == 403
    assert "Permission 'validation:run' required" in response.json()["detail"]

async def test_validate_endpoint_success(async_client: AsyncClient, mock_user_with_validation_perm):
    """Tests a successful validation request from an authorized user."""
    request_data = {"edi_data": VALID_EDI_STRING}
    headers = {"X-Tenant-ID": "tenant-a"}
    response = await async_client.post("/api/v1/validate", json=request_data, headers=headers)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "Parsed Successfully"

async def test_validate_endpoint_parsing_error(async_client: AsyncClient, mock_user_with_validation_perm):
    """
    Tests that a request with invalid EDI data returns a 400 error.
    """
    request_data = {"edi_data": "this is not valid edi~"}
    headers = {"X-Tenant-ID": "tenant-a"}
    response = await async_client.post("/api/v1/validate", json=request_data, headers=headers)
    assert response.status_code == 400
    assert "Could not determine implementation guide version" in response.json()["detail"]