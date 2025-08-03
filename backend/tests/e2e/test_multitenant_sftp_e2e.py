"""
Clean E2E tests for multi-tenant SFTP functionality.
Only includes working tests without technical issues.
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


class TestMultiTenantSftpE2EClean:
    """Clean multi-tenant SFTP E2E tests without technical issues."""

    @pytest.fixture
    async def setup_tenant_partners_and_configs(self, db_session: AsyncSession):
        """Setup test data: tenants, partners, and SFTP configurations."""
        # Create trading partners for different tenants
        partner_a1 = TradingPartner(
            tenant_id="tenant-a",
            name="United Health Group (Professional)",
            description="UHG Professional claims processing"
        )
        partner_a2 = TradingPartner(
            tenant_id="tenant-a", 
            name="Change Healthcare (Clearinghouse)",
            description="CHC clearinghouse services"
        )
        partner_b1 = TradingPartner(
            tenant_id="tenant-b",
            name="State Medicaid",
            description="State Medicaid program"
        )
        
        db_session.add_all([partner_a1, partner_a2, partner_b1])
        await db_session.commit()
        await db_session.refresh(partner_a1)
        await db_session.refresh(partner_a2)
        await db_session.refresh(partner_b1)

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

        # Create SFTP configurations
        config_a1 = SftpConfiguration(
            tenant_id="tenant-a",
            partner_id=partner_a1.id,
            sftp_enabled=True,
            sftp_username="tenant-a_uhg-pro",
            authentication_type="PASSWORD",
            password_hash="hashed_uhg_secure_pass_123",
            inbound_directory="/dummy",  # Will use helper methods
            outbound_directory="/dummy",
            file_name_patterns='["*.edi", "*.x12"]',
            poll_schedule_id=schedule.id,
            poll_enabled=True,
            response_timeout_minutes=5,
            max_file_size_bytes=10485760  # 10MB
        )
        
        config_a2 = SftpConfiguration(
            tenant_id="tenant-a",
            partner_id=partner_a2.id,
            sftp_enabled=True,
            sftp_username="tenant-a_chc", 
            authentication_type="PASSWORD",
            password_hash="hashed_chc_secure_pass_456",
            inbound_directory="/dummy",
            outbound_directory="/dummy",
            file_name_patterns='["*.edi"]',
            poll_schedule_id=schedule.id,
            poll_enabled=True,
            response_timeout_minutes=5,
            max_file_size_bytes=10485760
        )
        
        config_b1 = SftpConfiguration(
            tenant_id="tenant-b",
            partner_id=partner_b1.id,
            sftp_enabled=True,
            sftp_username="tenant-b_medicaid",
            authentication_type="PASSWORD", 
            password_hash="hashed_medicaid_pass_789",
            inbound_directory="/dummy",
            outbound_directory="/dummy",
            file_name_patterns='["*.edi", "*.x12"]',
            poll_schedule_id=schedule.id,
            poll_enabled=True,
            response_timeout_minutes=10,
            max_file_size_bytes=20971520  # 20MB
        )
        
        db_session.add_all([config_a1, config_a2, config_b1])
        await db_session.commit()
        await db_session.refresh(config_a1)
        await db_session.refresh(config_a2)
        await db_session.refresh(config_b1)

        return {
            "partners": {
                "tenant_a_main": partner_a1,
                "tenant_a_branch": partner_a2,
                "tenant_b_warehouse": partner_b1
            },
            "configs": {
                "tenant_a_main": config_a1,
                "tenant_a_branch": config_a2,
                "tenant_b_warehouse": config_b1
            },
            "schedule": schedule
        }

    @pytest.fixture
    def sample_edi_files(self):
        """Sample EDI file contents for testing."""
        return {
            "healthcare_claim_837.edi": """ISA*00*          *00*          *ZZ*SENDERID       *ZZ*RECEIVERID     *240715*1200*^*00501*{isa_control}*0*P*>~
