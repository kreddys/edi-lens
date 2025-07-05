import pytest
from httpx import AsyncClient

from .test_edi_parser import VALID_EDI_STRING
from src.core.auth import User, RealmAccess

pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_get_current_user():
    """
    Mocks the get_current_user dependency for the validation endpoint.
    Provides a user with the 'validation:run' permission and tenant membership.
    """
    from src.main import app
    from src.core.auth import get_current_user
    
    mock_user = User(
        sub="mock-validator-user-456",
        preferred_username="validator",
        groups=["tenant-a"],
        realm_access=RealmAccess(roles=["validation:run"])
    )
    
    async def _mock():
        return mock_user

    app.dependency_overrides[get_current_user] = _mock
    yield
    del app.dependency_overrides[get_current_user]


async def test_validate_endpoint_unauthenticated(async_client: AsyncClient):
    """
    Tests that a request without an Authorization header is rejected.
    """
    request_data = {"edi_data": VALID_EDI_STRING}
    # We still need to send the header, but the auth dependency will fail first.
    headers = {"X-Tenant-ID": "tenant-a"}
    response = await async_client.post(
        "/api/v1/validate/", 
        json=request_data,
        headers=headers
    )

    # --- THIS IS THE FIX ---
    # FastAPI's Bearer scheme fails before checking the header, returning 403.
    assert response.status_code == 403


async def test_validate_endpoint_success(async_client: AsyncClient, mock_get_current_user):
    """Tests a successful validation request from an authenticated user."""
    request_data = {"edi_data": VALID_EDI_STRING}
    
    headers = {"X-Tenant-ID": "tenant-a"}

    response = await async_client.post(
        "/api/v1/validate/", 
        json=request_data,
        headers=headers
    )
    
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "Parsed Successfully"
    assert len(data["parsed_segments"]) == 5


async def test_validate_endpoint_parsing_error(async_client: AsyncClient, mock_get_current_user):
    """Tests that a request with invalid EDI data returns a 400 error."""
    request_data = {"edi_data": "this is not valid edi~"}
    
    headers = {"X-Tenant-ID": "tenant-a"}

    response = await async_client.post(
        "/api/v1/validate/", 
        json=request_data,
        headers=headers
    )

    assert response.status_code == 400, response.text
    assert "No valid segments found" in response.json()["detail"]