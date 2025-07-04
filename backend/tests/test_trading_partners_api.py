import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.models import trading_partner
from src.core.auth import User

pytestmark = pytest.mark.asyncio

@pytest.fixture
def mock_get_current_user(app):
    """Fixture to mock the get_current_user dependency for protected routes."""
    # This user object mimics the one we'd get from a validated Keycloak token
    mock_user = User(
        sub="mock-user-id",
        username="testuser",
        email="test@example.com",
        roles=["user"]
    )
    
    async def _mock():
        return mock_user

    from src.core.auth import get_current_user
    app.dependency_overrides[get_current_user] = _mock
    yield
    del app.dependency_overrides[get_current_user]


async def test_create_trading_partner(
    async_client: AsyncClient, 
    db_session: AsyncSession, # Get the transactional session from conftest
    mock_get_current_user # Activate the dependency override
):
    """
    Test creating a trading partner with a profile and criteria successfully.
    """
    partner_data = {
        "name": "Test Payer Health Inc.",
        "description": "Primary Payer for Testing",
        "profiles": [
            {
                "name": "Health Inc. Production 837I",
                "implementation_guide": "837.5010.X223.A1",
                "priority": 20,
                "criteria": [
                    {
                        "field_source": "GS",
                        "field_identifier": "02",
                        "operator": "EQUALS",
                        "value": "HEALTHINC"
                    }
                ]
            }
        ]
    }

    response = await async_client.post("/api/v1/trading-partners/", json=partner_data)

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["name"] == "Test Payer Health Inc."
    assert len(data["profiles"]) == 1
    assert data["profiles"][0]["name"] == "Health Inc. Production 837I"
    assert len(data["profiles"][0]["criteria"]) == 1
    assert data["profiles"][0]["criteria"][0]["value"] == "HEALTHINC"
    assert data["profiles"][0]["criteria"][0]["field_source"] == "GS"

    # Verify it was saved to the database correctly
    result = await db_session.execute(
        select(trading_partner.TradingPartner)
        .where(trading_partner.TradingPartner.id == data["id"])
    )
    saved_partner = result.scalars().one_or_none()
    assert saved_partner is not None
    assert saved_partner.name == "Test Payer Health Inc."