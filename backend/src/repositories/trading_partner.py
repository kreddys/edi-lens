# FILE: backend/src/repositories/trading_partner.py

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Optional, List, Tuple
from sqlalchemy.orm import selectinload
import logging
import sqlalchemy as sa

from src.models import trading_partner, partner_profile
from src.api import schemas
from src.core.auth import AuthContext

logger = logging.getLogger(__name__)

class TradingPartnerRepository:
    def __init__(self, db_session: AsyncSession, auth_context: AuthContext):
        """
        Initializes the repository with a database session and a mandatory
        authentication context to ensure all operations are tenant-isolated.
        """
        self.db: AsyncSession = db_session
        self.auth_context = auth_context
        self.tenant_id = auth_context.tenant_id

    async def get_by_id(self, *, partner_id: int) -> Optional[trading_partner.TradingPartner]:
        """Retrieve a single trading partner by its ID within the user's tenant."""
        logger.debug(f"Querying for partner id='{partner_id}' in tenant='{self.tenant_id}'.")
        query = (
            select(trading_partner.TradingPartner)
            .options(selectinload(trading_partner.TradingPartner.profiles))
            .filter_by(id=partner_id, tenant_id=self.tenant_id)
        )
        result = await self.db.execute(query)
        return result.scalars().first()

    async def get_by_name(self, *, name: str) -> Optional[trading_partner.TradingPartner]:
        """Retrieve a single trading partner by name within the user's tenant."""
        logger.debug(f"Querying for trading partner with name='{name}' in tenant='{self.tenant_id}'.")
        result = await self.db.execute(
            select(trading_partner.TradingPartner)
            .filter(trading_partner.TradingPartner.name == name)
            .filter(trading_partner.TradingPartner.tenant_id == self.tenant_id)
        )
        return result.scalars().first()
    
    async def get_all_for_tenant(self, *, skip: int = 0, limit: int = 100) -> Tuple[List[trading_partner.TradingPartner], int]:
        """Retrieve all trading partners for the user's tenant with pagination."""
        logger.debug(f"Querying for all partners in tenant='{self.tenant_id}' with skip={skip}, limit={limit}.")
        
        count_query = select(sa.func.count()).select_from(trading_partner.TradingPartner).filter_by(tenant_id=self.tenant_id)
        total_count = (await self.db.execute(count_query)).scalar_one()

        query = (
            select(trading_partner.TradingPartner)
            .options(selectinload(trading_partner.TradingPartner.profiles))
            .filter_by(tenant_id=self.tenant_id)
            .offset(skip)
            .limit(limit)
            .order_by(trading_partner.TradingPartner.name)
        )
        result = await self.db.execute(query)
        partners = result.scalars().all()
        
        logger.debug(f"Successfully fetched {len(partners)} partners.")
        return partners, total_count    

    async def create_with_profiles(self, *, partner_in: schemas.TradingPartnerCreate) -> trading_partner.TradingPartner:
        """Create a new trading partner within the user's tenant."""
        logger.info(f"Creating partner '{partner_in.name}' for tenant '{self.tenant_id}'.")
        
        db_partner = trading_partner.TradingPartner(
            name=partner_in.name,
            description=partner_in.description,
            tenant_id=self.tenant_id,
            sftp_enabled=partner_in.sftp_enabled,
            sftp_username=partner_in.sftp_username
        )
        
        db_profiles = [
            partner_profile.PartnerProfile(
                tenant_id=self.tenant_id,
                **p.model_dump()
            )
            for p in partner_in.profiles
        ]
        db_partner.profiles = db_profiles
        
        self.db.add(db_partner)
        await self.db.flush()
        return db_partner

    async def update(
        self, *, db_partner: trading_partner.TradingPartner, partner_in: schemas.TradingPartnerUpdate
    ) -> trading_partner.TradingPartner:
        """Update a trading partner, ensuring it belongs to the user's tenant."""
        if db_partner.tenant_id != self.tenant_id:
            raise PermissionError("Access denied: Cannot update a trading partner from another tenant.")

        logger.info(f"Updating partner id={db_partner.id} for tenant '{self.tenant_id}'.")
        
        partner_data_to_update = partner_in.model_dump(exclude_unset=True)
        
        # Update direct attributes of the partner
        db_partner.name = partner_data_to_update.get("name", db_partner.name)
        db_partner.description = partner_data_to_update.get("description", db_partner.description)
        db_partner.sftp_enabled = partner_data_to_update.get("sftp_enabled", db_partner.sftp_enabled)
        db_partner.sftp_username = partner_data_to_update.get("sftp_username", db_partner.sftp_username)

        # Sync profiles (add, update, delete)
        if "profiles" in partner_data_to_update:
            existing_profiles_map = {p.id: p for p in db_partner.profiles}
            updated_profiles = []
            incoming_profile_ids = {p.id for p in partner_in.profiles if p.id}

            for profile_in in partner_in.profiles:
                if profile_in.id and profile_in.id in existing_profiles_map:
                    # Update existing profile
                    db_profile = existing_profiles_map[profile_in.id]
                    for key, value in profile_in.model_dump(exclude={'id'}).items():
                        setattr(db_profile, key, value)
                    updated_profiles.append(db_profile)
                else:
                    # Create new profile
                    new_profile = partner_profile.PartnerProfile(
                        tenant_id=self.tenant_id,
                        **profile_in.model_dump()
                    )
                    updated_profiles.append(new_profile)
            
            # This line handles deletions by replacing the collection.
            # SQLAlchemy's cascade="all, delete-orphan" will remove profiles
            # that are no longer in the updated_profiles list.
            db_partner.profiles = updated_profiles

        self.db.add(db_partner)
        await self.db.flush()
        return db_partner

    async def delete(self, *, db_partner: trading_partner.TradingPartner) -> None:
        """Delete a trading partner, ensuring it belongs to the user's tenant."""
        if db_partner.tenant_id != self.tenant_id:
            raise PermissionError("Access denied: Cannot delete a trading partner from another tenant.")
            
        logger.info(f"Deleting partner id={db_partner.id} for tenant '{self.tenant_id}'.")
        await self.db.delete(db_partner)
        await self.db.flush()