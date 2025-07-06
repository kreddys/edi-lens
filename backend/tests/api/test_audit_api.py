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
    mock_user = User(
        sub="audit-user-789", preferred_username="auditor", groups=["tenant-a"], 
        realm_access=RealmAccess(roles=["partner:create", "partner:update", "partner:delete"]) 
    )
    app.dependency_overrides[get_current_user] = lambda: mock_user
    yield mock_user
    del app.dependency_overrides[get_current_user]

async def test_no_audit_log_for_unauthenticated_request(async_client: AsyncClient, db_session: AsyncSession):
    create_data = { "name": "Should Not Be Logged", "profiles": [] }
    headers = {"X-Tenant-ID": "tenant-a"}
    response = await async_client.post("/api/v1/trading-partners", json=create_data, headers=headers)
    assert response.status_code == 403
    result = await db_session.execute(select(audit_log.AuditLog))
    assert len(result.scalars().all()) == 0

async def test_trading_partner_lifecycle_creates_audit_logs(async_client: AsyncClient, db_session: AsyncSession, mock_get_current_user_for_audit):
    headers = {"X-Tenant-ID": "tenant-a"}
    create_data = { "name": "Audit Test Corp", "description": "Initial", "profiles": [] }
    create_response = await async_client.post("/api/v1/trading-partners", json=create_data, headers=headers)
    assert create_response.status_code == 201
    partner_id = create_response.json()["id"]
    
    update_data = { "name": "Audit Test Corp", "description": "Updated", "profiles": [] }
    await async_client.put(f"/api/v1/trading-partners/{partner_id}", json=update_data, headers=headers)
    
    await async_client.delete(f"/api/v1/trading-partners/{partner_id}", headers=headers)
    
    logs = (await db_session.execute(select(audit_log.AuditLog).order_by(audit_log.AuditLog.id))).scalars().all()
    assert len(logs) == 3
    assert logs[0].action == audit_log.AuditAction.CREATE
    assert logs[1].action == audit_log.AuditAction.UPDATE
    assert logs[2].action == audit_log.AuditAction.DELETE