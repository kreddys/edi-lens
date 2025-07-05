import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from src.core.auth import get_current_user
from tests.utils_for_test import forge_jwt, TEST_PUBLIC_KEY

pytestmark = pytest.mark.asyncio

@pytest.fixture(autouse=True)
def mock_get_public_key(mocker):
    from jose import jwk
    public_jwk_dict = jwk.construct(TEST_PUBLIC_KEY, algorithm="RS256").to_dict()
    mocker.patch(
        "src.core.auth.get_keycloak_public_key",
        return_value=public_jwk_dict,
    )

async def test_get_current_user_success():
    """
    Tests successful validation of a perfectly valid token.
    """
    token = forge_jwt(payload_override={})
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    user = await get_current_user(creds=creds)

    # --- THIS IS THE FIX ---
    # Assert using the correct attribute names from the Pydantic model
    assert user.sub == "test-user-id"
    assert user.preferred_username == "testuser"
    assert user.given_name == "Test"
    assert user.family_name == "User"
    assert "test_role" in user.realm_access.roles

# ... (the rest of the file is correct and does not need changes,
#      as it only checks for exceptions, not attribute values) ...

async def test_get_current_user_expired_token_raises_exception():
    """
    Tests that a token with an expiration time in the past is rejected.
    """
    # Forge a token that expired 10 seconds ago.
    token = forge_jwt(payload_override={}, expires_in=-10)
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    # Use pytest.raises to assert that the correct exception is thrown.
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(creds=creds)

    # Assert details about the exception.
    assert exc_info.value.status_code == 401
    assert "Could not validate credentials" in exc_info.value.detail


async def test_get_current_user_invalid_audience_raises_exception():
    """
    Tests that a token intended for a different service (audience) is rejected.
    """
    # Forge a token with an 'aud' claim that won't match our settings.
    token = forge_jwt(payload_override={}, client_id="some-other-service")
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(creds=creds)

    assert exc_info.value.status_code == 401


async def test_get_current_user_invalid_signature_raises_exception():
    """
    Tests that a token signed with a different private key is rejected.
    This simulates a forged token from a malicious source.
    """
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from jose import jwt

    # Create a completely separate, "malicious" private key.
    malicious_private_key = rsa.generate_private_key(
        public_exponent=65537, key_size=2048
    ).private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    # Get the payload from a normally forged token.
    legit_token = forge_jwt(payload_override={})
    payload = jwt.get_unverified_claims(legit_token)

    # Sign the same payload with the *malicious* key.
    tampered_token = jwt.encode(payload, malicious_private_key, algorithm="RS256")
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=tampered_token)

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(creds=creds)

    assert exc_info.value.status_code == 401


async def test_get_current_user_missing_sub_claim_raises_exception():
    """
    Tests that a token without the required 'sub' (subject ID) claim is rejected.
    """
    # Forge a token, but override the 'sub' claim to be None.
    # Our forging helper will need to handle removing the key.
    token = forge_jwt(payload_override={"sub": None})
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(creds=creds)

    # This fails because the Pydantic model `User` will fail validation,
    # leading to the generic 401 error in our try/except block.
    assert exc_info.value.status_code == 401