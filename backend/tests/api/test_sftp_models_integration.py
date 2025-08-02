import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.models.trading_partner import TradingPartner
from src.models.processing_schedule import ProcessingSchedule
from src.models.sftp_configuration import SftpConfiguration, AuthenticationType
from src.models.file_processing_log import FileProcessingLog, FileProcessingStatus
from src.models.validation_transaction import ValidationTransaction, SourceType, ValidationStatus

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


@pytest_asyncio.fixture
async def sample_partner(db_session: AsyncSession) -> TradingPartner:
    """Create a sample trading partner for testing"""
    partner = TradingPartner(
        tenant_id="test-tenant",
        name="Test Partner",
        description="Partner for SFTP testing"
    )
    db_session.add(partner)
    await db_session.commit()
    await db_session.refresh(partner)
    return partner


@pytest_asyncio.fixture
async def sample_schedule(db_session: AsyncSession) -> ProcessingSchedule:
    """Create a sample processing schedule for testing"""
    schedule = ProcessingSchedule(
        name="Test Schedule",
        description="Test every 5 minutes",
        cron_expression="*/5 * * * *",
        is_active=True
    )
    db_session.add(schedule)
    await db_session.commit()
    await db_session.refresh(schedule)
    return schedule


async def test_processing_schedule_creation(db_session: AsyncSession):
    """Test creating a processing schedule"""
    schedule = ProcessingSchedule(
        name="Hourly",
        description="Run every hour",
        cron_expression="0 * * * *",
        is_active=True
    )
    
    db_session.add(schedule)
    await db_session.commit()
    await db_session.refresh(schedule)
    
    assert schedule.id is not None
    assert schedule.name == "Hourly"
    assert schedule.cron_expression == "0 * * * *"
    assert schedule.is_active is True
    assert schedule.created_at is not None


async def test_sftp_configuration_creation(db_session: AsyncSession, sample_partner: TradingPartner, sample_schedule: ProcessingSchedule):
    """Test creating an SFTP configuration"""
    config = SftpConfiguration(
        tenant_id=sample_partner.tenant_id,
        partner_id=sample_partner.id,
        sftp_enabled=True,
        sftp_username="testuser",
        authentication_type=AuthenticationType.PASSWORD.value,
        password_hash="hashed_password_123",
        inbound_directory="/partners/test/inbound",
        outbound_directory="/partners/test/outbound",
        archive_directory="/partners/test/archive",
        file_name_patterns='["*.x12", "*.edi"]',
        poll_schedule_id=sample_schedule.id,
        poll_enabled=True,
        response_filename_template="{original_name}_ack",
        response_timeout_minutes=10,
        max_file_size_bytes=104857600  # 100MB
    )
    
    db_session.add(config)
    await db_session.commit()
    await db_session.refresh(config)
    
    assert config.id is not None
    assert config.partner_id == sample_partner.id
    assert config.sftp_username == "testuser"
    assert config.authentication_type == AuthenticationType.PASSWORD.value
    assert config.inbound_directory == "/partners/test/inbound"
    assert config.max_file_size_bytes == 104857600
    assert config.created_at is not None


async def test_sftp_configuration_ssh_key_auth(db_session: AsyncSession, sample_partner: TradingPartner):
    """Test SFTP configuration with SSH key authentication"""
    config = SftpConfiguration(
        tenant_id=sample_partner.tenant_id,
        partner_id=sample_partner.id,
        sftp_enabled=True,
        sftp_username="testuser",
        authentication_type=AuthenticationType.SSH_KEY.value,
        ssh_public_key="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQ...",
        inbound_directory="/partners/test/inbound",
        outbound_directory="/partners/test/outbound",
        poll_enabled=False  # Manual only
    )
    
    db_session.add(config)
    await db_session.commit()
    await db_session.refresh(config)
    
    assert config.authentication_type == AuthenticationType.SSH_KEY.value
    assert config.ssh_public_key is not None
    assert config.password_hash is None
    assert config.poll_enabled is False


