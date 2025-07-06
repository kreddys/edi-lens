import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError

from src.repositories.trading_partner import TradingPartnerRepository
from src.models import trading_partner, partner_profile
from src.api import schemas

pytestmark = pytest.mark.asyncio

@pytest.fixture
def repo(db_session: AsyncSession) -> TradingPartnerRepository:
    """Provides a TradingPartnerRepository instance."""
    return TradingPartnerRepository(db_session)

@pytest_asyncio.fixture
async def partner_with_two_profiles(repo: TradingPartnerRepository, db_session: AsyncSession) -> trading_partner.TradingPartner:
    """A partner with multiple profiles for testing."""
    partner_in = schemas.TradingPartnerCreate(
        name="Complex Corp",
        profiles=[
            schemas.PartnerProfileCreate(name="Profile 1 to keep", implementation_guide="1", criteria=[]),
            schemas.PartnerProfileCreate(name="Profile 2 to delete", implementation_guide="2", criteria=[]),
        ]
    )
    partner = await repo.create_with_profiles(partner_in=partner_in, tenant_id="tenant-a")
    await db_session.commit()
    
    result = await db_session.execute(
        select(trading_partner.TradingPartner)
        .options(selectinload(trading_partner.TradingPartner.profiles))
        .filter_by(id=partner.id)
    )
    return result.scalars().one()

async def test_repo_create_conflict_raises_integrity_error(repo: TradingPartnerRepository, db_session: AsyncSession):
    """
    Tests that the database's UniqueConstraint correctly prevents duplicate
    (name, tenant_id) pairs at the lowest level.
    """
    partner1 = trading_partner.TradingPartner(name="Duplicate Corp", tenant_id="tenant-a")
    partner2 = trading_partner.TradingPartner(name="Duplicate Corp", tenant_id="tenant-a")
    
    repo.db.add(partner1)
    repo.db.add(partner2)
    
    with pytest.raises(IntegrityError):
        await db_session.commit()

async def test_repo_update_removes_orphan_profile(repo: TradingPartnerRepository, db_session: AsyncSession, partner_with_two_profiles):
    """
    Tests that the repository's update logic correctly removes a nested profile
    that is no longer present in the input data.
    """
    profile_to_keep = partner_with_two_profiles.profiles[0]
    
    update_schema = schemas.TradingPartnerUpdate(
        name=partner_with_two_profiles.name,
        profiles=[
            schemas.PartnerProfileUpdate(
                id=profile_to_keep.id,
                name=profile_to_keep.name,
                implementation_guide=profile_to_keep.implementation_guide,
                criteria=[]
            )
        ]
    )

    updated_partner = await repo.update(db_partner=partner_with_two_profiles, partner_in=update_schema)
    await db_session.commit()

    # --- THIS IS THE FIX ---
    # We must re-query the partner from the database with eager loading
    # to safely inspect its relationships after the transaction.
    result = await db_session.execute(
        select(trading_partner.TradingPartner)
        .options(selectinload(trading_partner.TradingPartner.profiles))
        .filter_by(id=updated_partner.id)
    )
    final_partner_state = result.scalars().one()

    assert len(final_partner_state.profiles) == 1
    assert final_partner_state.profiles[0].id == profile_to_keep.id
    assert final_partner_state.profiles[0].name == profile_to_keep.name