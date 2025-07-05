import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwt

from src.core.auth import get_current_user
from tests.utils_for_test import forge_jwt, TEST_PUBLIC_KEY

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def mock_get_public_key(mocker):
    """Mocks the call to fetch the public key from Keycloak."""
    from jose import jwk
    public_jwk_dict = jwk.construct(TEST_PUBLIC_KEY, algorithm="RS256").to_dict()
    mocker.patch(
        "src.core.auth.get_keycloak_public_key",
        return_value=public_jwk_dict,
    )


async def test_get_current_user_success():
    token = forge_jwt(payload_override={})
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    user = await get_current_user(creds=creds)

    assert user.sub == "test-user-id"
    assert user.preferred_username == "testuser"
    assert "test_role" in user.realm_access.roles
    assert "tenant-a" in user.groups


async def test_get_current_user_expired_token_raises_exception():
    token = forge_jwt(payload_override={}, expires_in=-10)
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(creds=creds)

    assert exc_info.value.status_code == 401
    assert "Could not validate credentials" in exc_info.value.detail


async def test_get_current_user_invalid_audience_raises_exception():
    token = forge_jwt(payload_override={}, client_id="some-other-service")
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(creds=creds)

    assert exc_info.value.status_code == 401


async def test_get_current_user_invalid_signature_raises_exception():
    malicious_private_key = rsa.generate_private_key(
        public_exponent=65537, key_size=2048
    ).private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    legit_token = forge_jwt(payload_override={})
    payload = jwt.get_unverified_claims(legit_token)
    tampered_token = jwt.encode(payload, malicious_private_key, algorithm="RS256")
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=tampered_token)

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(creds=creds)

    assert exc_info.value.status_code == 401


async def test_get_current_user_missing_sub_claim_raises_exception():
    token = forge_jwt(payload_override={"sub": None})
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(creds=creds)

    assert exc_info.value.status_code == 401