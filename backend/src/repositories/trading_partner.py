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
        db_partner.name = partner_data_to_update.get("name", db_partner.name)
        db_partner.description = partner_data_to_update.get("description", db_partner.description)

        if "profiles" in partner_data_to_update:
            # --- THIS IS THE FIX ---
            # Create a map of existing profiles for quick lookup.
            existing_profiles_map = {p.id: p for p in db_partner.profiles}
            updated_profiles = []

            for profile_in in partner_in.profiles:
                if profile_in.id and profile_in.id in existing_profiles_map:
                    # It's an existing profile, update it.
                    db_profile = existing_profiles_map[profile_in.id]
                    db_profile.name = profile_in.name
                    db_profile.implementation_guide = profile_in.implementation_guide
                    db_profile.priority = profile_in.priority
                    self._sync_criteria(db_profile, profile_in.criteria)
                    updated_profiles.append(db_profile)
                else:
                    # It's a new profile, create it.
                    new_profile = partner_profile.PartnerProfile(
                        name=profile_in.name,
                        implementation_guide=profile_in.implementation_guide,
                        priority=profile_in.priority,
                        tenant_id=db_partner.tenant_id,
                        criteria=[
                            profile_criterion.ProfileCriterion(tenant_id=db_partner.tenant_id, **c.model_dump())
                            for c in profile_in.criteria
                        ]
                    )
                    updated_profiles.append(new_profile)

            # Assign the new list to the relationship. SQLAlchemy's 'delete-orphan'
            # cascade will automatically delete any profiles that were in the original
            # list but are not in this new `updated_profiles` list.
            db_partner.profiles = updated_profiles

        self.db.add(db_partner)
        await self.db.flush()
        return db_partner

    def _sync_criteria(self, db_profile: partner_profile.PartnerProfile, criteria_in: List[schemas.ProfileCriterionUpdate]):
        """Helper to sync criteria for a given profile."""
        existing_criteria_map = {c.id: c for c in db_profile.criteria}
        updated_criteria = []

        for crit_in in criteria_in:
            if crit_in.id and crit_in.id in existing_criteria_map:
                db_crit = existing_criteria_map[crit_in.id]
                db_crit.field_source = crit_in.field_source
                db_crit.field_identifier = crit_in.field_identifier
                db_crit.operator = crit_in.operator
                db_crit.value = crit_in.value
                updated_criteria.append(db_crit)
            else:
                new_crit = profile_criterion.ProfileCriterion(tenant_id=db_profile.tenant_id, **crit_in.model_dump())
                updated_criteria.append(new_crit)
        
        db_profile.criteria = updated_criteria

    async def delete(self, *, db_partner: trading_partner.TradingPartner) -> None:
        """Delete a trading partner."""
        logger.info(f"Deleting partner id={db_partner.id} for tenant '{db_partner.tenant_id}'.")
        await self.db.delete(db_partner)
        await self.db.flush()