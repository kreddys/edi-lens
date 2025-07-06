from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Optional, List, Tuple
from sqlalchemy.orm import selectinload
import logging
import sqlalchemy as sa

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
        
        count_query = select(sa.func.count()).select_from(trading_partner.TradingPartner).filter_by(tenant_id=tenant_id)
        total_count = (await self.db.execute(count_query)).scalar_one()

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
        
        # --- THIS IS THE FIX ---
        # Following the recommended pattern: build the object graph, add it to the
        # session, and flush to get IDs, but let the caller manage the commit.
        
        db_partner = trading_partner.TradingPartner(
            name=partner_in.name,
            description=partner_in.description,
            tenant_id=tenant_id
        )
        
        db_profiles = []
        for profile_in in partner_in.profiles:
            db_profile = partner_profile.PartnerProfile(
                name=profile_in.name,
                implementation_guide=profile_in.implementation_guide,
                priority=profile_in.priority,
                tenant_id=tenant_id
            )
            db_criteria = []
            for criterion_in in profile_in.criteria:
                db_criteria.append(profile_criterion.ProfileCriterion(
                    tenant_id=tenant_id,
                    **criterion_in.model_dump()
                ))
            db_profile.criteria = db_criteria
            db_profiles.append(db_profile)
        db_partner.profiles = db_profiles
        
        # 2. Add the top-level object to the session.
        self.db.add(db_partner)
        
        # 3. Flush the session to send data to the DB and get generated IDs.
        #    The transaction remains OPEN.
        await self.db.flush()
        logger.debug(f"Flushed partner '{db_partner.name}'. ID should be available now.")
        
        # 4. Return the instance. It's fully populated and part of the session.
        #    The calling test fixture or get_db dependency will handle the commit/rollback.
        return db_partner