async def test_file_processing_log_creation(db_session: AsyncSession, sample_partner: TradingPartner):
    """Test creating a file processing log entry"""
    # First create an SFTP config
    config = SftpConfiguration(
        tenant_id=sample_partner.tenant_id,
        partner_id=sample_partner.id,
        sftp_enabled=True,
        sftp_username="testuser",
        inbound_directory="/partners/test/inbound",
        outbound_directory="/partners/test/outbound"
    )
    db_session.add(config)
    await db_session.commit()
    await db_session.refresh(config)
    
    # Create processing log
    log = FileProcessingLog(
        tenant_id=sample_partner.tenant_id,
        partner_id=sample_partner.id,
        sftp_config_id=config.id,
        source_filename="test_file.x12",
        source_directory="/partners/test/inbound",
        source_file_size=1024,
        source_file_hash="abc123",
        status=FileProcessingStatus.DISCOVERED.value
    )
    
    db_session.add(log)
    await db_session.commit()
    await db_session.refresh(log)
    
    assert log.id is not None
    assert log.source_filename == "test_file.x12"
    assert log.status == FileProcessingStatus.DISCOVERED.value
    assert log.retry_count == 0
    assert log.max_retries == 3
    assert log.created_at is not None


async def test_validation_transaction_sftp_fields(db_session: AsyncSession, sample_partner: TradingPartner):
    """Test validation transaction with SFTP-specific fields"""
    transaction = ValidationTransaction(
        tenant_id=sample_partner.tenant_id,
        user_id="system",
        username="sftp-processor",
        original_filename="test_file.x12",
        request_object_key="tenant/partner/123/request.edi",
        source_type=SourceType.SFTP,
        source_partner_id=sample_partner.id,
        source_file_path="/partners/test/inbound/test_file.x12",
        status=ValidationStatus.COMPLETE
    )
    
    db_session.add(transaction)
    await db_session.commit()
    await db_session.refresh(transaction)
    
    assert transaction.id is not None
    assert transaction.source_type == SourceType.SFTP
    assert transaction.source_partner_id == sample_partner.id
    assert transaction.source_file_path == "/partners/test/inbound/test_file.x12"
    assert transaction.response_delivered is False
    assert transaction.response_delivery_attempts == 0
    assert transaction.created_at is not None


async def test_partner_sftp_configuration_relationship(db_session: AsyncSession, sample_partner: TradingPartner):
    """Test the relationship between trading partner and SFTP configuration"""
    config = SftpConfiguration(
        tenant_id=sample_partner.tenant_id,
        partner_id=sample_partner.id,
        sftp_enabled=True,
        sftp_username="testuser",
        inbound_directory="/partners/test/inbound",
        outbound_directory="/partners/test/outbound"
    )
    
    db_session.add(config)
    await db_session.commit()
    
    # Refresh partner to load relationships
    await db_session.refresh(sample_partner)
    
    # Query the relationship using the async session to avoid greenlet issues
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    
    # Load partner with SFTP configuration relationship
    result = await db_session.execute(
        select(TradingPartner)
        .options(selectinload(TradingPartner.sftp_configuration))
        .where(TradingPartner.id == sample_partner.id)
    )
    partner_with_config = result.scalar_one()
    
    # Test relationship
    assert partner_with_config.sftp_configuration is not None
    assert partner_with_config.sftp_configuration.sftp_username == "testuser"
    assert partner_with_config.sftp_configuration.partner_id == sample_partner.id


async def test_processing_schedules_populated(db_session: AsyncSession):
    """Test that default processing schedules can be populated and queried"""
    from src.models.processing_schedule import get_default_schedules
    
    # Insert default schedules since database gets reset between tests
    default_schedules = get_default_schedules()
    for schedule_data in default_schedules:
        schedule = ProcessingSchedule(**schedule_data)
        db_session.add(schedule)
    await db_session.commit()
    
    # Query all schedules
    result = await db_session.execute(select(ProcessingSchedule))
    schedules = result.scalars().all()
    
    # Should have the 6 default schedules
    assert len(schedules) == 6
    
    schedule_names = [s.name for s in schedules]
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


