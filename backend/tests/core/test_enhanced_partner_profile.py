# FILE: backend/tests/core/test_enhanced_partner_profile.py

import pytest
from src.models.partner_profile import PartnerProfile
from src.models.processing_log import ProcessingLog

pytestmark = [pytest.mark.unit]

class TestEnhancedPartnerProfile:
    """Unit tests for enhanced PartnerProfile model with validation configuration."""
    
    def test_default_validation_configuration(self):
        """Test that PartnerProfile has proper default validation settings."""
        # --- THIS IS THE FIX ---
        # Replace 'implementation_guide' with the required 'validation_schema_name'.
        profile = PartnerProfile(
            tenant_id="test-tenant",
            partner_id=1,
            name="Test Profile",
            validation_schema_name="837p.json"
        )
        # --- END OF FIX ---
        
        assert profile.snip_level == "SNIP3"
        assert profile.generate_ta1 is True
        assert profile.generate_999 is False
        assert profile.custom_validation_rules is None
    
    def test_custom_validation_configuration(self):
        """Test PartnerProfile with custom validation settings."""
        custom_rules = {"require_npi": True, "allow_test_mode": False}
        
        profile = PartnerProfile(
            tenant_id="test-tenant",
            partner_id=2,
            name="Custom Profile",
            validation_schema_name="835.json", # <-- FIX
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
                validation_schema_name="837p.json", # <-- FIX
                snip_level=snip_level
            )
            assert profile.snip_level == snip_level
    
    def test_processing_logs_relationship(self):
        """Test that PartnerProfile can be related to ProcessingLog instances."""
        profile = PartnerProfile(
            tenant_id="test-tenant",
            partner_id=1,
            name="Test Profile",
            validation_schema_name="837p.json" # <-- FIX
        )
        
        processing_log = ProcessingLog(
            tenant_id="test-tenant", source="API", validation_result="VALID",
            snip_level_used="SNIP3", profile_id=1
        )
        
        assert hasattr(profile, 'processing_logs')
        assert hasattr(processing_log, 'profile')
    
    def test_repr_method(self):
        """Test the enhanced __repr__ method."""
        profile = PartnerProfile(
            id=42, tenant_id="test-tenant", partner_id=1, name="Test Profile",
            validation_schema_name="837p.json", # <-- FIX
            snip_level="SNIP4", generate_ta1=False, generate_999=True
        )
        
        repr_str = repr(profile)
        assert "Test Profile" in repr_str
        assert "SNIP4" in repr_str
        assert "ta1=False" in repr_str
    
    def test_validation_configuration_combinations(self):
        """Test various combinations of TA1/999 generation settings."""
        test_cases = [(True, False), (False, True), (True, True), (False, False)]
        
        for ta1, ta1_999 in test_cases:
            profile = PartnerProfile(
                tenant_id="test-tenant", partner_id=1,
                name=f"Profile TA1:{ta1} 999:{ta1_999}",
                validation_schema_name="837p.json", # <-- FIX
                generate_ta1=ta1, generate_999=ta1_999
            )
            assert profile.generate_ta1 == ta1
            assert profile.generate_999 == ta1_999
    
    def test_custom_validation_rules_json(self):
        """Test that custom validation rules can handle complex JSON structures."""
        complex_rules = { "business_rules": [{"rule_id": "BR001"}] }
        
        profile = PartnerProfile(
            tenant_id="test-tenant", partner_id=1,
            name="Complex Rules Profile",
            validation_schema_name="837p.json", # <-- FIX
            custom_validation_rules=complex_rules
        )
        
        assert profile.custom_validation_rules == complex_rules

# --- The TestProcessingLog class is unaffected and correct as is ---
class TestProcessingLog:
    """Unit tests for the new ProcessingLog model."""
    
    def test_default_processing_log(self):
        log = ProcessingLog(tenant_id="test-tenant", source="API", validation_result="VALID")
        assert log.error_count == 0
    
    def test_processing_log_with_file_info(self):
        log = ProcessingLog(
            tenant_id="test-tenant", source="SFTP", validation_result="INVALID",
            file_name="test_837.edi", file_size_bytes=1024, error_count=3
        )
        assert log.file_name == "test_837.edi"
    
    def test_processing_log_with_acknowledgments(self):
        log = ProcessingLog(
            tenant_id="test-tenant", source="API", validation_result="VALID",
            snip_level_used="SNIP3", ta1_generated=True,
            original_content_path="path/to/original"
        )
        assert log.ta1_generated is True
    
    def test_processing_log_repr(self):
        log = ProcessingLog(id=123, tenant_id="test-tenant", source="SFTP", validation_result="ERROR")
        assert "id=123" in repr(log)
    
    def test_processing_source_types(self):
        log = ProcessingLog(tenant_id="test-tenant", source="MANUAL", validation_result="VALID")
        assert log.source == "MANUAL"
    
    def test_validation_result_types(self):
        log = ProcessingLog(tenant_id="test-tenant", source="API", validation_result="INVALID")
        assert log.validation_result == "INVALID"