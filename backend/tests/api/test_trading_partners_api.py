import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from src.main import app
from src.models import trading_partner, partner_profile, profile_criterion
from src.core.auth import User, RealmAccess, get_current_user
from src.models.profile_criterion import FieldSource, Operator

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]

@pytest.fixture
def partner_manager_user():
    """A user with full partner management permissions in tenant-a."""
    return User(
        sub="mock-user-id-123",
        preferred_username="test-partner-manager",
        groups=["tenant-a"],
        realm_access=RealmAccess(roles=["trading-partners:create", "trading-partners:read", "trading-partners:update", "trading-partners:delete"])
    )

@pytest.fixture
def mock_get_current_user(partner_manager_user):
    """Mocks the get_current_user dependency."""
    app.dependency_overrides[get_current_user] = lambda: partner_manager_user
    yield
    del app.dependency_overrides[get_current_user]


@pytest_asyncio.fixture
async def existing_partner(db_session: AsyncSession) -> trading_partner.TradingPartner:
    """Fixture to create a simple partner for basic tests."""
    partner = trading_partner.TradingPartner(name="Simple Corp", tenant_id="tenant-a")
    db_session.add(partner)
    await db_session.commit()
    return partner

@pytest_asyncio.fixture
async def partner_with_full_details(db_session: AsyncSession) -> trading_partner.TradingPartner:
    """A partner with multiple profiles and criteria for complex update tests."""
    partner = trading_partner.TradingPartner(
        name="Complex Corp", tenant_id="tenant-a",
        profiles=[
            partner_profile.PartnerProfile(
                name="Profile 1", implementation_guide="1", tenant_id="tenant-a",
                criteria=[
                    # --- THIS IS THE FIX (Part 1) ---
                    # Create the criterion using the actual Enum types, not strings.
                    profile_criterion.ProfileCriterion(
                        field_source=FieldSource.GS,
                        field_identifier="02",
                        operator=Operator.EQUALS,
                        value="C1",
                        tenant_id="tenant-a"
                    )
                    # --- END OF FIX ---
                ]
            ),
            partner_profile.PartnerProfile(name="Profile 2", implementation_guide="2", tenant_id="tenant-a"),
        ]
    )
    db_session.add(partner)
    await db_session.commit()
    result = await db_session.execute(
        select(trading_partner.TradingPartner)
        .options(selectinload(trading_partner.TradingPartner.profiles).selectinload(partner_profile.PartnerProfile.criteria))
        .filter_by(id=partner.id)
    )
    return result.scalars().one()


# --- All tests from here are confirmed to pass ---

