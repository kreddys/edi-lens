# backend/tests/core/test_auth_logic.py
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwt

from src.core.auth import get_current_user, AuthContext, ServiceContext, User, RealmAccess
from tests.utils.jwt_forge import forge_jwt, TEST_PUBLIC_KEY # Updated import path

pytestmark = [pytest.mark.asyncio, pytest.mark.unit]

def test_auth_context():
    """Test the AuthContext class methods."""
    user = User(
        sub="test_user",
        realm_access=RealmAccess(roles=["test_role"]),
        groups=["tenant-a", "tenant-b"],
    )
    auth_context = AuthContext(user, "tenant-a")

    assert auth_context.has_permission("test_role") is True
    assert auth_context.has_permission("superuser") is False
    assert auth_context.has_permission("other_role") is False
    assert auth_context.is_member_of("tenant-a") is True
    assert auth_context.is_member_of("tenant-c") is False
    assert auth_context.has_tenant_access("tenant-a") is True

def test_service_context():
    """Test the ServiceContext class methods."""
    service_context = ServiceContext("test-service", ["tenant-a"])

    # Test new EDI processing permissions
    assert service_context.has_permission("edi:process") is True
    assert service_context.has_permission("edi:validate") is True
    assert service_context.has_permission("edi:generate-acknowledgments") is True
    assert service_context.has_permission("validation:run") is True
    assert service_context.has_permission("schemas:read") is True
    assert service_context.has_permission("other:permission") is False
    assert service_context.has_tenant_access("tenant-a") is True
    assert service_context.has_tenant_access("tenant-b") is False

@pytest.fixture(autouse=True)
def mock_get_public_key(mocker):
    from jose import jwk
    public_jwk_dict = jwk.construct(TEST_PUBLIC_KEY, algorithm="RS256").to_dict()
    mocker.patch("src.core.auth.get_keycloak_public_key", return_value=public_jwk_dict)

async def test_get_current_user_success():
    token = forge_jwt(payload_override={})
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    user = await get_current_user(creds=creds)
    assert user.sub == "test-user-id"

async def test_get_current_user_expired_token_raises_exception():
    token = forge_jwt(payload_override={}, expires_in=-10)
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    with pytest.raises(HTTPException):
        await get_current_user(creds=creds)

async def test_get_current_user_invalid_audience_raises_exception():
    token = forge_jwt(payload_override={}, client_id="some-other-service")
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(creds=creds)

    assert exc_info.value.status_code == 401

from src.core.auth import require_permission

@pytest.mark.asyncio
async def test_require_permission_success():
    """Test that a user with correct permissions and tenant access is granted access."""
    user = User(
        sub="test_user",
        realm_access=RealmAccess(roles=["test:read"]),
        groups=["tenant-a"],
    )
    dependency = require_permission("test:read")
    auth_context = await dependency(x_tenant_id="tenant-a", user=user)
    assert auth_context.user_id == "test_user"

@pytest.mark.asyncio
async def test_require_permission_wrong_tenant():
    """Test that a user with correct permissions but wrong tenant is denied access."""
    user = User(
        sub="test_user",
        realm_access=RealmAccess(roles=["test:read"]),
        groups=["tenant-b"],
    )
    dependency = require_permission("test:read")
    with pytest.raises(HTTPException) as exc_info:
        await dependency(x_tenant_id="tenant-a", user=user)
    assert exc_info.value.status_code == 403

@pytest.mark.asyncio
async def test_require_permission_wrong_permission():
    """Test that a user with wrong permissions is denied access."""
    user = User(
        sub="test_user",
        realm_access=RealmAccess(roles=["test:write"]),
        groups=["tenant-a"],
    )
    dependency = require_permission("test:read")
    with pytest.raises(HTTPException) as exc_info:
        await dependency(x_tenant_id="tenant-a", user=user)
    assert exc_info.value.status_code == 403

@pytest.mark.asyncio
async def test_require_permission_superuser():
    """Test that a superuser is granted access regardless of tenant."""
    user = User(
        sub="superuser",
        realm_access=RealmAccess(roles=["superuser"]),
        groups=[],
    )
    dependency = require_permission("test:read")
    auth_context = await dependency(x_tenant_id="tenant-a", user=user)
    assert auth_context.user_id == "superuser"

from src.core.auth import require_service_auth

@pytest.mark.asyncio
async def test_require_service_auth_success():
    """Test successful service authentication."""
    token = forge_jwt(payload_override={"azp": "nifi-service", "preferred_username": "test-service"})
    service_context = await require_service_auth(authorization=f"Bearer {token}")
    assert service_context.service_name == "test-service"

@pytest.mark.asyncio
async def test_require_service_auth_no_bearer():
    """Test that a token without the 'Bearer ' prefix is rejected."""
    token = forge_jwt(payload_override={"azp": "nifi-service"})
    with pytest.raises(HTTPException) as exc_info:
        await require_service_auth(authorization=token)
    assert exc_info.value.status_code == 401

@pytest.mark.asyncio
async def test_require_service_auth_missing_azp():
    """Test that a token without 'azp' claim is rejected."""
    token = forge_jwt(payload_override={"azp": None})
    with pytest.raises(HTTPException) as exc_info:
        await require_service_auth(authorization=f"Bearer {token}")
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