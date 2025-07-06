import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.models import trading_partner, audit_log
from src.core.auth import User, RealmAccess

# This pytest mark applies the asyncio mode to all tests in this file
pytestmark = pytest.mark.asyncio

@pytest.fixture
def mock_get_current_user_for_audit():
    """
    Mocks the get_current_user dependency for audit tests.
    This provides a valid User object with all necessary permissions.
    """
    from src.main import app
    from src.core.auth import get_current_user

    mock_user = User(
        sub="audit-user-789",
        preferred_username="auditor",
        groups=["tenant-a"], 
        # Give all partner permissions for the lifecycle test
        realm_access=RealmAccess(roles=["partner:create", "partner:update", "partner:delete"]) 
    )

    async def _mock_get_user():
        return mock_user

    app.dependency_overrides[get_current_user] = _mock_get_user
    
    yield
    
    del app.dependency_overrides[get_current_user]

async def test_trading_partner_lifecycle_creates_audit_logs(
    async_client: AsyncClient, 
    db_session: AsyncSession,
    mock_get_current_user_for_audit  # Activate the fixture
):
    """
    Tests that CREATE, UPDATE, and DELETE operations on a Trading Partner
    generate corresponding audit log entries.
    """
    headers = {"X-Tenant-ID": "tenant-a"}
    
    # 1. CREATE Operation
    create_data = {
        "name": "Audit Test Corp",
        "description": "Initial Description",
        "profiles": []
    }
    response = await async_client.post("/api/v1/trading-partners", json=create_data, headers=headers)
    assert response.status_code == 201
    created_partner_id = response.json()["id"]

    # Verify CREATE audit log
    create_log_result = await db_session.execute(
        select(audit_log.AuditLog).filter_by(
            action=audit_log.AuditAction.CREATE,
            table_name='trading_partners',
            record_pk=str(created_partner_id)
        )
    )
    create_log = create_log_result.scalars().one_or_none()
    assert create_log is not None
    assert create_log.user_id == "audit-user-789"
    assert create_log.username == "auditor"
    assert create_log.tenant_id == "tenant-a"
    assert create_log.before_value is None
    assert create_log.after_value["name"] == "Audit Test Corp"
    assert create_log.after_value["description"] == "Initial Description"

    # 2. UPDATE Operation
    # We need a separate API endpoint for update, which doesn't exist yet.
    # For now, we will simulate an update directly via the repository to test the audit hook.
    partner_to_update = await db_session.get(trading_partner.TradingPartner, created_partner_id)
    assert partner_to_update is not None
    
    partner_to_update.description = "Updated Description"
    db_session.add(partner_to_update)
    await db_session.commit() # This will trigger the audit log

    # Verify UPDATE audit log
    update_log_result = await db_session.execute(
        select(audit_log.AuditLog).filter_by(
            action=audit_log.AuditAction.UPDATE,
            table_name='trading_partners',
            record_pk=str(created_partner_id)
        )
    )
    update_log = update_log_result.scalars().one()
    assert update_log.before_value["description"] == "Initial Description"
    assert update_log.after_value["description"] == "Updated Description"
    assert "name" not in update_log.before_value # Should only log changed fields

    # 3. DELETE Operation
    # We also don't have a DELETE endpoint, so we'll simulate it.
    await db_session.delete(partner_to_update)
    await db_session.commit()

    # Verify DELETE audit log
    delete_log_result = await db_session.execute(
        select(audit_log.AuditLog).filter_by(
            action=audit_log.AuditAction.DELETE,
            table_name='trading_partners',
            record_pk=str(created_partner_id)
        )
    )
    delete_log = delete_log_result.scalars().one()
    assert delete_log.after_value is None
    assert delete_log.before_value["name"] == "Audit Test Corp"
    assert delete_log.before_value["description"] == "Updated Description"