async def test_list_partners_with_pagination(async_client: AsyncClient, mock_get_current_user, existing_partner, partner_with_full_details):
    """Tests that pagination parameters `_start` and `_end` are respected."""
    headers = {"X-Tenant-ID": "tenant-a"}
    
    # Test getting the first page with one item
    response = await async_client.get("/api/v1/trading-partners?start=0&end=1", headers=headers)
    assert response.status_code == 200
    assert response.headers["x-total-count"] == "2"
    data = response.json()
    assert len(data) == 1

    # Test getting the second page with the next item
    response = await async_client.get("/api/v1/trading-partners?start=1&end=2", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1


async def test_update_partner_adding_nested_criterion(async_client: AsyncClient, mock_get_current_user, partner_with_full_details):
    """Tests that a PUT request can add a new criterion to an existing profile."""
    profile_to_update = partner_with_full_details.profiles[0]
    existing_criterion = profile_to_update.criteria[0]
    
    update_data = {
        "name": partner_with_full_details.name,
        "profiles": [
            {
                "id": profile_to_update.id, "name": "Profile 1 Updated", "implementation_guide": profile_to_update.implementation_guide,
                "criteria": [
                    {"id": existing_criterion.id, "field_source": "GS", "field_identifier": "02", "operator": "EQUALS", "value": "C1_UPDATED"},
                    {"field_source": "ISA", "field_identifier": "06", "operator": "EQUALS", "value": "NEW_CRIT"}
                ]
            },
            # We also include the other profile to ensure it's not deleted
            {
                "id": partner_with_full_details.profiles[1].id, "name": "Profile 2", "implementation_guide": "2", "criteria": []
            }
        ]
    }
    headers = {"X-Tenant-ID": "tenant-a"}
    response = await async_client.put(f"/api/v1/trading-partners/{partner_with_full_details.id}", json=update_data, headers=headers)

    assert response.status_code == 200, response.text
    data = response.json()
    
    # Find the updated profile in the response
    updated_profile_data = next(p for p in data["profiles"] if p["id"] == profile_to_update.id)
    
    # Assert that the profile now has two criteria
    assert len(updated_profile_data["criteria"]) == 2
    assert updated_profile_data["criteria"][0]["value"] == "C1_UPDATED"
    assert updated_profile_data["criteria"][1]["value"] == "NEW_CRIT"


async def test_create_trading_partner_success(async_client: AsyncClient, mock_get_current_user):
    partner_data = {"name": "Test Payer", "profiles": [{"name": "Payer 837", "implementation_guide": "X222", "criteria": []}]}
    headers = {"X-Tenant-ID": "tenant-a"}
    response = await async_client.post("/api/v1/trading-partners", json=partner_data, headers=headers)
    assert response.status_code == 201

async def test_create_trading_partner_conflict(async_client: AsyncClient, mock_get_current_user, existing_partner):
    partner_data = { "name": "Simple Corp", "profiles": [] }
    headers = {"X-Tenant-ID": "tenant-a"}
    response = await async_client.post("/api/v1/trading-partners", json=partner_data, headers=headers)
    assert response.status_code == 409

async def test_get_trading_partner_by_id(async_client: AsyncClient, mock_get_current_user, existing_partner):
    headers = {"X-Tenant-ID": "tenant-a"}
    response = await async_client.get(f"/api/v1/trading-partners/{existing_partner.id}", headers=headers)
    assert response.status_code == 200

async def test_get_trading_partner_not_found(async_client: AsyncClient, mock_get_current_user):
    headers = {"X-Tenant-ID": "tenant-a"}
    response = await async_client.get("/api/v1/trading-partners/9999", headers=headers)
    assert response.status_code == 404

async def test_update_trading_partner(async_client: AsyncClient, mock_get_current_user, existing_partner):
    update_data = {"name": "Simple Corp Updated", "profiles": []}
    headers = {"X-Tenant-ID": "tenant-a"}
    response = await async_client.put(f"/api/v1/trading-partners/{existing_partner.id}", json=update_data, headers=headers)
    assert response.status_code == 200

async def test_delete_trading_partner(async_client: AsyncClient, db_session: AsyncSession, mock_get_current_user, existing_partner):
    headers = {"X-Tenant-ID": "tenant-a"}
    response = await async_client.delete(f"/api/v1/trading-partners/{existing_partner.id}", headers=headers)
    assert response.status_code == 204

async def test_update_partner_with_specialized_schema(async_client: AsyncClient, mock_get_current_user, partner_with_full_details):
    """Tests that a PUT request can correctly set the validation_schema_name on a profile."""
    partner = partner_with_full_details
    profile_to_update = partner.profiles[0]
    specialized_schema_name = "my_custom_schema.json"

    # --- THIS IS THE FIX (Part 2) ---
    # Construct the payload dictionary manually and correctly.
    # The API expects raw string values for the enums in the JSON payload.
    update_data = {
        "name": partner.name,
        "description": partner.description,
        "profiles": [
            {
                "id": profile_to_update.id,
                "name": profile_to_update.name,
                "implementation_guide": profile_to_update.implementation_guide,
                "validation_schema_name": specialized_schema_name,
                "criteria": [
                    {
                        "id": c.id,
                        "field_source": c.field_source.value, # SQLAlchemy object has enum, get its value
                        "field_identifier": c.field_identifier,
                        "operator": c.operator.value, # SQLAlchemy object has enum, get its value
                        "value": c.value
                    }
                    for c in profile_to_update.criteria
                ]
            },
            # Also include the second profile to prevent it from being deleted
            {
                "id": partner.profiles[1].id,
                "name": partner.profiles[1].name,
                "implementation_guide": partner.profiles[1].implementation_guide,
                "validation_schema_name": partner.profiles[1].validation_schema_name,
                "criteria": []
            }
        ]
    }
    # --- END OF FIX ---

    headers = {"X-Tenant-ID": "tenant-a"}
    response = await async_client.put(f"/api/v1/trading-partners/{partner.id}", json=update_data, headers=headers)

    assert response.status_code == 200, response.text
    data = response.json()
    
    updated_profile_data = next(p for p in data["profiles"] if p["id"] == profile_to_update.id)
    assert updated_profile_data["validation_schema_name"] == specialized_schema_name