import pytest
from httpx import AsyncClient
from fastapi import FastAPI, Depends, APIRouter
import uuid

from src.main import app
from src.core.auth import User, RealmAccess, get_current_user, require_permission, AuthContext
from src.core.audit import user_id_cv, username_cv, tenant_id_cv, request_id_cv

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]

auth_test_router = APIRouter()
@auth_test_router.get("/protected-route")
async def protected_route(auth: AuthContext = Depends(require_permission("test:read"))):
    # In a real app, the audit context would be used by SQLAlchemy event listeners.
    # For this test, we'll just return it to verify it was set.
    return {
        "message": f"Welcome, {auth.username}!",
        "audit_user_id": user_id_cv.get(),
        "audit_tenant_id": tenant_id_cv.get(),
    }
app.include_router(auth_test_router, prefix="/auth-test")

@pytest.fixture
def user_with_permission():
    """A standard user with the correct permission."""
    return User(
        sub="test-user-sub-123",
        preferred_username="testuser",
        groups=["tenant-a"],
        realm_access=RealmAccess(roles=["test:read"])
    )

@pytest.fixture
def user_with_wrong_permission():
    """A user who is in the correct tenant but has the wrong permission."""
    return User(
        sub="wrong-perm-user", preferred_username="perm-tester", groups=["tenant-a"],
        realm_access=RealmAccess(roles=["some:other:permission"])
    )

@pytest.fixture
def user_in_wrong_tenant():
    """A user who has the right permission but is not in the target tenant group."""
    return User(
        sub="wrong-tenant-user", preferred_username="tenant-tester", groups=["tenant-c"],
        realm_access=RealmAccess(roles=["test:read"])
    )

@pytest.fixture
def superuser():
    """A superuser who should have access to everything."""
    return User(
        sub="superuser-id", preferred_username="super", groups=["tenant-a", "tenant-b"],
        realm_access=RealmAccess(roles=["superuser"])
    )

async def test_require_permission_sets_audit_context(async_client: AsyncClient, user_with_permission):
    """Verify that a successful permission check also sets the contextvars for the audit log."""
    app.dependency_overrides[get_current_user] = lambda: user_with_permission
    headers = {"X-Tenant-ID": "tenant-a"}
    
    # Reset context variables before the test
    user_id_cv.set(None)
    tenant_id_cv.set(None)

    response = await async_client.get("/auth-test/protected-route", headers=headers)
    
    assert response.status_code == 200
    data = response.json()

    # Check that the context variables were set correctly inside the endpoint
    assert data["audit_user_id"] == user_with_permission.sub
    assert data["audit_tenant_id"] == "tenant-a"
    
    del app.dependency_overrides[get_current_user]


async def test_require_permission_rejects_user_with_wrong_permission(async_client: AsyncClient, user_with_wrong_permission):
    """Verify a user with the wrong role is rejected with a 403."""
    app.dependency_overrides[get_current_user] = lambda: user_with_wrong_permission
    headers = {"X-Tenant-ID": "tenant-a"}
    response = await async_client.get("/auth-test/protected-route", headers=headers)
    assert response.status_code == 403
    del app.dependency_overrides[get_current_user]

async def test_require_permission_rejects_user_in_wrong_tenant(async_client: AsyncClient, user_in_wrong_tenant):
    """Verify a user is rejected if they don't belong to the tenant in the header."""
    app.dependency_overrides[get_current_user] = lambda: user_in_wrong_tenant
    headers = {"X-Tenant-ID": "tenant-a"}
    response = await async_client.get("/auth-test/protected-route", headers=headers)
    assert response.status_code == 403
    del app.dependency_overrides[get_current_user]

async def test_require_permission_allows_superuser(async_client: AsyncClient, superuser):
    """Verify a user with the 'superuser' role bypasses permission checks."""
    app.dependency_overrides[get_current_user] = lambda: superuser
    headers = {"X-Tenant-ID": "tenant-a"}
    response = await async_client.get("/auth-test/protected-route", headers=headers)
    assert response.status_code == 200
    del app.dependency_overrides[get_current_user]