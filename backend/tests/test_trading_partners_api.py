import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from src.main import app
from src.models import trading_partner, partner_profile, profile_criterion
from src.core.auth import User, RealmAccess, get_current_user

pytestmark = pytest.mark.asyncio

@pytest.fixture
def mock_get_current_user_for_partner_api():
    """Mocks the get_current_user dependency for the partner API tests."""
    mock_user = User(
        sub="mock-user-id-123",
        preferred_username="test-partner-manager",
        groups=["tenant-a"],
        realm_access=RealmAccess(roles=["partner:create", "partner:read", "partner:update", "partner:delete"])
    )
    app.dependency_overrides[get_current_user] = lambda: mock_user
    yield mock_user
    del app.dependency_overrides[get_current_user]

@pytest_asyncio.fixture
async def existing_partner(db_session: AsyncSession) -> trading_partner.TradingPartner:
    """Fixture to create a trading partner in the DB for tests."""
    partner = trading_partner.TradingPartner(
        name="Existing Corp", description="A pre-existing partner for testing.", tenant_id="tenant-a",
        profiles=[
            partner_profile.PartnerProfile(
                name="Existing 837P Profile", implementation_guide="005010X222A1", tenant_id="tenant-a",
                criteria=[profile_criterion.ProfileCriterion(field_source="GS", field_identifier="02", operator="EQUALS", value="EXISTCORP", tenant_id="tenant-a")]
            )
        ]
    )
    db_session.add(partner)
    await db_session.commit()
    await db_session.refresh(partner)

    # --- THIS IS THE FIX ---
    # Eagerly load the relationships to prevent lazy loading in the test function.
    # We re-fetch the object from the database with explicit loading options.
    result = await db_session.execute(
        select(trading_partner.TradingPartner)
        .options(
            selectinload(trading_partner.TradingPartner.profiles)
            .selectinload(partner_profile.PartnerProfile.criteria)
        )
        .filter_by(id=partner.id)
    )
    return result.scalars().one()

async def test_create_trading_partner_success(async_client: AsyncClient, mock_get_current_user_for_partner_api):
    """Tests successful creation of a new Trading Partner."""
    partner_data = {
        "name": "Test Payer Health Inc.", "description": "Primary Payer for Testing",
        "profiles": [{"name": "Health Inc. Prod 837I", "implementation_guide": "837.5010.X223.A1",
                      "criteria": [{"field_source": "GS", "field_identifier": "02", "operator": "EQUALS", "value": "HEALTHINC"}]}]}
    headers = {"X-Tenant-ID": "tenant-a"}
    response = await async_client.post("/api/v1/trading-partners", json=partner_data, headers=headers)
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["name"] == "Test Payer Health Inc."

async def test_create_trading_partner_conflict(async_client: AsyncClient, mock_get_current_user_for_partner_api, existing_partner):
    """Tests that creating a partner with a duplicate name in the same tenant fails."""
    partner_data = { "name": "Existing Corp", "description": "Duplicate", "profiles": [] }
    headers = {"X-Tenant-ID": "tenant-a"}
    response = await async_client.post("/api/v1/trading-partners", json=partner_data, headers=headers)
    assert response.status_code == 409

async def test_get_trading_partner_list(async_client: AsyncClient, mock_get_current_user_for_partner_api, existing_partner):
    """Tests listing trading partners with pagination."""
    headers = {"X-Tenant-ID": "tenant-a"}
    response = await async_client.get("/api/v1/trading-partners?start=0&end=10", headers=headers)
    assert response.status_code == 200

async def test_get_trading_partner_by_id(async_client: AsyncClient, mock_get_current_user_for_partner_api, existing_partner):
    """Tests fetching a single trading partner by its ID."""
    headers = {"X-Tenant-ID": "tenant-a"}
    response = await async_client.get(f"/api/v1/trading-partners/{existing_partner.id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["id"] == existing_partner.id

async def test_get_trading_partner_not_found(async_client: AsyncClient, mock_get_current_user_for_partner_api):
    """Tests that a 404 is returned for a non-existent partner ID."""
    headers = {"X-Tenant-ID": "tenant-a"}
    response = await async_client.get("/api/v1/trading-partners/9999", headers=headers)
    assert response.status_code == 404

async def test_update_trading_partner(async_client: AsyncClient, mock_get_current_user_for_partner_api, existing_partner):
    """Tests updating a trading partner, including nested profiles and criteria."""
    update_data = {
        "name": "Existing Corp Updated", "description": "Updated Description",
        "profiles": [{"id": existing_partner.profiles[0].id, "name": "Updated 837P Profile", "implementation_guide": "005010X222A2",
                      "criteria": [{"id": existing_partner.profiles[0].criteria[0].id, "field_source": "ISA", "field_identifier": "06", "operator": "EQUALS", "value": "NEWVALUE"}]}]}
    headers = {"X-Tenant-ID": "tenant-a"}
    response = await async_client.put(f"/api/v1/trading-partners/{existing_partner.id}", json=update_data, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["name"] == "Existing Corp Updated"

async def test_delete_trading_partner(async_client: AsyncClient, db_session: AsyncSession, mock_get_current_user_for_partner_api, existing_partner):
    """Tests deleting a trading partner."""
    headers = {"X-Tenant-ID": "tenant-a"}
    response = await async_client.delete(f"/api/v1/trading-partners/{existing_partner.id}", headers=headers)
    assert response.status_code == 204
    partner_in_db = await db_session.get(trading_partner.TradingPartner, existing_partner.id)
    assert partner_in_db is None