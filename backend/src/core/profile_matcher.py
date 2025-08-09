import logging
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from src.models import partner_profile
from src.models.profile_criterion import FieldSource, Operator

logger = logging.getLogger(__name__)

class EdiMetadata:
    """
    A DTO that performs a robust, non-validating parse of EDI headers
    to extract metadata needed for profile matching. It correctly handles
    dynamic delimiters defined in the ISA segment.
    """
    def __init__(self, edi_string: str):
        self.isa_segments: List[str] = []
        self.gs_segments: List[str] = []
        
        try:
            clean_edi = edi_string.strip()
            if not (clean_edi.startswith('ISA') and len(clean_edi) >= 106):
                logger.warning("EDI data does not start with a valid ISA segment. Cannot perform profile matching.")
                return

            element_delimiter = clean_edi[3]
            segment_terminator = clean_edi[105]

            if segment_terminator in ('\r', '\n'):
                raw_segments = [seg.rstrip(segment_terminator) for seg in clean_edi.splitlines()]
            else:
                raw_segments = clean_edi.split(segment_terminator)

            for seg_str in raw_segments:
                if not seg_str:
                    continue
                
                clean_seg_str = seg_str.strip()
                parts = clean_seg_str.split(element_delimiter)
                
                if not parts:
                    continue
                
                seg_id = parts[0]
                if seg_id == 'ISA' and not self.isa_segments:
                    self.isa_segments = parts
                elif seg_id == 'GS' and not self.gs_segments:
                    self.gs_segments = parts
                
                if self.isa_segments and self.gs_segments:
                    break
        except Exception:
            logger.warning("Could not parse EDI headers for profile matching.", exc_info=True)

    def get_value(self, source: FieldSource, identifier: str) -> Optional[str]:
        try:
            idx = int(identifier)
            if source == FieldSource.ISA and len(self.isa_segments) > idx:
                # --- THIS IS THE FIX ---
                # Remove .strip(). ISA fields are fixed-width and comparisons must be exact.
                return self.isa_segments[idx]
            if source == FieldSource.GS and len(self.gs_segments) > idx:
                # GS fields are variable-length, but stripping here is also risky.
                # The matching logic should handle exact values.
                return self.gs_segments[idx]
                # --- END OF FIX ---
        except (ValueError, IndexError):
            return None
        return None

class ProfileMatcher:
    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def get_profile_by_name(self, tenant_id: str, profile_name: str) -> Optional[partner_profile.PartnerProfile]:
        """Get a specific profile by name for a tenant."""
        query = (
            select(partner_profile.PartnerProfile)
            .options(selectinload(partner_profile.PartnerProfile.criteria))
            .filter_by(tenant_id=tenant_id, name=profile_name)
        )
        result = await self.db.execute(query)
        return result.scalars().first()

    async def list_tenant_profiles(self, tenant_id: str) -> List[partner_profile.PartnerProfile]:
        """List all profiles for a tenant."""
        query = (
            select(partner_profile.PartnerProfile)
            .options(selectinload(partner_profile.PartnerProfile.criteria))
            .filter_by(tenant_id=tenant_id)
            .order_by(partner_profile.PartnerProfile.priority.asc())
        )
        result = await self.db.execute(query)
        return result.scalars().all()

    async def match(self, edi_string: str, tenant_id: str) -> Optional[partner_profile.PartnerProfile]:
        """
        Matches an EDI string to the highest-priority partner profile for a tenant.
        """
        edi_meta = EdiMetadata(edi_string)
        
        query = (
            select(partner_profile.PartnerProfile)
            .options(selectinload(partner_profile.PartnerProfile.criteria))
            .filter_by(tenant_id=tenant_id)
            .order_by(partner_profile.PartnerProfile.priority.asc())
        )
        result = await self.db.execute(query)
        all_profiles = result.scalars().all()

        if not all_profiles:
            logger.info(f"No profiles configured for tenant '{tenant_id}'. Using default validation.")
            return None

        for profile in all_profiles:
            if self._does_profile_match(profile, edi_meta):
                logger.info(f"Matched EDI to profile '{profile.name}' (ID: {profile.id}) for tenant '{tenant_id}'.")
                return profile
        
        logger.info(f"No specific profile matched for tenant '{tenant_id}'. Using default validation.")
        return None

    def _does_profile_match(self, profile: partner_profile.PartnerProfile, edi_meta: EdiMetadata) -> bool:
        if not profile.criteria:
            return True

        for criterion in profile.criteria:
            value_from_edi = edi_meta.get_value(criterion.field_source, criterion.field_identifier)
            if value_from_edi is None:
                return False

            match = False
            # The criterion value should be an exact match, including any padding.
            if criterion.operator == Operator.EQUALS:
                match = value_from_edi == criterion.value
            elif criterion.operator == Operator.STARTS_WITH:
                match = value_from_edi.startswith(criterion.value)
            elif criterion.operator == Operator.CONTAINS:
                match = criterion.value in value_from_edi
            
            if not match:
                return False
        
        return True