"""
Secure Multi-Tenant Trading Partner Repository
==============================================

This repository provides secure, tenant-isolated access to trading partner data.
All operations are validated against the authenticated user's tenant context.

Key Security Features:
- Mandatory authentication context
- Automatic tenant isolation enforcement
- Audit logging for all operations
- Input validation and sanitization
- Secure error handling
"""

import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import text
from typing import Optional, List, Tuple
import sqlalchemy as sa

from src.models import trading_partner, partner_profile, profile_criterion, sftp_configuration
from src.api import schemas
from src.core.auth import AuthContext

logger = logging.getLogger(__name__)


class TenantSecurityError(Exception):
    """Raised when tenant security validation fails."""
    pass


class SecureTradingPartnerRepository:
    """
    Secure repository for trading partner operations with mandatory tenant isolation.
    
    This repository ensures:
    1. All operations are scoped to the authenticated user's tenant
    2. Cross-tenant access is prevented
    3. All operations are audited
    4. Input validation is performed
    5. Secure error handling prevents information disclosure
    """
    
    def __init__(self, db_session: AsyncSession, auth_context: AuthContext):
        """
        Initialize secure repository with authentication context.
        
        Args:
            db_session: Database session
            auth_context: Authenticated user context with tenant information
        """
        self.db: AsyncSession = db_session
        self.auth_context = auth_context
        self.tenant_id = auth_context.tenant_id
        self.user_id = auth_context.user_id
        self.username = auth_context.username
        
        logger.info(
            f"SecureTradingPartnerRepository initialized for user {self.username} "
            f"in tenant {self.tenant_id}"
        )
    
    def _log_operation(self, operation: str, partner_id: Optional[int] = None, 
                      status: str = "SUCCESS", details: Optional[dict] = None):
        """Log repository operation for audit trail."""
        logger.info(
            f"TradingPartner Operation: {operation} by {self.username} "
            f"in tenant {self.tenant_id} - Status: {status}",
            extra={
                'tenant_id': self.tenant_id,
                'user_id': self.user_id,
                'operation': operation,
                'partner_id': partner_id,
                'status': status,
                'details': details or {}
            }
        )
    
    def _validate_tenant_ownership(self, partner: trading_partner.TradingPartner):
        """Validate that partner belongs to user's tenant."""
        if partner.tenant_id != self.tenant_id:
            self._log_operation(
                "security_violation",
                partner_id=partner.id,
                status="DENIED",
                details={
                    "violation_type": "cross_tenant_access",
                    "partner_tenant": partner.tenant_id,
                    "user_tenant": self.tenant_id
                }
            )
            
            raise TenantSecurityError(
                f"Access denied: Partner belongs to different tenant"
            )
    
    def _sanitize_partner_name(self, name: str) -> str:
        """Sanitize partner name input."""
        if not name or len(name.strip()) == 0:
            raise ValueError("Partner name cannot be empty")
        
        # Basic sanitization - could be enhanced based on requirements
        sanitized = name.strip()[:255]  # Limit length
        
        if len(sanitized) != len(name.strip()):
            logger.warning(f"Partner name truncated from {len(name)} to {len(sanitized)} characters")
        
        return sanitized
    
    async def get_by_id(self, *, partner_id: int) -> Optional[trading_partner.TradingPartner]:
        """
        Retrieve a trading partner by ID within user's tenant.
        
        Args:
            partner_id: ID of the partner to retrieve
            
        Returns:
            TradingPartner if found and accessible, None otherwise
        """
        try:
            logger.debug(f"Querying for partner id='{partner_id}' in tenant='{self.tenant_id}'.")
            
            query = (
                select(trading_partner.TradingPartner)
                .options(
                    selectinload(trading_partner.TradingPartner.profiles)
                    .selectinload(partner_profile.PartnerProfile.criteria)
                )
                .filter_by(id=partner_id, tenant_id=self.tenant_id)  # ✅ ENFORCED
            )
            
            result = await self.db.execute(query)
            partner = result.scalars().first()
            
            if partner:
                # Double-check tenant ownership (defense in depth)
                self._validate_tenant_ownership(partner)
                
                self._log_operation(
                    "get_by_id",
                    partner_id=partner_id,
                    status="SUCCESS",
                    details={"partner_name": partner.name}
                )
            else:
                self._log_operation(
                    "get_by_id",
                    partner_id=partner_id,
                    status="NOT_FOUND"
                )
            
            return partner
            
        except TenantSecurityError:
            raise
        except Exception as e:
            self._log_operation(
                "get_by_id",
                partner_id=partner_id,
                status="ERROR",
                details={"error": str(e)}
            )
            logger.error(f"Error retrieving partner {partner_id}: {e}", exc_info=True)
            raise
    
    async def get_by_name(self, *, name: str) -> Optional[trading_partner.TradingPartner]:
        """
        Retrieve a trading partner by name within user's tenant.
        
        Args:
            name: Name of the partner to retrieve
            
        Returns:
            TradingPartner if found and accessible, None otherwise
        """
        try:
            sanitized_name = self._sanitize_partner_name(name)
            
            logger.debug(f"Querying for trading partner with name='{sanitized_name}' in tenant='{self.tenant_id}'.")
            
            result = await self.db.execute(
                select(trading_partner.TradingPartner)
                .filter(trading_partner.TradingPartner.name == sanitized_name)
                .filter(trading_partner.TradingPartner.tenant_id == self.tenant_id)  # ✅ ENFORCED
            )
            
            partner = result.scalars().first()
            
            if partner:
                # Double-check tenant ownership (defense in depth)
                self._validate_tenant_ownership(partner)
                
                self._log_operation(
                    "get_by_name",
                    partner_id=partner.id,
                    status="SUCCESS",
                    details={"partner_name": sanitized_name}
                )
            else:
                self._log_operation(
                    "get_by_name",
                    status="NOT_FOUND",
                    details={"partner_name": sanitized_name}
                )
            
            return partner
            
        except TenantSecurityError:
            raise
        except Exception as e:
            self._log_operation(
                "get_by_name",
                status="ERROR",
                details={"error": str(e), "partner_name": name}
            )
            logger.error(f"Error retrieving partner by name '{name}': {e}", exc_info=True)
            raise
    
    async def get_all_for_tenant(
        self, *, skip: int = 0, limit: int = 100
    ) -> Tuple[List[trading_partner.TradingPartner], int]:
        """
        Retrieve all trading partners for the authenticated user's tenant.
        
        Args:
            skip: Number of records to skip (pagination)
            limit: Maximum number of records to return
            
        Returns:
            Tuple of (partners list, total count)
        """
        try:
            # Validate pagination parameters
            skip = max(0, skip)
            limit = max(1, min(1000, limit))  # Cap at 1000 for safety
            
            logger.debug(f"Querying for all partners in tenant='{self.tenant_id}' with skip={skip}, limit={limit}.")
            
            # Count query - scoped to user's tenant
            count_query = (
                select(sa.func.count())
                .select_from(trading_partner.TradingPartner)
                .filter_by(tenant_id=self.tenant_id)  # ✅ ENFORCED
            )
            total_count = (await self.db.execute(count_query)).scalar_one()
            
            # Data query - scoped to user's tenant
            query = (
                select(trading_partner.TradingPartner)
                .options(
                    selectinload(trading_partner.TradingPartner.profiles)
                    .selectinload(partner_profile.PartnerProfile.criteria)
                )
                .filter_by(tenant_id=self.tenant_id)  # ✅ ENFORCED
                .offset(skip)
                .limit(limit)
                .order_by(trading_partner.TradingPartner.name)
            )
            
            result = await self.db.execute(query)
            partners = result.scalars().all()
            
            # Validate all returned partners belong to user's tenant (defense in depth)
            for partner in partners:
                self._validate_tenant_ownership(partner)
            
            self._log_operation(
                "get_all_for_tenant",
                status="SUCCESS",
                details={
                    "total_count": total_count,
                    "returned_count": len(partners),
                    "skip": skip,
                    "limit": limit
                }
            )
            
            logger.debug(f"Successfully fetched {len(partners)} partners with eager loading.")
            return partners, total_count
            
        except TenantSecurityError:
            raise
        except Exception as e:
            self._log_operation(
                "get_all_for_tenant",
                status="ERROR",
                details={"error": str(e), "skip": skip, "limit": limit}
            )
            logger.error(f"Error retrieving all partners for tenant: {e}", exc_info=True)
            raise
    
    async def create_with_profiles(self, *, partner_in: schemas.TradingPartnerCreate) -> trading_partner.TradingPartner:
        """
        Create a new trading partner within the user's tenant.
        
        Args:
            partner_in: Partner creation data
            
        Returns:
            Created TradingPartner
        """
        try:
            sanitized_name = self._sanitize_partner_name(partner_in.name)
            
            logger.info(f"Creating partner '{sanitized_name}' with {len(partner_in.profiles)} profiles for tenant '{self.tenant_id}'.")
            
            # Check for duplicate name within tenant
            existing = await self.get_by_name(name=sanitized_name)
            if existing:
                raise ValueError(f"Partner with name '{sanitized_name}' already exists in your tenant")
            
            # Create partner - ALWAYS with user's tenant_id
            db_partner = trading_partner.TradingPartner(
                name=sanitized_name,
                description=partner_in.description,
                tenant_id=self.tenant_id  # ✅ ALWAYS USER'S TENANT
            )
            
            # Create profiles
            db_profiles = []
            for profile_in in partner_in.profiles:
                db_profile = partner_profile.PartnerProfile(
                    name=profile_in.name,
                    implementation_guide=profile_in.implementation_guide,
                    validation_schema_name=profile_in.validation_schema_name,
                    priority=profile_in.priority,
                    tenant_id=self.tenant_id  # ✅ ALWAYS USER'S TENANT
                )
                
                # Create criteria
                db_criteria = []
                for criterion_in in profile_in.criteria:
                    db_criteria.append(profile_criterion.ProfileCriterion(
                        tenant_id=self.tenant_id,  # ✅ ALWAYS USER'S TENANT
                        **criterion_in.model_dump()
                    ))
                
                db_profile.criteria = db_criteria
                db_profiles.append(db_profile)
            
            db_partner.profiles = db_profiles
            
            self.db.add(db_partner)
            await self.db.flush()
            
            # Create SFTP configuration if enabled
            if partner_in.sftp_enabled and partner_in.sftp_username and partner_in.sftp_password:
                logger.info(f"Creating SFTP configuration for partner '{sanitized_name}'")
                
                db_sftp_config = sftp_configuration.SftpConfiguration(
                    partner_id=db_partner.id,
                    tenant_id=self.tenant_id,  # ✅ ALWAYS USER'S TENANT
                    sftp_enabled=True,
                    sftp_username=partner_in.sftp_username,
                    password_hash=partner_in.sftp_password,  # TODO: Hash this properly
                    authentication_type=sftp_configuration.AuthenticationType.PASSWORD.value,
                    inbound_directory=f"/sftp/tenants/{self.tenant_id}/{partner_in.sftp_username}/in",
                    outbound_directory=f"/sftp/tenants/{self.tenant_id}/{partner_in.sftp_username}/out",
                    archive_directory=f"/sftp/tenants/{self.tenant_id}/.archive/{partner_in.sftp_username}",
                    file_name_patterns='["*.edi", "*.x12", "*.txt"]',
                    max_file_size_bytes=52428800,  # 50MB
                    response_timeout_minutes=30
                )
                
                self.db.add(db_sftp_config)
                await self.db.flush()
            
            self._log_operation(
                "create_with_profiles",
                partner_id=db_partner.id,
                status="SUCCESS",
                details={
                    "partner_name": sanitized_name,
                    "profiles_count": len(partner_in.profiles),
                    "sftp_enabled": partner_in.sftp_enabled
                }
            )
            
            logger.debug(f"Created partner '{db_partner.name}' with ID {db_partner.id}")
            return db_partner
            
        except Exception as e:
            self._log_operation(
                "create_with_profiles",
                status="ERROR",
                details={"error": str(e), "partner_name": partner_in.name}
            )
            logger.error(f"Error creating partner '{partner_in.name}': {e}", exc_info=True)
            raise
    
    async def update(
        self, *, db_partner: trading_partner.TradingPartner, partner_in: schemas.TradingPartnerUpdate
    ) -> trading_partner.TradingPartner:
        """
        Update a trading partner within the user's tenant.
        
        Args:
            db_partner: Existing partner to update
            partner_in: Update data
            
        Returns:
            Updated TradingPartner
        """
        try:
            # Validate tenant ownership
            self._validate_tenant_ownership(db_partner)
            
            sanitized_name = self._sanitize_partner_name(partner_in.name)
            
            logger.info(f"Updating partner id={db_partner.id} for tenant '{self.tenant_id}'.")
            
            # Check for name conflicts (excluding current partner)
            if sanitized_name != db_partner.name:
                existing = await self.get_by_name(name=sanitized_name)
                if existing and existing.id != db_partner.id:
                    raise ValueError(f"Partner with name '{sanitized_name}' already exists in your tenant")
            
            # Update basic fields
            partner_data_to_update = partner_in.model_dump(exclude_unset=True)
            db_partner.name = sanitized_name
            db_partner.description = partner_data_to_update.get("description", db_partner.description)
            
            # Update profiles if provided
            if "profiles" in partner_data_to_update:
                existing_profiles_map = {p.id: p for p in db_partner.profiles}
                updated_profiles = []
                
                for profile_in in partner_in.profiles:
                    if profile_in.id and profile_in.id in existing_profiles_map:
                        # Update existing profile
                        db_profile = existing_profiles_map[profile_in.id]
                        
                        # Validate profile belongs to same tenant
                        if db_profile.tenant_id != self.tenant_id:
                            raise TenantSecurityError("Profile belongs to different tenant")
                        
                        db_profile.name = profile_in.name
                        db_profile.implementation_guide = profile_in.implementation_guide
                        db_profile.validation_schema_name = profile_in.validation_schema_name
                        db_profile.priority = profile_in.priority
                        
                        self._sync_criteria(db_profile, profile_in.criteria)
                        updated_profiles.append(db_profile)
                    else:
                        # Create new profile
                        new_profile = partner_profile.PartnerProfile(
                            name=profile_in.name,
                            implementation_guide=profile_in.implementation_guide,
                            validation_schema_name=profile_in.validation_schema_name,
                            priority=profile_in.priority,
                            tenant_id=self.tenant_id,  # ✅ ALWAYS USER'S TENANT
                            criteria=[
                                profile_criterion.ProfileCriterion(
                                    tenant_id=self.tenant_id,  # ✅ ALWAYS USER'S TENANT
                                    **c.model_dump()
                                )
                                for c in profile_in.criteria
                            ]
                        )
                        updated_profiles.append(new_profile)
                
                db_partner.profiles = updated_profiles
            
            self.db.add(db_partner)
            await self.db.flush()
            
            self._log_operation(
                "update",
                partner_id=db_partner.id,
                status="SUCCESS",
                details={"partner_name": sanitized_name}
            )
            
            return db_partner
            
        except TenantSecurityError:
            raise
        except Exception as e:
            self._log_operation(
                "update",
                partner_id=db_partner.id,
                status="ERROR",
                details={"error": str(e)}
            )
            logger.error(f"Error updating partner {db_partner.id}: {e}", exc_info=True)
            raise
    
    def _sync_criteria(self, db_profile: partner_profile.PartnerProfile, 
                      criteria_in: List[schemas.ProfileCriterionUpdate]):
        """Helper to sync criteria for a given profile."""
        existing_criteria_map = {c.id: c for c in db_profile.criteria}
        updated_criteria = []
        
        for crit_in in criteria_in:
            if crit_in.id and crit_in.id in existing_criteria_map:
                # Update existing criterion
                db_crit = existing_criteria_map[crit_in.id]
                
                # Validate criterion belongs to same tenant
                if db_crit.tenant_id != self.tenant_id:
                    raise TenantSecurityError("Criterion belongs to different tenant")
                
                db_crit.field_source = crit_in.field_source
                db_crit.field_identifier = crit_in.field_identifier
                db_crit.operator = crit_in.operator
                db_crit.value = crit_in.value
                updated_criteria.append(db_crit)
            else:
                # Create new criterion
                new_crit = profile_criterion.ProfileCriterion(
                    tenant_id=self.tenant_id,  # ✅ ALWAYS USER'S TENANT
                    **crit_in.model_dump()
                )
                updated_criteria.append(new_crit)
        
        db_profile.criteria = updated_criteria
    
    async def delete(self, *, db_partner: trading_partner.TradingPartner) -> None:
        """
        Delete a trading partner from the user's tenant.
        
        Args:
            db_partner: Partner to delete
        """
        try:
            # Validate tenant ownership
            self._validate_tenant_ownership(db_partner)
            
            logger.info(f"Deleting partner id={db_partner.id} for tenant '{self.tenant_id}'.")
            
            await self.db.delete(db_partner)
            await self.db.flush()
            
            self._log_operation(
                "delete",
                partner_id=db_partner.id,
                status="SUCCESS",
                details={"partner_name": db_partner.name}
            )
            
        except TenantSecurityError:
            raise
        except Exception as e:
            self._log_operation(
                "delete",
                partner_id=db_partner.id,
                status="ERROR",
                details={"error": str(e)}
            )
            logger.error(f"Error deleting partner {db_partner.id}: {e}", exc_info=True)
            raise