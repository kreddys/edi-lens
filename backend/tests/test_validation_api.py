import pytest
from httpx import AsyncClient

from .test_edi_parser import VALID_EDI_STRING
# --- ADD IMPORTS ---
from src.core.auth import User, RealmAccess

pytestmark = pytest.mark.asyncio

# --- ADD THIS FIXTURE TO MOCK THE USER ---
@pytest.fixture
def mock_get_current_user():
    """Mocks the get_current_user dependency for the validation endpoint."""
    from src.main import app
    from src.core.auth import get_current_user
    
    mock_user = User(
        sub="mock-validation-user",
        preferred_username="validator",
        realm_access=RealmAccess(roles=["validator_role"])
    )
    
    async def _mock():
        return mock_user

    app.dependency_overrides[get_current_user] = _mock
    yield
    del app.dependency_overrides[get_current_user]


async def test_validate_endpoint_unauthenticated(async_client: AsyncClient):
    """Tests that an unauthenticated request is rejected."""
    request_data = {"edi_data": VALID_EDI_STRING}
    response = await async_client.post("/api/v1/validate/", json=request_data)
    # The default response for a missing dependency is 403, not 401, when using HTTPBearer
    assert response.status_code == 403 


async def test_validate_endpoint_success(async_client: AsyncClient, mock_get_current_user):
    """Tests a successful validation request from an authenticated user."""
    request_data = {
        "edi_data": VALID_EDI_STRING,
        # The implementation_guide is no longer in the request body in our schemas
        # "implementation_guide": "837.5010.X222.A1"
    }
    response = await async_client.post("/api/v1/validate/", json=request_data)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "Parsed Successfully"
    assert len(data["parsed_segments"]) == 5


async def test_validate_endpoint_parsing_error(async_client: AsyncClient, mock_get_current_user):
    """Tests that a request with invalid EDI data returns a 400 error."""
    request_data = {
        "edi_data": "this is not valid edi~",
    }
    response = await async_client.post("/api/v1/validate/", json=request_data)
    assert response.status_code == 400
    assert "No valid segments found" in response.json()["detail"]