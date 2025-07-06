import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import uuid

from src.models import trading_partner, audit_log
from src.core.auth import User, RealmAccess
# --- THIS IS THE FIX ---
# Import the context variables to set them in the test
from src.core.audit import user_id_cv, username_cv, tenant_id_cv, request_id_cv


pytestmark = pytest.mark.asyncio

# This mock user will be used for both the API call and direct DB operations
MOCK_AUDIT_USER = User(
    sub="audit-user-789",
    preferred_username="auditor",
    groups=["tenant-a"], 
    realm_access=RealmAccess(roles=["partner:create", "partner:update", "partner:delete"]) 
)

@pytest.fixture
def mock_get_current_user_for_audit():
    """Mocks the get_current_user dependency for audit tests."""
    from src.main import app
    from src.core.auth import get_current_user

    async def _mock_get_user():
        return MOCK_AUDIT_USER

    app.dependency_overrides[get_current_user] = _mock_get_user
    yield
    del app.dependency_overrides[get_current_user]


async def test_trading_partner_lifecycle_creates_audit_logs(
    async_client: AsyncClient, 
    db_session: AsyncSession,
    mock_get_current_user_for_audit
):
    """
    Tests that CREATE, UPDATE, and DELETE operations on a Trading Partner
    generate corresponding audit log entries.
    """
    headers = {"X-Tenant-ID": "tenant-a"}
    
    # 1. CREATE Operation (via API)
    create_data = {
        "name": "Audit Test Corp",
        "description": "Initial Description",
        "profiles": []
    }
    # The API call will handle its own commit and context variables
    response = await async_client.post("/api/v1/trading-partners", json=create_data, headers=headers)
    assert response.status_code == 201
    created_partner_id = response.json()["id"]

    # Verify CREATE audit log
    create_log_result = await db_session.execute(
        select(audit_log.AuditLog).filter_by(
            action=audit_log.AuditAction.CREATE,
            table_name='trading_partners'
        )
    )
    create_log = create_log_result.scalars().one()
    assert create_log.user_id == MOCK_AUDIT_USER.sub
    assert create_log.username == MOCK_AUDIT_USER.username
    assert create_log.tenant_id == "tenant-a"
    assert create_log.record_pk == str(created_partner_id)
    assert create_log.before_value is None
    assert create_log.after_value["name"] == "Audit Test Corp"

    # --- THIS IS THE FIX ---
    # 2. UPDATE Operation (Direct DB interaction)
    # Manually set the context variables for this part of the test
    user_id_cv.set(MOCK_AUDIT_USER.sub)
    username_cv.set(MOCK_AUDIT_USER.username)
    tenant_id_cv.set("tenant-a")
    request_id_cv.set(f"test-request-{uuid.uuid4()}")

    partner_to_update = await db_session.get(trading_partner.TradingPartner, created_partner_id)
    assert partner_to_update is not None
    
    partner_to_update.description = "Updated Description"
    db_session.add(partner_to_update)
    await db_session.commit() # This will trigger the audit log hook with the context we just set

    # Verify UPDATE audit log
    update_log_result = await db_session.execute(
        select(audit_log.AuditLog).filter_by(action=audit_log.AuditAction.UPDATE)
    )
    update_log = update_log_result.scalars().one()
    assert update_log.before_value["description"] == "Initial Description"
    assert update_log.after_value["description"] == "Updated Description"

    # 3. DELETE Operation (Direct DB interaction)
    # The context variables are still set from the step above
    await db_session.delete(partner_to_update)
    await db_session.commit()

    # Verify DELETE audit log
    delete_log_result = await db_session.execute(
        select(audit_log.AuditLog).filter_by(action=audit_log.AuditAction.DELETE)
    )
    delete_log = delete_log_result.scalars().one()
    assert delete_log.after_value is None
    assert delete_log.before_value["name"] == "Audit Test Corp"