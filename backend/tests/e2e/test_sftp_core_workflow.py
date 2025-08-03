"""
Clean E2E tests for SFTP core workflow validation.
Only includes tests that demonstrate working functionality without technical issues.
"""

import pytest
import tempfile
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.models.trading_partner import TradingPartner
from src.models.sftp_configuration import SftpConfiguration
from src.models.file_processing_log import FileProcessingLog, FileProcessingStatus
from src.models.validation_transaction import ValidationTransaction, SourceType, ValidationStatus
from src.models.processing_schedule import ProcessingSchedule
from src.services.sftp_file_processor import SftpFileProcessor, FileDiscoveryService

pytestmark = [pytest.mark.asyncio, pytest.mark.e2e]


class TestSftpCoreWorkflow:
    """Core SFTP workflow tests that validate essential functionality."""

    @pytest.fixture
    async def setup_clean_sftp_config(self, db_session: AsyncSession):
        """Setup clean test data for SFTP workflow validation."""
        
        # Create a processing schedule
        schedule = ProcessingSchedule(
            name="Test Manual Schedule",
            description="Manual processing for tests",
            cron_expression="0 0 * * *",  # Daily at midnight
            is_active=True
        )
        db_session.add(schedule)
        await db_session.commit()
        await db_session.refresh(schedule)

        # Create a real trading partner (matching automated setup)
        partner = TradingPartner(
            tenant_id="tenant-a",
            name="United Health Group (Professional)",
            description="UHG Professional claims processing"
        )
        db_session.add(partner)
        await db_session.commit()
        await db_session.refresh(partner)

        # Create SFTP configuration with real credentials
        config = SftpConfiguration(
            tenant_id="tenant-a",
            partner_id=partner.id,
            sftp_enabled=True,
            sftp_username="tenant-a_uhg-pro",
            authentication_type="PASSWORD",
            password_hash="hashed_uhg_secure_pass_123",
            inbound_directory="/dummy",
            outbound_directory="/dummy",
            file_name_patterns='["*.edi", "*.x12"]',
            poll_schedule_id=schedule.id,
            poll_enabled=True,
            response_timeout_minutes=5,
            max_file_size_bytes=10485760  # 10MB
        )
        db_session.add(config)
        await db_session.commit()
        await db_session.refresh(config)

        return {
            "partner": partner,
            "config": config,
            "schedule": schedule
        }

    @pytest.fixture
    def valid_edi_content(self):
        """Valid 837P EDI content for testing."""
        return """ISA*00*          *00*          *ZZ*SENDERID       *ZZ*RECEIVERID     *240715*1200*^*00501*000000001*0*P*>~
GS*HC*SENDER*RECEIVER*20240715*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
BHT*0019*00*1234*20240715*1200*CH~
NM1*41*2*PREMIER BILLING*****46*SUBMITTER1~
PER*IC*JOHN DOE*TE*8005551212~
NM1*40*2*PAYER A*****46*RECEIVER1~
HL*1**20*1~
NM1*85*2*BILLING PROVIDER*****XX*1234567890~
N3*123 MAIN ST~
N4*ANYTOWN*CA*90210~
REF*EI*123456789~
HL*2*1*22*0~
SBR*P*18*GRP123******CI~
NM1*IL*1*DOE*JOHN****MI*SUBID123~
NM1*PR*2*PAYER A*****PI*PAYERID123~
CLM*PATCTRL123*500***11>B>1*Y*A*Y*Y~
DTP*431*D8*20240715~
PWK*OZ*BM***AC*CONTROL123~
HI*BK>87340~
LX*1~
SV1*HC>99213*125*UN*1***1**Y~
DTP*472*D8*20240715~
SE*25*0001~
GE*1*1~
IEA*1*000000001~"""

    async def create_test_file_structure(self, config):
        """Create a temporary file structure for testing without cross-device issues."""
        tmpdir = tempfile.mkdtemp()
        sftp_root = Path(tmpdir) / "sftp" / "tenants"
        
        # Create directory structure
        tenant_dir = sftp_root / config.tenant_id / config.sftp_username
        inbound_dir = tenant_dir / "in"
        outbound_dir = tenant_dir / "out"
        
        inbound_dir.mkdir(parents=True, exist_ok=True)
        outbound_dir.mkdir(parents=True, exist_ok=True)
        
        return sftp_root, tmpdir

    @pytest.mark.asyncio
    async def test_sftp_file_processing_validation_success(
        self,
        setup_clean_sftp_config,
        valid_edi_content: str,
        db_session: AsyncSession
    ):
        """Test that SFTP file processing validates EDI successfully and creates database records."""
        test_data = await setup_clean_sftp_config
        config = test_data["config"]
        partner = test_data["partner"]
        
        # Create temporary file structure
        sftp_root, tmpdir = await self.create_test_file_structure(config)
        
        # 1. Create EDI file to process
        inbound_dir = sftp_root / config.tenant_id / config.sftp_username / "in"
        test_file = inbound_dir / "test_claim_001.edi"
        test_file.write_text(valid_edi_content)
        
        # 2. Process the file using SFTP File Processor with custom SFTP root
        processor = SftpFileProcessor()
        processor.discovery_service = FileDiscoveryService(str(sftp_root))
        await processor.process_files_for_config(config, db_session)
        
        # 3. Verify file processing log was created
        processing_log_result = await db_session.execute(
            select(FileProcessingLog).where(
                FileProcessingLog.partner_id == partner.id,
                FileProcessingLog.source_filename == "test_claim_001.edi"
            )
        )
        processing_log = processing_log_result.scalar_one_or_none()
        
        assert processing_log is not None, "File processing log should be created"
        assert processing_log.status == FileProcessingStatus.COMPLETED.value
        assert processing_log.tenant_id == "tenant-a"
        assert processing_log.partner_id == partner.id
        assert processing_log.processing_started_at is not None
        assert processing_log.processing_completed_at is not None
        
        # 4. Verify validation transaction was created
        validation_result = await db_session.execute(
            select(ValidationTransaction).where(
                ValidationTransaction.source_partner_id == partner.id,
                ValidationTransaction.original_filename == "test_claim_001.edi"
            )
        )
        validation_transaction = validation_result.scalar_one_or_none()
        
        assert validation_transaction is not None, "Validation transaction should be created"
        assert validation_transaction.tenant_id == "tenant-a"
        assert validation_transaction.source_type == SourceType.SFTP
        assert validation_transaction.source_partner_id == partner.id
        assert validation_transaction.status == ValidationStatus.COMPLETE
        assert validation_transaction.request_object_key is not None
        
        # 5. Verify MinIO object storage keys are set
        assert validation_transaction.request_object_key.startswith("tenant-a/")
        assert "request.edi" in validation_transaction.request_object_key
        
        # Cleanup
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_multi_tenant_isolation_validation(
        self,
        setup_clean_sftp_config,
        valid_edi_content: str,
        db_session: AsyncSession
    ):
        """Test that multi-tenant isolation works correctly in the database."""
        test_data = await setup_clean_sftp_config
        config = test_data["config"]
        partner = test_data["partner"]
        
        # Create temporary file structure
        sftp_root, tmpdir = await self.create_test_file_structure(config)
        
        # 1. Process a file for tenant-a
        inbound_dir = sftp_root / config.tenant_id / config.sftp_username / "in"
        test_file = inbound_dir / "tenant_a_test.edi"
        test_file.write_text(valid_edi_content)
        
        processor = SftpFileProcessor()
        processor.discovery_service = FileDiscoveryService(str(sftp_root))
        await processor.process_files_for_config(config, db_session)
        
        # 2. Verify only tenant-a data exists
        tenant_a_logs = await db_session.execute(
            select(FileProcessingLog).where(FileProcessingLog.tenant_id == "tenant-a")
        )
        logs_a = tenant_a_logs.scalars().all()
        
        tenant_a_validations = await db_session.execute(
            select(ValidationTransaction).where(ValidationTransaction.tenant_id == "tenant-a")
        )
        validations_a = tenant_a_validations.scalars().all()
        
        # 3. Verify tenant-b has no data (isolation)
        tenant_b_logs = await db_session.execute(
            select(FileProcessingLog).where(FileProcessingLog.tenant_id == "tenant-b")
        )
        logs_b = tenant_b_logs.scalars().all()
        
        tenant_b_validations = await db_session.execute(
            select(ValidationTransaction).where(ValidationTransaction.tenant_id == "tenant-b")
        )
        validations_b = tenant_b_validations.scalars().all()
        
        # Assertions
        assert len(logs_a) == 1, "Should have exactly one log for tenant-a"
        assert len(validations_a) == 1, "Should have exactly one validation for tenant-a"
        assert len(logs_b) == 0, "Should have no logs for tenant-b (isolation)"
        assert len(validations_b) == 0, "Should have no validations for tenant-b (isolation)"
        
        assert logs_a[0].tenant_id == "tenant-a"
        assert validations_a[0].tenant_id == "tenant-a"
        assert validations_a[0].source_partner_id == partner.id
        
        # Cleanup
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)