import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.main import app
from src.models import audit_log
from src.core.auth import User, RealmAccess, get_current_user

pytestmark = pytest.mark.asyncio

@pytest.fixture
def mock_get_current_user_for_audit():
    """Mocks the get_current_user dependency for audit tests."""
    mock_user = User(
        sub="audit-user-789",
        preferred_username="auditor",
        groups=["tenant-a"], 
        realm_access=RealmAccess(roles=["partner:create", "partner:update", "partner:delete"]) 
    )
    # --- THIS IS THE FIX ---
    app.dependency_overrides[get_current_user] = lambda: mock_user
    yield mock_user
    del app.dependency_overrides[get_current_user]


async def test_trading_partner_lifecycle_creates_audit_logs(
    async_client: AsyncClient, 
    db_session: AsyncSession,
    mock_get_current_user_for_audit
):
    """
    Tests that CREATE, UPDATE, and DELETE operations via the API
    generate corresponding audit log entries.
    """
    headers = {"X-Tenant-ID": "tenant-a"}
    
    # 1. CREATE Operation (via API)
    create_data = { "name": "Audit Test Corp", "description": "Initial Description", "profiles": [] }
    create_response = await async_client.post("/api/v1/trading-partners", json=create_data, headers=headers)
    assert create_response.status_code == 201
    created_partner_id = create_response.json()["id"]

    create_log_result = await db_session.execute(
        select(audit_log.AuditLog).filter_by(action=audit_log.AuditAction.CREATE, table_name='trading_partners')
    )
    create_log = create_log_result.scalars().one()
    assert create_log.user_id == mock_get_current_user_for_audit.sub
    assert create_log.username == mock_get_current_user_for_audit.username
    assert create_log.record_pk == str(created_partner_id)

    # 2. UPDATE Operation (via API)
    update_data = { "name": "Audit Test Corp", "description": "Updated Description", "profiles": [] }
    update_response = await async_client.put(f"/api/v1/trading-partners/{created_partner_id}", json=update_data, headers=headers)
    assert update_response.status_code == 200

    update_log_result = await db_session.execute(
        select(audit_log.AuditLog).filter_by(action=audit_log.AuditAction.UPDATE).order_by(audit_log.AuditLog.id.desc())
    )
    update_log = update_log_result.scalars().first()
    assert update_log.record_pk == str(created_partner_id)
    assert update_log.before_value["description"] == "Initial Description"
    assert update_log.after_value["description"] == "Updated Description"

    # 3. DELETE Operation (via API)
    delete_response = await async_client.delete(f"/api/v1/trading-partners/{created_partner_id}", headers=headers)
    assert delete_response.status_code == 204

    delete_log_result = await db_session.execute(
        select(audit_log.AuditLog).filter_by(action=audit_log.AuditAction.DELETE).order_by(audit_log.AuditLog.id.desc())
    )
    delete_log = delete_log_result.scalars().one()
    assert delete_log.record_pk == str(created_partner_id)
    assert delete_log.after_value is None
    assert delete_log.before_value["name"] == "Audit Test Corp"