import pytest
import httpx

from src.core.config import settings

# Mark all tests in this file as 'integration' tests
pytestmark = pytest.mark.integration


async def get_test_user_token() -> str:
    """
    Gets a real access token from the running Keycloak instance
    using the Direct Access Grant (password) flow.
    """
    # --- THIS IS THE FIX ---
    # Use the internal KEYCLOAK_URL for container-to-container communication,
    # not the host-facing KEYCLOAK_BROWSER_URL.
    token_url = (
        f"{settings.KEYCLOAK_URL}/realms/{settings.KEYCLOAK_REALM}"
        "/protocol/openid-connect/token"
    )

    payload = {
        "grant_type": "password",
        "client_id": settings.KEYCLOAK_CLIENT_ID,
        "client_secret": settings.KEYCLOAK_CLIENT_SECRET,
        "username": "testuser",
        "password": "test",
        "scope": "openid",
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(token_url, data=payload)
        response.raise_for_status()
        
        token_data = response.json()
        assert "access_token" in token_data
        return token_data["access_token"]


@pytest.mark.asyncio
async def test_users_me_with_live_token():
    """
    Tests the protected /users/me endpoint using a real token from Keycloak.
    This test requires the full Docker stack to be running.
    """
    try:
        token = await get_test_user_token()
    except httpx.RequestError as e:
        pytest.fail(f"Could not connect to Keycloak service. Is it running? Error: {e}")

    # --- THIS IS ALSO A FIX ---
    # When testing from within the Docker network, we must use the service name 'backend',
    # not 'localhost'.
    headers = {"Authorization": f"Bearer {token}"}
    backend_url = "http://backend:8000/users/me"

    async with httpx.AsyncClient() as client:
        response = await client.get(backend_url, headers=headers)

    assert response.status_code == 200, f"API call failed: {response.text}"
    
    data = response.json()
    assert data["username"] == "testuser"
    assert "admin" in data["realm_access"]["roles"]