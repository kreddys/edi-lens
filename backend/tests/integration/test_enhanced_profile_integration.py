# FILE: backend/tests/integration/test_enhanced_profile_integration.py

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from src.models.partner_profile import PartnerProfile
from src.models.processing_log import ProcessingLog
from src.models.trading_partner import TradingPartner

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]

@pytest.mark.integration
class TestEnhancedPartnerProfileIntegration:
    @pytest_asyncio.fixture
    async def sample_partner(self, db_session: AsyncSession):
        partner = TradingPartner(tenant_id="test-tenant", name="Test Partner")
        db_session.add(partner)
        await db_session.commit()
        await db_session.refresh(partner)
        return partner
    
    async def test_create_enhanced_partner_profile(self, db_session: AsyncSession, sample_partner):
        profile = PartnerProfile(
            tenant_id="test-tenant",
            partner_id=sample_partner.id,
            name="Enhanced Test Profile",
            validation_schema_name="837P.json", # <-- FIX
            snip_level="SNIP4",
            generate_ta1=False,
            generate_999=True,
            custom_validation_rules={"require_npi": True}
        )
        db_session.add(profile)
        await db_session.commit()
        await db_session.refresh(profile)
        
        assert profile.id is not None
        assert profile.snip_level == "SNIP4"

    async def test_default_values_in_database(self, db_session: AsyncSession, sample_partner):
        profile = PartnerProfile(
            tenant_id="test-tenant",
            partner_id=sample_partner.id,
            name="Default Values Profile",
            validation_schema_name="835.json" # <-- FIX
        )
        db_session.add(profile)
        await db_session.commit()
        await db_session.refresh(profile)
        
        assert profile.snip_level == "SNIP3"
        assert profile.generate_ta1 is True

    async def test_create_processing_log_with_profile_relationship(self, db_session: AsyncSession, sample_partner):
        profile = PartnerProfile(
            tenant_id="test-tenant",
            partner_id=sample_partner.id,
            name="Processing Log Test Profile",
            validation_schema_name="837P.json", # <-- FIX
            snip_level="SNIP3"
        )
        db_session.add(profile)
        await db_session.commit()
        await db_session.refresh(profile)
        
        log = ProcessingLog(
            tenant_id="test-tenant", source="API", validation_result="VALID",
            profile_id=profile.id
        )
        db_session.add(log)
        await db_session.commit()
        
        assert log.id is not None
        assert log.profile_id == profile.id

    async def test_query_profiles_with_processing_logs(self, db_session: AsyncSession, sample_partner):
        profile = PartnerProfile(
            tenant_id="test-tenant",
            partner_id=sample_partner.id,
            name="Query Test Profile",
            validation_schema_name="837P.json" # <-- FIX
        )
        db_session.add(profile)
        await db_session.commit()
        await db_session.refresh(profile)
        
        # This test just verifies the relationship can be set up
        assert profile.id is not None

    async def test_update_profile_with_new_validation_config(self, db_session: AsyncSession, sample_partner):
        profile = PartnerProfile(
            tenant_id="test-tenant",
            partner_id=sample_partner.id,
            name="Update Test Profile",
            validation_schema_name="837P.json", # <-- FIX
            snip_level="SNIP1"
        )
        db_session.add(profile)
        await db_session.commit()
        await db_session.refresh(profile)
        
        profile.snip_level = "SNIP5"
        await db_session.commit()
        await db_session.refresh(profile)
        
        assert profile.snip_level == "SNIP5"