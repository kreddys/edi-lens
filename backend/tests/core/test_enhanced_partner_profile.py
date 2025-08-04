import pytest
from datetime import datetime
from src.models.partner_profile import PartnerProfile
from src.models.processing_log import ProcessingLog


@pytest.mark.unit
class TestEnhancedPartnerProfile:
    """Unit tests for enhanced PartnerProfile model with validation configuration."""
    
    def test_default_validation_configuration(self):
        """Test that PartnerProfile has proper default validation settings."""
        profile = PartnerProfile(
            tenant_id="test-tenant",
            partner_id=1,
            name="Test Profile",
            implementation_guide="837P"
        )
        
        # Test default validation configuration
        assert profile.snip_level == "SNIP3"
        assert profile.generate_ta1 is True
        assert profile.generate_999 is False
        assert profile.custom_validation_rules is None
        
        # Test legacy compatibility defaults
        assert profile.priority == 10
        assert profile.snip_level_enabled == 1
    
    def test_custom_validation_configuration(self):
        """Test PartnerProfile with custom validation settings."""
        custom_rules = {"require_837p_batch_control": True, "allow_test_isa": False}
        
        profile = PartnerProfile(
            tenant_id="test-tenant",
            partner_id=2,
            name="Custom Profile",
            implementation_guide="835",
            snip_level="SNIP5",
            generate_ta1=False,
            generate_999=True,
            custom_validation_rules=custom_rules
        )
        
        assert profile.snip_level == "SNIP5"
        assert profile.generate_ta1 is False
        assert profile.generate_999 is True
        assert profile.custom_validation_rules == custom_rules
    
    def test_snip_level_values(self):
        """Test different SNIP level values."""
        valid_snip_levels = ["SNIP1", "SNIP2", "SNIP3", "SNIP4", "SNIP5"]
        
        for snip_level in valid_snip_levels:
            profile = PartnerProfile(
                tenant_id="test-tenant",
                partner_id=1,
                name=f"Profile {snip_level}",
                implementation_guide="837P",
                snip_level=snip_level
            )
            assert profile.snip_level == snip_level
    
    def test_processing_logs_relationship(self):
        """Test that PartnerProfile can be related to ProcessingLog instances."""
        profile = PartnerProfile(
            tenant_id="test-tenant",
            partner_id=1,
            name="Test Profile",
            implementation_guide="837P"
        )
        
        # Create a processing log (without database, just model relationship)
        processing_log = ProcessingLog(
            tenant_id="test-tenant",
            source="API",
            validation_result="VALID",
            snip_level_used="SNIP3",
            profile_id=1  # Would be set by database relationship
        )
        
        # Test that the relationship attribute exists
        assert hasattr(profile, 'processing_logs')
        assert hasattr(processing_log, 'profile')
    
    def test_repr_method(self):
        """Test the enhanced __repr__ method."""
        profile = PartnerProfile(
            id=42,
            tenant_id="test-tenant",
            partner_id=1,
            name="Test Profile",
            implementation_guide="837P",
            snip_level="SNIP4",
            generate_ta1=False,
            generate_999=True
        )
        
        repr_str = repr(profile)
        assert "Test Profile" in repr_str
        assert "SNIP4" in repr_str
        assert "ta1=False" in repr_str
        assert "ta1_999=True" in repr_str
        assert "id=42" in repr_str
    
    def test_validation_configuration_combinations(self):
        """Test various combinations of TA1/999 generation settings."""
        test_cases = [
            (True, False),   # TA1 only (default)
            (False, True),   # 999 only
            (True, True),    # Both
            (False, False),  # Neither
        ]
        
        for ta1, ta1_999 in test_cases:
            profile = PartnerProfile(
                tenant_id="test-tenant",
                partner_id=1,
                name=f"Profile TA1:{ta1} 999:{ta1_999}",
                implementation_guide="837P",
                generate_ta1=ta1,
                generate_999=ta1_999
            )
            
            assert profile.generate_ta1 == ta1
            assert profile.generate_999 == ta1_999
    
    def test_custom_validation_rules_json(self):
        """Test that custom validation rules can handle complex JSON structures."""
        complex_rules = {
            "snip_overrides": {
                "SNIP1": {"allow_empty_segments": True},
                "SNIP3": {"require_all_elements": False}
            },
            "business_rules": [
                {"rule_id": "BR001", "description": "Validate provider NPI"},
                {"rule_id": "BR002", "description": "Check claim totals"}
            ],
            "format_preferences": {
                "decimal_precision": 2,
                "date_format": "CCYYMMDD",
                "allow_leading_zeros": True
            }
        }
        
        profile = PartnerProfile(
            tenant_id="test-tenant",
            partner_id=1,
            name="Complex Rules Profile",
            implementation_guide="837P",
            custom_validation_rules=complex_rules
        )
        
        assert profile.custom_validation_rules == complex_rules
        assert "snip_overrides" in profile.custom_validation_rules
        assert len(profile.custom_validation_rules["business_rules"]) == 2