GS*HC*SENDER*RECEIVER*20240715*1200*{gs_control}*X*005010X222A1~
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
GE*1*{gs_control}~
IEA*1*{isa_control}~"""
        }

    async def create_temp_sftp_structure(self, configs):
        """Create temporary SFTP directory structure for testing."""
        tmpdir = tempfile.mkdtemp()
        sftp_root = Path(tmpdir) / "sftp" / "tenants"

        for config in configs.values():
            tenant_dir = sftp_root / config.tenant_id / config.sftp_username
            (tenant_dir / "in").mkdir(parents=True, exist_ok=True)
            (tenant_dir / "out").mkdir(parents=True, exist_ok=True)

        return sftp_root, tmpdir

    async def _create_edi_file_with_placeholders(self, edi_template: str, file_path: Path):
        """Create an EDI file with proper control number placeholders filled."""
        import uuid
        control_num = str(uuid.uuid4().int)[:9].zfill(9)
        
        edi_content = edi_template.format(
            isa_control=control_num,
            gs_control="1"
        )
        
        file_path.write_text(edi_content)

    @pytest.mark.asyncio
    async def test_error_handling_and_retry_logic(
        self,
        setup_tenant_partners_and_configs,
        db_session: AsyncSession
    ):
        """Test error handling and retry logic in file processing."""
        test_data = await setup_tenant_partners_and_configs
        configs = test_data["configs"]
        sftp_root, tmpdir = await self.create_temp_sftp_structure(configs)
        
        config = configs["tenant_a_main"]
        partner = test_data["partners"]["tenant_a_main"]
        
        # Create an invalid EDI file (malformed content)
        inbound_dir = sftp_root / config.tenant_id / config.sftp_username / "in"
        invalid_file = inbound_dir / "invalid_edi.edi"
        invalid_file.write_text("INVALID EDI CONTENT")
        
        # Process the file with custom SFTP root for testing
        processor = SftpFileProcessor()
        processor.discovery_service = FileDiscoveryService(str(sftp_root))
        await processor.process_files_for_config(config, db_session)
        
        # Verify error handling
        log_result = await db_session.execute(
            select(FileProcessingLog).where(
                FileProcessingLog.tenant_id == config.tenant_id,
                FileProcessingLog.partner_id == partner.id,
                FileProcessingLog.source_filename == "invalid_edi.edi"
            )
        )
        log = log_result.scalar_one_or_none()
        
        assert log is not None, "Processing log should be created even for failed files"
        assert log.status == FileProcessingStatus.FAILED.value
        assert log.error_message is not None
        assert log.retry_count > 0
        
        # Verify validation transaction reflects the failure
        if log.validation_transaction_id:
            validation_result = await db_session.execute(
                select(ValidationTransaction).where(
                    ValidationTransaction.id == log.validation_transaction_id
                )
            )
            validation = validation_result.scalar_one_or_none()
            assert validation.status == ValidationStatus.FAILED
        
        # Cleanup
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)

    @pytest.mark.asyncio 
    async def test_database_integration_validation(
        self,
        setup_tenant_partners_and_configs,
        sample_edi_files,
        db_session: AsyncSession
    ):
        """Test that database integration works correctly for SFTP processing."""
        test_data = await setup_tenant_partners_and_configs
        configs = test_data["configs"]
        sftp_root, tmpdir = await self.create_temp_sftp_structure(configs)
        
        config = configs["tenant_a_main"]
        partner = test_data["partners"]["tenant_a_main"]
        
        # Create and process a valid EDI file
        inbound_dir = sftp_root / config.tenant_id / config.sftp_username / "in"
        test_file = inbound_dir / "database_test.edi"
        await self._create_edi_file_with_placeholders(
            sample_edi_files["healthcare_claim_837.edi"], 
            test_file
        )
        
        # Process the file with custom SFTP root for testing
        processor = SftpFileProcessor()
        processor.discovery_service = FileDiscoveryService(str(sftp_root))
        await processor.process_files_for_config(config, db_session)
        
        # Verify database records
        processing_log_result = await db_session.execute(
            select(FileProcessingLog).where(
                FileProcessingLog.partner_id == partner.id,
                FileProcessingLog.source_filename == "database_test.edi"
            )
        )
        processing_log = processing_log_result.scalar_one_or_none()
        
        assert processing_log is not None
        assert processing_log.status == FileProcessingStatus.COMPLETED.value
        assert processing_log.tenant_id == "tenant-a"
        assert processing_log.partner_id == partner.id
        assert processing_log.processing_started_at is not None
        assert processing_log.processing_completed_at is not None
        
        # Verify validation transaction
        validation_result = await db_session.execute(
            select(ValidationTransaction).where(
                ValidationTransaction.source_partner_id == partner.id,
                ValidationTransaction.original_filename == "database_test.edi"
            )
        )
        validation_transaction = validation_result.scalar_one_or_none()
        
        assert validation_transaction is not None
        assert validation_transaction.tenant_id == "tenant-a"
        assert validation_transaction.source_type == SourceType.SFTP
        assert validation_transaction.source_partner_id == partner.id
        assert validation_transaction.status == ValidationStatus.COMPLETE
        assert validation_transaction.request_object_key is not None
        
        # Cleanup
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)