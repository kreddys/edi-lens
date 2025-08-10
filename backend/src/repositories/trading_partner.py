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
from src.services.sftp_user_manager import SftpUserManager

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
        """Create a new trading partner for a specific tenant."""
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

        # If SFTP is enabled, create the user in SFTPGo.
        if db_partner.sftp_enabled and db_partner.sftp_username:
            sftp_manager = SftpUserManager()
            success = sftp_manager.create_user(
                username=db_partner.sftp_username,
                tenant_id=self.tenant_id,
                partner_name=db_partner.name
            )
            if not success:
                # If SFTP user creation fails, we should not save the partner.
                # The exception will trigger a rollback of the DB transaction.
                raise Exception(f"Failed to create corresponding SFTPGo user '{db_partner.sftp_username}'.")

        await self.db.flush()
    
        return db_partner

    async def update(
        self, *, db_partner: trading_partner.TradingPartner, partner_in: schemas.TradingPartnerUpdate
    ) -> trading_partner.TradingPartner:
        """
        Update a trading partner, ensuring it belongs to the user's tenant.
        This method handles updates to partner details, profiles, and SFTP configuration.
        If SFTP is enabled or the username changes, it triggers user creation in SFTPGo.
        """
        # Security check: ensure the partner being updated belongs to the authenticated tenant
        if db_partner.tenant_id != self.tenant_id:
            raise PermissionError("Access denied: Cannot update a trading partner from another tenant.")

        logger.info(f"Updating partner id={db_partner.id} for tenant '{self.tenant_id}'.")
        
        # --- SFTP LOGIC: Store original values before updating ---
        original_sftp_enabled = db_partner.sftp_enabled
        original_sftp_username = db_partner.sftp_username
        
        # Update direct attributes of the partner from the incoming Pydantic model
        update_data = partner_in.model_dump(exclude_unset=True)
        db_partner.name = update_data.get("name", db_partner.name)
        db_partner.description = update_data.get("description", db_partner.description)
        db_partner.sftp_enabled = update_data.get("sftp_enabled", db_partner.sftp_enabled)
        db_partner.sftp_username = update_data.get("sftp_username", db_partner.sftp_username)

        # Sync profiles (add, update, delete)
        if "profiles" in update_data:
            existing_profiles_map = {p.id: p for p in db_partner.profiles}
            updated_profiles = []

            for profile_in in partner_in.profiles:
                if profile_in.id and profile_in.id in existing_profiles_map:
                    # Update existing profile
                    db_profile = existing_profiles_map[profile_in.id]
                    for key, value in profile_in.model_dump(exclude={'id'}, exclude_unset=True).items():
                        setattr(db_profile, key, value)
                    updated_profiles.append(db_profile)
                else:
                    # Create new profile
                    new_profile = partner_profile.PartnerProfile(
                        tenant_id=self.tenant_id,
                        **profile_in.model_dump()
                    )
                    updated_profiles.append(new_profile)
            
            db_partner.profiles = updated_profiles

        # --- SFTP LOGIC: Trigger user creation if SFTP state changed meaningfully ---
        sftp_username_changed = (db_partner.sftp_enabled and db_partner.sftp_username != original_sftp_username)
        sftp_was_just_enabled = (db_partner.sftp_enabled and not original_sftp_enabled)

        if (sftp_username_changed or sftp_was_just_enabled) and db_partner.sftp_username:
            logger.info(f"SFTP configuration changed for partner '{db_partner.name}'. Ensuring user exists in SFTPGo.")
            sftp_manager = SftpUserManager()
            success = sftp_manager.create_user(
                username=db_partner.sftp_username,
                tenant_id=self.tenant_id,
                partner_name=db_partner.name
            )
            if not success:
                # This exception will trigger a rollback of the entire database transaction,
                # preventing the partner from being saved in an inconsistent state.
                raise Exception(f"Failed to create or update the corresponding SFTPGo user '{db_partner.sftp_username}'.")
        
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