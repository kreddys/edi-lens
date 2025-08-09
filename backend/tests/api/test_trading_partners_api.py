# FILE: backend/tests/api/test_trading_partners_api.py

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from src.main import app
from src.models import trading_partner, partner_profile
from src.core.auth import User, RealmAccess, get_current_user

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
    """Fixture to create a partner with profiles for update tests."""
    partner = trading_partner.TradingPartner(
        name="Complex Corp", tenant_id="tenant-a",
        profiles=[
            partner_profile.PartnerProfile(
                name="Profile 1", 
                validation_schema_name="schema1.json", # <-- FIX
                tenant_id="tenant-a",
                file_name_patterns='["initial_claims_*.edi"]'
            ),
            partner_profile.PartnerProfile(
                name="Profile 2", 
                validation_schema_name="schema2.json", # <-- FIX
                tenant_id="tenant-a"
            ),
        ]
    )

async def test_update_trading_partner_with_filename_patterns(async_client: AsyncClient, db_session: AsyncSession, mock_get_current_user, existing_partner):
    """Tests updating a partner, including adding/modifying profiles with filename patterns."""
    profile1 = existing_partner.profiles[0]
    profile2 = existing_partner.profiles[1]

    update_data = {
        "name": "Complex Corp Updated",
        "profiles": [
            {
                "id": profile1.id, "name": "Profile 1 Updated", "implementation_guide": "1",
                "file_name_patterns": '["updated_claims_*.edi"]'
            },
            {
                "id": profile2.id, "name": "Profile 2", "implementation_guide": "2",
                "file_name_patterns": '["remits_*.x12"]'
            },
            {
                "name": "New Profile", "implementation_guide": "3", "file_name_patterns": '["new_*.txt"]'
            }
        ]
    }
    headers = {"X-Tenant-ID": "tenant-a"}
    response = await async_client.put(f"/api/v1/trading-partners/{existing_partner.id}", json=update_data, headers=headers)

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["name"] == "Complex Corp Updated"
    assert len(data["profiles"]) == 3
    
    # --- FIX: Refresh the object within the async session to load the new state ---
    await db_session.refresh(existing_partner, attribute_names=["profiles"])
    
    assert len(existing_partner.profiles) == 3

    profile1_db = next(p for p in existing_partner.profiles if p.id == profile1.id)
    profile2_db = next(p for p in existing_partner.profiles if p.id == profile2.id)
    new_profile_db = next(p for p in existing_partner.profiles if p.name == "New Profile")

    assert profile1_db.file_name_patterns == '["updated_claims_*.edi"]'
    assert profile2_db.file_name_patterns == '["remits_*.x12"]'
    assert new_profile_db.file_name_patterns == '["new_*.txt"]'