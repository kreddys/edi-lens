import pytest
from httpx import AsyncClient

from src.main import app
from src.core.auth import User, RealmAccess, get_current_user

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]

@pytest.fixture
def mock_user_with_validation_perm():
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
    mock_user = User(
        sub="mock-no-perm-user-789",
        preferred_username="no-validator",
        groups=["tenant-a"],
        realm_access=RealmAccess(roles=["some-other-role"])
    )
    app.dependency_overrides[get_current_user] = lambda: mock_user
    yield
    del app.dependency_overrides[get_current_user]

async def test_validate_endpoint_unauthenticated(async_client: AsyncClient, valid_837p_edi_string: str):
    request_data = {"edi_data": valid_837p_edi_string}
    headers = {"X-Tenant-ID": "tenant-a", "Authorization": "Bearer invalidtoken"}
    response = await async_client.post("/api/v1/validate", json=request_data, headers=headers)
    assert response.status_code == 401

async def test_validate_endpoint_lacks_permission(async_client: AsyncClient, mock_user_without_validation_perm, valid_837p_edi_string: str):
    request_data = {"edi_data": valid_837p_edi_string}
    headers = {"X-Tenant-ID": "tenant-a"}
    response = await async_client.post("/api/v1/validate", json=request_data, headers=headers)
    assert response.status_code == 403
    assert "Permission 'validation:run' required" in response.json()["detail"]

async def test_validate_endpoint_success(async_client: AsyncClient, mock_user_with_validation_perm, valid_837p_edi_string: str):
    """Tests a successful validation where no TA1 is requested."""
    request_data = {"edi_data": valid_837p_edi_string}
    headers = {"X-Tenant-ID": "tenant-a"}
    response = await async_client.post("/api/v1/validate", json=request_data, headers=headers)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "Validation Complete"
    assert data["ta1_acknowledgement"] is None

async def test_validate_endpoint_returns_accepted_ta1_when_requested(
    async_client: AsyncClient, mock_user_with_validation_perm, edi_with_ack_requested: str
):
    """
    Tests that a valid file with ISA14='1' correctly receives an 'Accepted' TA1.
    """
    request_data = {"edi_data": edi_with_ack_requested}
    headers = {"X-Tenant-ID": "tenant-a"}
    response = await async_client.post("/api/v1/validate", json=request_data, headers=headers)
    
    assert response.status_code == 200, response.text
    data = response.json()
    
    assert data["status"] == "Validation Complete"
    assert data["ta1_acknowledgement"] is not None
    assert data["ta1_acknowledgement"].startswith("TA1*000000001")
    assert data["ta1_acknowledgement"].endswith("*A*000")

async def test_validate_endpoint_returns_rejected_ta1_on_isa_error(
    async_client: AsyncClient, mock_user_with_validation_perm, edi_with_isa_error: str
):
    """
    Tests that a file with an ISA/IEA mismatch error correctly receives a 'Rejected' TA1.
    """
    request_data = {"edi_data": edi_with_isa_error}
    headers = {"X-Tenant-ID": "tenant-a"}
    response = await async_client.post("/api/v1/validate", json=request_data, headers=headers)

    assert response.status_code == 200, response.text
    data = response.json()
    
    assert data["status"] == "Rejected at Interchange Level"
    assert data["ta1_acknowledgement"] is not None
    assert data["ta1_acknowledgement"].startswith("TA1*000000001")
    assert data["ta1_acknowledgement"].endswith("*R*001")

async def test_validate_endpoint_parsing_error(async_client: AsyncClient, mock_user_with_validation_perm):
    """
    Tests that a request with invalid EDI data that fails pre-validation
    returns a 400 Bad Request error.
    """
    request_data = {"edi_data": "this is not valid edi~"}
    headers = {"X-Tenant-ID": "tenant-a"}
    response = await async_client.post("/api/v1/validate", json=request_data, headers=headers)
    
    assert response.status_code == 400
    assert "Could not determine implementation guide version" in response.json()["detail"]