async def test_unique_constraints(db_session: AsyncSession, sample_partner: TradingPartner):
    """Test unique constraints on SFTP configuration"""
    # Create first configuration
    config1 = SftpConfiguration(
        tenant_id=sample_partner.tenant_id,
        partner_id=sample_partner.id,
        sftp_enabled=True,
        sftp_username="testuser1",
        inbound_directory="/partners/test/inbound",
        outbound_directory="/partners/test/outbound"
    )
    
    db_session.add(config1)
    await db_session.commit()
    
    # Try to create duplicate configuration for same tenant+partner
    config2 = SftpConfiguration(
        tenant_id=sample_partner.tenant_id,
        partner_id=sample_partner.id,
        sftp_enabled=True,
        sftp_username="testuser2",
        inbound_directory="/partners/test/inbound2",
        outbound_directory="/partners/test/outbound2"
    )
    
    db_session.add(config2)
    
    # Should raise integrity error due to unique constraint
    with pytest.raises(Exception):  # SQLAlchemy will raise an IntegrityError
        await db_session.commit()


async def test_file_processing_log_relationships(db_session: AsyncSession, sample_partner: TradingPartner):
    """Test relationships in file processing log"""
    # Create SFTP config
    config = SftpConfiguration(
        tenant_id=sample_partner.tenant_id,
        partner_id=sample_partner.id,
        sftp_enabled=True,
        sftp_username="testuser",
        inbound_directory="/partners/test/inbound",
        outbound_directory="/partners/test/outbound"
    )
    db_session.add(config)
    await db_session.commit()
    await db_session.refresh(config)
    
    # Create validation transaction
    transaction = ValidationTransaction(
        tenant_id=sample_partner.tenant_id,
        user_id="system",
        username="sftp-processor",
        original_filename="test_file.x12",
        request_object_key="tenant/partner/123/request.edi",
        source_type=SourceType.SFTP,
        source_partner_id=sample_partner.id
    )
    db_session.add(transaction)
    await db_session.commit()
    await db_session.refresh(transaction)
    
    # Create processing log
    log = FileProcessingLog(
        tenant_id=sample_partner.tenant_id,
        partner_id=sample_partner.id,
        sftp_config_id=config.id,
        validation_transaction_id=transaction.id,
        source_filename="test_file.x12",
        source_directory="/partners/test/inbound"
    )
    
    db_session.add(log)
    await db_session.commit()
    await db_session.refresh(log)
    
    # Test relationships
    assert log.partner is not None
    assert log.partner.id == sample_partner.id
    assert log.sftp_config is not None
    assert log.sftp_config.id == config.id
    assert log.validation_transaction is not None
    assert log.validation_transaction.id == transaction.id


async def test_api_validation_transaction_defaults(db_session: AsyncSession, sample_partner: TradingPartner):
    """Test that API validation transactions get proper defaults"""
    # Simulate existing API validation behavior
    transaction = ValidationTransaction(
        tenant_id=sample_partner.tenant_id,
        user_id="api-user",
        username="test-user",
        original_filename="api_upload.x12",
        request_object_key="tenant/api/123/request.edi",
        status=ValidationStatus.COMPLETE
        # Note: NOT setting source_type, should default to API
    )
    
    db_session.add(transaction)
    await db_session.commit()
    await db_session.refresh(transaction)
    
    # Verify defaults for API processing
    assert transaction.source_type == SourceType.API
    assert transaction.source_partner_id is None
    assert transaction.source_file_path is None
    assert transaction.response_delivered is False
    assert transaction.response_delivery_attempts == 0
    assert transaction.response_delivered_at is None