from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Optional, List, Tuple
from sqlalchemy.orm import selectinload, joinedload
import logging
import sqlalchemy as sa

from src.models import trading_partner, partner_profile, profile_criterion
from src.api import schemas

logger = logging.getLogger(__name__)

class TradingPartnerRepository:
    def __init__(self, db_session: AsyncSession):
        self.db: AsyncSession = db_session

    async def get_by_id(self, *, partner_id: int, tenant_id: str) -> Optional[trading_partner.TradingPartner]:
        """Retrieve a single trading partner by its ID for a specific tenant."""
        logger.debug(f"Querying for partner id='{partner_id}' in tenant='{tenant_id}'.")
        query = (
            select(trading_partner.TradingPartner)
            .options(
                selectinload(trading_partner.TradingPartner.profiles)
                .selectinload(partner_profile.PartnerProfile.criteria)
            )
            .filter_by(id=partner_id, tenant_id=tenant_id)
        )
        result = await self.db.execute(query)
        return result.scalars().first()

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
        
        self.db.add(db_partner)
        await self.db.flush()
        logger.debug(f"Flushed partner '{db_partner.name}'. ID should be available now.")
        return db_partner

    async def update(
        self, *, db_partner: trading_partner.TradingPartner, partner_in: schemas.TradingPartnerUpdate
    ) -> trading_partner.TradingPartner:
        """Update a trading partner and its nested profiles/criteria."""
        logger.info(f"Updating partner id={db_partner.id} for tenant '{db_partner.tenant_id}'.")
        
        partner_data_to_update = partner_in.model_dump(exclude_unset=True)
        # Update top-level fields
        db_partner.name = partner_data_to_update.get("name", db_partner.name)
        db_partner.description = partner_data_to_update.get("description", db_partner.description)

        # Sync profiles
        if "profiles" in partner_data_to_update:
            # A simple but effective strategy: delete existing and add new ones.
            # This is safe because of cascade delete-orphan.
            db_partner.profiles.clear()
            await self.db.flush()

            for profile_in in partner_in.profiles:
                new_profile = partner_profile.PartnerProfile(
                    name=profile_in.name,
                    implementation_guide=profile_in.implementation_guide,
                    priority=profile_in.priority,
                    tenant_id=db_partner.tenant_id
                )
                new_profile.criteria = [
                    profile_criterion.ProfileCriterion(tenant_id=db_partner.tenant_id, **c.model_dump())
                    for c in profile_in.criteria
                ]
                db_partner.profiles.append(new_profile)

        self.db.add(db_partner)
        await self.db.flush()
        # The key fix is to return the flushed object which is still attached to the session
        # The endpoint will then handle the final commit and eager re-fetch.
        return db_partner

    async def delete(self, *, db_partner: trading_partner.TradingPartner) -> None:
        """Delete a trading partner."""
        logger.info(f"Deleting partner id={db_partner.id} for tenant '{db_partner.tenant_id}'.")
        await self.db.delete(db_partner)
        await self.db.flush()