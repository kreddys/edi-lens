from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Optional, List, Tuple
from sqlalchemy.orm import selectinload
import logging
import sqlalchemy as sa

# No changes needed to this import
from src.models import trading_partner, partner_profile, profile_criterion
from src.api import schemas

logger = logging.getLogger(__name__)

class TradingPartnerRepository:
    def __init__(self, db_session: AsyncSession):
        self.db: AsyncSession = db_session

    async def get_by_name(self, *, name: str, tenant_id: str) -> Optional[trading_partner.TradingPartner]:
        """Retrieve a single trading partner by name for a specific tenant."""
        logger.debug(f"Querying for trading partner with name='{name}' in tenant='{tenant_id}'.")
        result = await self.db.execute(
            select(trading_partner.TradingPartner)
            .filter(trading_partner.TradingPartner.name == name)
            .filter(trading_partner.TradingPartner.tenant_id == tenant_id)
        )
        return result.scalars().first()
    
    async def get_all_for_tenant(
        self, *, tenant_id: str, skip: int = 0, limit: int = 100
    ) -> Tuple[List[trading_partner.TradingPartner], int]:
        """Retrieve all trading partners for a specific tenant with pagination."""
        logger.debug(f"Querying for all partners in tenant='{tenant_id}' with skip={skip}, limit={limit}.")
        
        # Query for the total count first
        count_query = select(sa.func.count()).select_from(trading_partner.TradingPartner).filter_by(tenant_id=tenant_id)
        total_count = (await self.db.execute(count_query)).scalar_one()

        # --- THIS IS THE FIX ---
        # Eagerly load the 'profiles' and the nested 'criteria' relationships
        # to prevent the MissingGreenlet/lazy-loading error during response serialization.
        query = (
            select(trading_partner.TradingPartner)
            .options(
                selectinload(trading_partner.TradingPartner.profiles)
                .selectinload(partner_profile.PartnerProfile.criteria)
            )
            .filter_by(tenant_id=tenant_id)
            .offset(skip)
            .limit(limit)
            .order_by(trading_partner.TradingPartner.name)
        )
        result = await self.db.execute(query)
        partners = result.scalars().all()
        
        logger.debug(f"Successfully fetched {len(partners)} partners with eager loading.")
        return partners, total_count    

    async def create_with_profiles(self, *, partner_in: schemas.TradingPartnerCreate, tenant_id: str) -> trading_partner.TradingPartner:
        """Create a new trading partner for a specific tenant."""
        logger.info(f"Creating partner '{partner_in.name}' with {len(partner_in.profiles)} profiles for tenant '{tenant_id}'.")
        db_partner = trading_partner.TradingPartner(
            name=partner_in.name,
            description=partner_in.description,
            tenant_id=tenant_id
        )
        self.db.add(db_partner)
        await self.db.flush()

        logger.debug(f"Created base partner with id={db_partner.id}. Now creating profiles.")
        for profile_in in partner_in.profiles:
            db_profile = partner_profile.PartnerProfile(
                name=profile_in.name,
                implementation_guide=profile_in.implementation_guide,
                priority=profile_in.priority,
                partner_id=db_partner.id,
                tenant_id=tenant_id
            )
            self.db.add(db_profile)
            await self.db.flush()

            for criterion_in in profile_in.criteria:
                db_criterion = profile_criterion.ProfileCriterion(
                    profile_id=db_profile.id,
                    tenant_id=tenant_id,
                    **criterion_in.model_dump()
                )
                self.db.add(db_criterion)
        
        await self.db.commit()
        logger.debug(f"Committed partner '{db_partner.name}'. Refreshing object with relationships.")
        
        # Eagerly load the relationships before returning
        # This is necessary because after a commit, the previous object instances are expired.
        result = await self.db.execute(
            select(trading_partner.TradingPartner)
            .options(
                selectinload(trading_partner.TradingPartner.profiles)
                .selectinload(partner_profile.PartnerProfile.criteria)
            )
            .filter(trading_partner.TradingPartner.id == db_partner.id)
        )
        return result.scalars().one()