@pytest.mark.unit
class TestProcessingLog:
    """Unit tests for the new ProcessingLog model."""
    
    def test_default_processing_log(self):
        """Test ProcessingLog with default values."""
        log = ProcessingLog(
            tenant_id="test-tenant",
            source="API",
            validation_result="VALID"
        )
        
        assert log.tenant_id == "test-tenant"
        assert log.source == "API"
        assert log.validation_result == "VALID"
        assert log.error_count == 0
        assert log.ta1_generated is False
        assert log.ta1_999_generated is False
    
    def test_processing_log_with_file_info(self):
        """Test ProcessingLog with file information."""
        log = ProcessingLog(
            tenant_id="test-tenant",
            source="SFTP",
            validation_result="INVALID",
            file_name="test_837.edi",
            file_size_bytes=1024,
            error_count=3,
            processing_time_ms=150
        )
        
        assert log.source == "SFTP"
        assert log.file_name == "test_837.edi"
        assert log.file_size_bytes == 1024
        assert log.error_count == 3
        assert log.processing_time_ms == 150
    
    def test_processing_log_with_acknowledgments(self):
        """Test ProcessingLog with acknowledgment generation flags."""
        log = ProcessingLog(
            tenant_id="test-tenant",
            source="API",
            validation_result="VALID",
            snip_level_used="SNIP3",
            ta1_generated=True,
            ta1_999_generated=False,
            original_content_path="tenant/api/original/file123.edi",
            ta1_content_path="tenant/api/responses/ta1_file123.edi"
        )
        
        assert log.snip_level_used == "SNIP3"
        assert log.ta1_generated is True
        assert log.ta1_999_generated is False
        assert log.original_content_path == "tenant/api/original/file123.edi"
        assert log.ta1_content_path == "tenant/api/responses/ta1_file123.edi"
        assert log.ta1_999_content_path is None
    
    def test_processing_log_repr(self):
        """Test ProcessingLog __repr__ method."""
        log = ProcessingLog(
            id=123,
            tenant_id="test-tenant",
            source="SFTP",
            validation_result="ERROR",
            snip_level_used="SNIP2"
        )
        
        repr_str = repr(log)
        assert "id=123" in repr_str
        assert "tenant='test-tenant'" in repr_str
        assert "source='SFTP'" in repr_str
        assert "result='ERROR'" in repr_str
        assert "snip_level='SNIP2'" in repr_str
    
    def test_processing_source_types(self):
        """Test different processing source types."""
        sources = ["API", "SFTP", "MANUAL"]
        
        for source in sources:
            log = ProcessingLog(
                tenant_id="test-tenant",
                source=source,
                validation_result="VALID"
            )
            assert log.source == source
    
    def test_validation_result_types(self):
        """Test different validation result types."""
        results = ["VALID", "INVALID", "ERROR"]
        
        for result in results:
            log = ProcessingLog(
                tenant_id="test-tenant",
                source="API",
                validation_result=result
            )
            assert log.validation_result == result