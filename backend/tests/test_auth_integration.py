import pytest
import httpx
import json
from jose import jwt

from src.core.config import settings

pytestmark = pytest.mark.integration


async def get_test_user_token() -> str:
    """
    Fetches a valid access token from the live Keycloak service using
    the credentials of a user created by our setup script.
    """
    token_url = (
        f"{settings.KEYCLOAK_URL}/realms/{settings.KEYCLOAK_REALM}"
        "/protocol/openid-connect/token"
    )

    payload = {
        "grant_type": "password",
        "client_id": settings.KEYCLOAK_BACKEND_CLIENT_ID,
        "client_secret": settings.KEYCLOAK_BACKEND_CLIENT_SECRET,
        "username": "superuser@edilens.com",
        "password": "password",
        "scope": "openid profile email",
        # --- THIS IS THE FIX ---
        # Explicitly request our client_id as the audience. This ensures the
        # 'aud' claim in the resulting token is 'edi-lens-client'.
        "audience": settings.KEYCLOAK_BACKEND_CLIENT_ID,
    }
    
    async with httpx.AsyncClient() as client:
        # The 'audience' parameter must be sent in the request body, not as a query param for token endpoint.
        response = await client.post(token_url, data=payload, timeout=10.0)
        
        try:
            token_data = response.json()
        except Exception:
            pytest.fail(
                f"Failed to decode JSON from Keycloak. "
                f"Status: {response.status_code}, Response: {response.text}"
            )

        response.raise_for_status()
        
        access_token = token_data.get("access_token")
        assert access_token, "Access token not found in Keycloak response"

        try:
            claims = jwt.get_unverified_claims(access_token)
            print("\n--- Keycloak Token Claims (Decoded) ---")
            print(json.dumps(claims, indent=2))
            print("---------------------------------------\n")
        except Exception as e:
            print(f"Could not decode token for debugging: {e}")

        return access_token


@pytest.mark.asyncio
async def test_users_me_with_live_token():
    try:
        token = await get_test_user_token()
    except httpx.RequestError as e:
        pytest.fail(f"Could not connect to Keycloak service. Is it running? Error: {e}")

    headers = {"Authorization": f"Bearer {token}"}
    
    backend_url = f"http://{settings.BACKEND_HOST}:8000/users/me"

    print("\n--- Request Headers Sent to API ---")
    print(f"Authorization: Bearer [token of length {len(token)}]")
    print("-----------------------------------\n")

    async with httpx.AsyncClient() as client:
        response = await client.get(backend_url, headers=headers, timeout=10.0)

    print("\n--- API Response ---")
    try:
        print(json.dumps(response.json(), indent=2))
    except Exception:
        print(response.text)
    print("--- End API Response ---\n")

    assert response.status_code == 200, f"API call failed: {response.text}"
    
    data = response.json()
    assert data["preferred_username"] == "superuser@edilens.com"
    assert data["email"] == "superuser@edilens.com"
    assert "superuser" in data["realm_access"]["roles"]
    assert "tenant-a" in data["groups"]