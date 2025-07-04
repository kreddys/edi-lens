from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Optional
from sqlalchemy.orm import selectinload

from src.models import trading_partner, partner_profile, profile_criterion
from src.api import schemas

class TradingPartnerRepository:
    def __init__(self, db_session: AsyncSession):
        self.db: AsyncSession = db_session

    async def get_by_name(self, *, name: str) -> Optional[trading_partner.TradingPartner]:
        """Retrieve a single trading partner by its unique name."""
        result = await self.db.execute(
            select(trading_partner.TradingPartner).filter(trading_partner.TradingPartner.name == name)
        )
        return result.scalars().first()

    async def create_with_profiles(self, *, partner_in: schemas.TradingPartnerCreate) -> trading_partner.TradingPartner:
        """
        Create a new trading partner, along with their profiles and criteria,
        all within a single database transaction.
        """
        async with self.db.begin_nested(): # Create a savepoint
            # Create the main TradingPartner object
            db_partner = trading_partner.TradingPartner(
                name=partner_in.name,
                description=partner_in.description,
            )
            self.db.add(db_partner)
            await self.db.flush()

            for profile_in in partner_in.profiles:
                db_profile = partner_profile.PartnerProfile(
                    name=profile_in.name,
                    implementation_guide=profile_in.implementation_guide,
                    priority=profile_in.priority,
                    partner_id=db_partner.id
                )
                self.db.add(db_profile)
                await self.db.flush()

                for criterion_in in profile_in.criteria:
                    db_criterion = profile_criterion.ProfileCriterion(
                        profile_id=db_profile.id,
                        **criterion_in.model_dump()
                    )
                    self.db.add(db_criterion)
        
        await self.db.commit()

        # Eagerly load the relationships before returning
        result = await self.db.execute(
            select(trading_partner.TradingPartner)
            .options(
                selectinload(trading_partner.TradingPartner.profiles)
                .selectinload(partner_profile.PartnerProfile.criteria)
            )
            .filter(trading_partner.TradingPartner.id == db_partner.id)
        )
        return result.scalars().one()