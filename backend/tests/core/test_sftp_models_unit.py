import pytest
from datetime import datetime, timedelta

from src.models.sftp_configuration import AuthenticationType
from src.models.file_processing_log import FileProcessingStatus, FileProcessingLog
from src.models.validation_transaction import SourceType, ValidationStatus
from src.models.processing_schedule import get_default_schedules

pytestmark = pytest.mark.unit


def test_authentication_type_enum():
    """Test AuthenticationType enum values"""
    assert AuthenticationType.PASSWORD.value == "PASSWORD"
    assert AuthenticationType.SSH_KEY.value == "SSH_KEY"
    assert AuthenticationType.BOTH.value == "BOTH"


def test_file_processing_status_enum():
    """Test FileProcessingStatus enum values"""
    assert FileProcessingStatus.DISCOVERED.value == "DISCOVERED"
    assert FileProcessingStatus.LOCKED.value == "LOCKED"
    assert FileProcessingStatus.PROCESSING.value == "PROCESSING"
    assert FileProcessingStatus.COMPLETED.value == "COMPLETED"
    assert FileProcessingStatus.FAILED.value == "FAILED"
    assert FileProcessingStatus.ARCHIVED.value == "ARCHIVED"
    assert FileProcessingStatus.RESPONSE_PENDING.value == "RESPONSE_PENDING"
    assert FileProcessingStatus.RESPONSE_DELIVERED.value == "RESPONSE_DELIVERED"
    assert FileProcessingStatus.RESPONSE_FAILED.value == "RESPONSE_FAILED"


def test_source_type_enum():
    """Test SourceType enum values"""
    assert SourceType.API.value == "API"
    assert SourceType.SFTP.value == "SFTP"
    assert SourceType.MANUAL.value == "MANUAL"


def test_validation_status_enum():
    """Test ValidationStatus enum values (existing)"""
    assert ValidationStatus.PENDING.value == "PENDING"
    assert ValidationStatus.COMPLETE.value == "COMPLETE"
    assert ValidationStatus.FAILED.value == "FAILED"


def test_get_default_schedules():
    """Test that default schedules are properly defined"""
    schedules = get_default_schedules()
    
    assert len(schedules) == 6
    
    # Check that all required fields are present
    for schedule in schedules:
        assert 'name' in schedule
        assert 'description' in schedule
        assert 'cron_expression' in schedule
        assert 'is_active' in schedule
        assert schedule['is_active'] is True
    
    # Check specific schedules
    schedule_names = [s['name'] for s in schedules]
    expected_names = [
        'Every 5 minutes',
        'Every 15 minutes', 
        'Every hour',
        'Business hours only',
        'Once daily at 9 AM',
        'Manual only'
    ]
    
    for name in expected_names:
        assert name in schedule_names
    
    # Check specific cron expressions
    five_min_schedule = next(s for s in schedules if s['name'] == 'Every 5 minutes')
    assert five_min_schedule['cron_expression'] == '*/5 * * * *'
    
    manual_schedule = next(s for s in schedules if s['name'] == 'Manual only')
    assert manual_schedule['cron_expression'] == ''


class TestFileProcessingLogBusinessLogic:
    """Test business logic methods on FileProcessingLog model"""
    
    def test_can_retry_default(self):
        """Test can_retry with default values"""
        log = FileProcessingLog()
        assert log.retry_count == 0
        assert log.max_retries == 3
        assert log.can_retry is True
    
    def test_can_retry_at_limit(self):
        """Test can_retry when at retry limit"""
        log = FileProcessingLog()
        log.retry_count = 3
        log.max_retries = 3
        assert log.can_retry is False
    
    def test_can_retry_over_limit(self):
        """Test can_retry when over retry limit"""
        log = FileProcessingLog()
        log.retry_count = 5
        log.max_retries = 3
        assert log.can_retry is False
    
    def test_processing_duration_seconds_not_started(self):
        """Test processing duration when not started"""
        log = FileProcessingLog()
        assert log.processing_duration_seconds == 0
    
    def test_processing_duration_seconds_not_completed(self):
        """Test processing duration when started but not completed"""
        log = FileProcessingLog()
        log.processing_started_at = datetime.utcnow()
        assert log.processing_duration_seconds == 0
    
    def test_processing_duration_seconds_completed(self):
        """Test processing duration when completed"""
        log = FileProcessingLog()
        start_time = datetime.utcnow()
        end_time = start_time + timedelta(seconds=45)
        
        log.processing_started_at = start_time
        log.processing_completed_at = end_time
        
        assert log.processing_duration_seconds == 45
    
    def test_processing_duration_seconds_fractional(self):
        """Test processing duration with fractional seconds"""
        log = FileProcessingLog()
        start_time = datetime.utcnow()
        end_time = start_time + timedelta(seconds=30, microseconds=750000)  # 30.75 seconds
        
        log.processing_started_at = start_time
        log.processing_completed_at = end_time
        
        # Should truncate to 30 seconds (int conversion)
        assert log.processing_duration_seconds == 30


class TestFileProcessingLogDefaults:
    """Test default values for FileProcessingLog model"""
    
    def test_default_values(self):
        """Test that FileProcessingLog has correct default values"""
        log = FileProcessingLog()
        
        assert log.status == FileProcessingStatus.DISCOVERED.value
        assert log.retry_count == 0
        assert log.max_retries == 3
        assert log.response_delivery_attempts == 0
        
        # These should be None by default
        assert log.processing_started_at is None
        assert log.processing_completed_at is None
        assert log.locked_by is None
        assert log.locked_at is None
        assert log.lock_expires_at is None
        assert log.response_filename is None
        assert log.response_directory is None
        assert log.response_delivered_at is None
        assert log.error_message is None
        assert log.archived_at is None
        assert log.archive_location is None


class TestFileProcessingLogValidation:
    """Test validation logic for FileProcessingLog"""
    
    def test_required_fields(self):
        """Test that required fields are properly set"""
        log = FileProcessingLog(
            tenant_id="test-tenant",
            partner_id=1,
            sftp_config_id=1,
            source_filename="test.x12",
            source_directory="/inbound"
        )
        
        assert log.tenant_id == "test-tenant"
        assert log.partner_id == 1
        assert log.sftp_config_id == 1
        assert log.source_filename == "test.x12"
        assert log.source_directory == "/inbound"
    
    def test_optional_fields(self):
        """Test that optional fields can be set"""
        log = FileProcessingLog(
            tenant_id="test-tenant",
            partner_id=1,
            sftp_config_id=1,
            source_filename="test.x12",
            source_directory="/inbound",
            source_file_size=1024,
            source_file_hash="abc123",
            error_message="Test error"
        )
        
        assert log.source_file_size == 1024
        assert log.source_file_hash == "abc123"
        assert log.error_message == "Test error"