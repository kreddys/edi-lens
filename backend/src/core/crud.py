from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional

from src.models import trading_partner, partner_profile, profile_criterion
from src.api import schemas

async def get_partner_by_name(db: AsyncSession, *, name: str, tenant_id: int) -> Optional[trading_partner.TradingPartner]:
    """Retrieve a single trading partner by name for a specific tenant."""
    result = await db.execute(
        select(trading_partner.TradingPartner)
        .filter(trading_partner.TradingPartner.name == name)
        .filter(trading_partner.TradingPartner.tenant_id == tenant_id)
    )
    return result.scalars().first()

async def create_partner_with_profiles(
    db: AsyncSession, *, partner_in: schemas.TradingPartnerCreate, tenant_id: int
) -> trading_partner.TradingPartner:
    """
    Create a new trading partner, along with their profiles and criteria,
    all within a single database transaction.
    """
    # Create the main TradingPartner object
    db_partner = trading_partner.TradingPartner(
        name=partner_in.name,
        description=partner_in.description,
        tenant_id=tenant_id
    )
    db.add(db_partner)
    await db.flush() # Flush to get the ID of the new partner

    # Loop through the profiles in the request data
    for profile_in in partner_in.profiles:
        db_profile = partner_profile.PartnerProfile(
            name=profile_in.name,
            implementation_guide=profile_in.implementation_guide,
            priority=profile_in.priority,
            partner_id=db_partner.id,
            tenant_id=tenant_id
        )
        db.add(db_profile)
        await db.flush() # Flush to get the ID of the new profile

        # Loop through the criteria for the current profile
        for criterion_in in profile_in.criteria:
            db_criterion = profile_criterion.ProfileCriterion(
                profile_id=db_profile.id,
                tenant_id=tenant_id,
                **criterion_in.model_dump()
            )
            db.add(db_criterion)
    
    await db.commit()
    await db.refresh(db_partner)
    return db_partner