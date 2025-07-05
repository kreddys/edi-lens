import pytest
import httpx
import json # Import the json library for pretty-printing

from src.core.config import settings

pytestmark = pytest.mark.integration

async def get_test_user_token() -> str:
    token_url = (
        f"{settings.KEYCLOAK_URL}/realms/{settings.KEYCLOAK_REALM}"
        "/protocol/openid-connect/token"
    )

    payload = {
        "grant_type": "password",
        "client_id": "fastapi-client",
        "client_secret": settings.KEYCLOAK_CLIENT_SECRET,
        "username": "backend-test-user-1",
        "password": "backend-test-password-1",
        "scope": "openid profile email",
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(token_url, data=payload, timeout=10.0)
        
        try:
            token_data = response.json()
        except Exception:
            pytest.fail(
                f"Failed to decode JSON from Keycloak. "
                f"Status: {response.status_code}, Response: {response.text}"
            )

        response.raise_for_status()
        
        assert "access_token" in token_data
        return token_data["access_token"]


@pytest.mark.asyncio
async def test_users_me_with_live_token():
    try:
        token = await get_test_user_token()
    except httpx.RequestError as e:
        pytest.fail(f"Could not connect to Keycloak service. Is it running? Error: {e}")

    headers = {"Authorization": f"Bearer {token}"}
    backend_url = "http://backend:8000/users/me"

    async with httpx.AsyncClient() as client:
        response = await client.get(backend_url, headers=headers, timeout=10.0)

    # --- THIS IS THE DEBUGGING STEP ---
    # Log the response content before making assertions
    print("\n--- API Response ---")
    try:
        # Try to pretty-print if it's JSON
        print(json.dumps(response.json(), indent=2))
    except Exception:
        # Otherwise, print as raw text
        print(response.text)
    print("--- End API Response ---\n")

    assert response.status_code == 200, f"API call failed: {response.text}"
    
    data = response.json()
    assert data["preferred_username"] == "backend-test-user-1"
    assert data["email"] == "backendtestuser1@edilens.com"