import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.models import trading_partner
from src.core.auth import User, RealmAccess

# This pytest mark applies the asyncio mode to all tests in this file
pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_get_current_user():
    """
    Mocks the get_current_user dependency.
    This fixture provides a valid User object that will be passed into the
    real `require_permission` dependency during the test.
    """
    from src.main import app
    from src.core.auth import get_current_user

    # 1. Create a mock user who has the necessary permissions and tenant group.
    mock_user = User(
        sub="mock-user-id-123",
        preferred_username="test-partner-creator",
        groups=["tenant-a"], # Belongs to the tenant we will test with
        realm_access=RealmAccess(roles=["partner:create"]) # Has the required permission
    )

    # 2. This is the simple dependency that will replace get_current_user
    async def _mock_get_user():
        return mock_user

    # 3. Override the base dependency
    app.dependency_overrides[get_current_user] = _mock_get_user
    
    yield
    
    # 4. Clean up the override after the test
    del app.dependency_overrides[get_current_user]


async def test_create_trading_partner(
    async_client: AsyncClient, 
    db_session: AsyncSession,
    mock_get_current_user  # Activate the fixture
):
    """
    Tests the successful creation of a new Trading Partner within a specific tenant.
    This tests the full RBAC flow by mocking the base user dependency.
    """
    partner_data = {
        "name": "Test Payer Health Inc.",
        "description": "Primary Payer for Testing",
        "profiles": [{
            "name": "Health Inc. Production 837I",
            "implementation_guide": "837.5010.X223.A1",
            "priority": 20,
            "criteria": [{
                "field_source": "GS", "field_identifier": "02",
                "operator": "EQUALS", "value": "HEALTHINC"
            }]
        }]
    }

    # The request must include the X-Tenant-ID header.
    # The value 'tenant-a' must match one of the groups in our mock_user.
    headers = {"X-Tenant-ID": "tenant-a"}

    # The request no longer needs an Authorization header because we are
    # directly mocking the get_current_user dependency.
    response = await async_client.post(
        "/api/v1/trading-partners/", 
        json=partner_data,
        headers=headers
    )

    assert response.status_code == 201, response.text
    
    data = response.json()
    assert data["name"] == "Test Payer Health Inc."
    assert data["tenant_id"] == "tenant-a"
    assert len(data["profiles"]) == 1
    assert data["profiles"][0]["tenant_id"] == "tenant-a"
    assert len(data["profiles"][0]["criteria"]) == 1
    assert data["profiles"][0]["criteria"][0]["tenant_id"] == "tenant-a"

    # Verify that the tenant_id was saved to the database correctly
    result = await db_session.execute(
        select(trading_partner.TradingPartner)
        .where(trading_partner.TradingPartner.id == data["id"])
    )
    saved_partner = result.scalars().one_or_none()
    assert saved_partner is not None
    assert saved_partner.name == "Test Payer Health Inc."
    assert saved_partner.tenant_id == "tenant-a"