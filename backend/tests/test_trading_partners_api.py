import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.models import trading_partner
# Import the nested Pydantic models needed to create a valid mock user
from src.core.auth import User, RealmAccess

# This pytest mark applies the asyncio mode to all tests in this file
pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_get_current_user():
    """
    This fixture mocks the `get_current_user` dependency for all protected API routes.
    It creates a valid User object that matches the updated Pydantic model,
    preventing validation errors during testing.
    """
    # Import the app and the dependency function inside the fixture
    from src.main import app
    from src.core.auth import get_current_user
    
    # 1. First, create the nested RealmAccess object that the User model now expects.
    mock_realm_access = RealmAccess(roles=["user", "admin"])

    # 2. Create the main User object. We initialize it using the alias names
    #    ('sub', 'preferred_username', etc.) because Pydantic uses these for
    #    validation when creating a model from a dict-like structure.
    mock_user = User(
        sub="mock-user-id",
        preferred_username="testuser",
        email="test@example.com",
        given_name="Mock",
        family_name="User",
        realm_access=mock_realm_access  # Pass the nested object here
    )
    
    # 3. Define the async function that will replace the real dependency.
    async def _mock_get_current_user():
        return mock_user

    # 4. Use FastAPI's dependency_overrides to replace the real function with our mock.
    app.dependency_overrides[get_current_user] = _mock_get_current_user
    
    # 5. The test runs at this point.
    yield
    
    # 6. After the test completes, clean up the override to ensure tests are isolated.
    del app.dependency_overrides[get_current_user]


async def test_create_trading_partner(
    async_client: AsyncClient, 
    db_session: AsyncSession,
    mock_get_current_user  # By including this as an argument, we activate the fixture.
):
    """
    Tests the successful creation of a new Trading Partner.
    This endpoint is protected and relies on the `mock_get_current_user` fixture.
    """
    # Define the payload for the API request
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

    # Make the API call to the protected endpoint
    response = await async_client.post("/api/v1/trading-partners/", json=partner_data)

    # Assert that the request was successful (201 Created)
    assert response.status_code == 201, response.text
    
    # Assert that the JSON response contains the correct data
    data = response.json()
    assert data["name"] == "Test Payer Health Inc."
    assert len(data["profiles"]) == 1
    assert data["profiles"][0]["name"] == "Health Inc. Production 837I"
    assert len(data["profiles"][0]["criteria"]) == 1
    assert data["profiles"][0]["criteria"][0]["value"] == "HEALTHINC"
    assert data["profiles"][0]["criteria"][0]["field_source"] == "GS"

    # Verify that the data was actually saved to the database correctly
    result = await db_session.execute(
        select(trading_partner.TradingPartner)
        .where(trading_partner.TradingPartner.id == data["id"])
    )
    saved_partner = result.scalars().one_or_none()
    assert saved_partner is not None
    assert saved_partner.name == "Test Payer Health Inc."