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
    """Integration tests for enhanced PartnerProfile with database operations."""
    
    @pytest_asyncio.fixture
    async def sample_partner(self, db_session: AsyncSession):
        """Create a sample trading partner for testing."""
        partner = TradingPartner(
            tenant_id="test-tenant",
            name="Test Partner"
        )
        db_session.add(partner)
        await db_session.commit()
        await db_session.refresh(partner)
        return partner
    
    async def test_create_enhanced_partner_profile(self, db_session: AsyncSession, sample_partner):
        """Test creating a partner profile with enhanced validation configuration."""
        profile = PartnerProfile(
            tenant_id="test-tenant",
            partner_id=sample_partner.id,
            name="Enhanced Test Profile",
            implementation_guide="837P",
            snip_level="SNIP4",
            generate_ta1=False,
            generate_999=True,
            custom_validation_rules={"require_npi": True, "allow_test_mode": False}
        )
        
        db_session.add(profile)
        await db_session.commit()
        await db_session.refresh(profile)
        
        # Verify all fields were saved correctly
        assert profile.id is not None
        assert profile.name == "Enhanced Test Profile"
        assert profile.snip_level == "SNIP4"
        assert profile.generate_ta1 is False
        assert profile.generate_999 is True
        assert profile.custom_validation_rules == {"require_npi": True, "allow_test_mode": False}
        assert profile.created_at is not None
        assert profile.updated_at is None  # Only set on updates
    
    async def test_default_values_in_database(self, db_session: AsyncSession, sample_partner):
        """Test that default values are applied correctly in database."""
        profile = PartnerProfile(
            tenant_id="test-tenant",
            partner_id=sample_partner.id,
            name="Default Values Profile",
            implementation_guide="835"
            # Not specifying optional fields to test defaults
        )
        
        db_session.add(profile)
        await db_session.commit()
        await db_session.refresh(profile)
        
        # Verify defaults were applied by the database
        assert profile.snip_level == "SNIP3"
        assert profile.generate_ta1 is True
        assert profile.generate_999 is False
        assert profile.custom_validation_rules is None
        assert profile.priority == 10
        assert profile.snip_level_enabled == 1
    
    async def test_create_processing_log_with_profile_relationship(self, db_session: AsyncSession, sample_partner):
        """Test creating processing logs linked to partner profiles."""
        # Create a profile first
        profile = PartnerProfile(
            tenant_id="test-tenant",
            partner_id=sample_partner.id,
            name="Processing Log Test Profile",
            implementation_guide="837P",
            snip_level="SNIP3"
        )
        db_session.add(profile)
        await db_session.commit()
        await db_session.refresh(profile)
        
        # Create a processing log linked to the profile
        log = ProcessingLog(
            tenant_id="test-tenant",
            source="API",
            validation_result="VALID",
            snip_level_used="SNIP3",
            profile_id=profile.id,
            ta1_generated=True,
            original_content_path="tenant/api/original/test123.edi",
            ta1_content_path="tenant/api/responses/ta1_test123.edi"
        )
        
        db_session.add(log)
        await db_session.commit()
        await db_session.refresh(log)
        
        # Verify the log was created with correct values
        assert log.id is not None
        assert log.profile_id == profile.id
        assert log.snip_level_used == "SNIP3"
        assert log.ta1_generated is True
        assert log.ta1_999_generated is False  # Default
        assert log.error_count == 0  # Default
        assert log.timestamp is not None
    
    async def test_query_profiles_with_processing_logs(self, db_session: AsyncSession, sample_partner):
        """Test querying profiles with their associated processing logs."""
        # Create profile
        profile = PartnerProfile(
            tenant_id="test-tenant",
            partner_id=sample_partner.id,
            name="Query Test Profile",
            implementation_guide="837P"
        )
        db_session.add(profile)
        await db_session.commit()
        await db_session.refresh(profile)
        
        # Create multiple processing logs
        logs = [
            ProcessingLog(
                tenant_id="test-tenant",
                source="API",
                validation_result="VALID",
                profile_id=profile.id,
                snip_level_used="SNIP3"
            ),
            ProcessingLog(
                tenant_id="test-tenant",
                source="SFTP",
                validation_result="INVALID",
                profile_id=profile.id,
                snip_level_used="SNIP3",
                error_count=2
            )
        ]
        
        for log in logs:
            db_session.add(log)
        await db_session.commit()
        
        # Query profile with processing logs
        query = (
            select(PartnerProfile)
            .filter_by(id=profile.id)
        )
        result = await db_session.execute(query)
        retrieved_profile = result.scalar_one()
        
        assert retrieved_profile.name == "Query Test Profile"
        # Note: We don't eagerly load processing_logs in this simple query,
        # but the relationship exists and can be accessed
    
    async def test_update_profile_with_new_validation_config(self, db_session: AsyncSession, sample_partner):
        """Test updating a profile's validation configuration."""
        # Create initial profile
        profile = PartnerProfile(
            tenant_id="test-tenant",
            partner_id=sample_partner.id,
            name="Update Test Profile",
            implementation_guide="837P",
            snip_level="SNIP1",
            generate_ta1=True,
            generate_999=False
        )
        db_session.add(profile)
        await db_session.commit()
        await db_session.refresh(profile)
        
        original_created_at = profile.created_at
        
        # Update validation configuration
        profile.snip_level = "SNIP5"
        profile.generate_ta1 = False
        profile.generate_999 = True
        profile.custom_validation_rules = {"strict_mode": True}
        
        await db_session.commit()
        await db_session.refresh(profile)
        
        # Verify updates
        assert profile.snip_level == "SNIP5"
        assert profile.generate_ta1 is False
        assert profile.generate_999 is True
        assert profile.custom_validation_rules == {"strict_mode": True}
        assert profile.created_at == original_created_at  # Unchanged
        assert profile.updated_at is not None  # Should be set on update