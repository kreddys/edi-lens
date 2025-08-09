# FILE: backend/src/core/profile_matcher.py

import logging
import json
import fnmatch
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from src.models import partner_profile

logger = logging.getLogger(__name__)

# --- REMOVED: The EdiMetadata class is no longer needed for profile matching ---

class ProfileMatcher:
    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def get_profile_by_name(self, tenant_id: str, profile_name: str) -> Optional[partner_profile.PartnerProfile]:
        """
        Get a specific profile by name for a tenant.
        This is now the primary method for the API validation workflow.
        """
        query = (
            select(partner_profile.PartnerProfile)
            .filter_by(tenant_id=tenant_id, name=profile_name)
        )
        result = await self.db.execute(query)
        return result.scalars().first()

    async def list_tenant_profiles(self, tenant_id: str) -> List[partner_profile.PartnerProfile]:
        """List all profiles for a tenant, ordered by priority."""
        query = (
            select(partner_profile.PartnerProfile)
            .filter_by(tenant_id=tenant_id)
            .order_by(partner_profile.PartnerProfile.priority.asc())
        )
        result = await self.db.execute(query)
        return result.scalars().all()

    # --- REMOVED: The old EDI content-based match method is now gone ---

    async def match_by_filename(self, tenant_id: str, filename: str) -> Optional[partner_profile.PartnerProfile]:
        """
        Matches a filename to the highest-priority partner profile for a tenant
        based on the profile's file_name_patterns. This is used by the SFTP workflow.
        """
        all_profiles = await self.list_tenant_profiles(tenant_id)

        if not all_profiles:
            logger.info(f"No profiles configured for tenant '{tenant_id}'. Cannot match filename.")
            return None

        for profile in all_profiles:
            if not profile.file_name_patterns:
                continue
            
            try:
                patterns = json.loads(profile.file_name_patterns)
                if not isinstance(patterns, list):
                    logger.warning(f"file_name_patterns for profile {profile.id} is not a JSON list. Skipping.")
                    continue

                if any(fnmatch.fnmatch(filename, pattern) for pattern in patterns):
                    logger.info(f"Matched filename '{filename}' to profile '{profile.name}' (ID: {profile.id}) for tenant '{tenant_id}'.")
                    return profile
            except (json.JSONDecodeError, TypeError):
                logger.error(f"Could not parse file_name_patterns for profile {profile.id}: '{profile.file_name_patterns}'")

        logger.warning(f"No profile match found for filename '{filename}' in tenant '{tenant_id}'.")
        return None