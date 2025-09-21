import httpx
import json
import pytest

from src.core.config import settings

async def get_user_token(username: str, password: str = "password") -> str:
    """
    Fetches a valid access token from the live Keycloak service.
    This is a shared helper for all E2E tests.
    """
    token_url = f"{settings.KEYCLOAK_URL}/realms/{settings.KEYCLOAK_REALM}/protocol/openid-connect/token"
    payload = {
        "grant_type": "password",
        "client_id": settings.KEYCLOAK_BACKEND_CLIENT_ID,
        "client_secret": settings.KEYCLOAK_BACKEND_CLIENT_SECRET,
        "username": username,
        "password": password,
        "audience": settings.KEYCLOAK_BACKEND_CLIENT_ID,
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(token_url, data=payload, timeout=10.0)
            response.raise_for_status()
            token_data = response.json()
            return token_data["access_token"]
        except (httpx.RequestError, KeyError, json.JSONDecodeError) as e:
            pytest.fail(f"Could not get token for user {username} from Keycloak. Is it running and configured? Error: {e}")