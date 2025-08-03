"""
End-to-End Tests for Multi-Tenant SFTP Functionality

These tests simulate real-world scenarios where:
1. Trading partners upload EDI files via SFTP
2. Scheduled jobs discover and process files
3. Validation occurs and acknowledgments are generated
4. Response files are delivered to partner outbound directories
5. All database and object storage state is properly maintained

The tests verify complete tenant isolation, proper file processing workflows,
and integration between all system components.
"""

import pytest
import httpx
import asyncio
import tempfile
import uuid
from pathlib import Path
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from src.core.config import settings
from src.core.storage import storage_client
from src.models.trading_partner import TradingPartner
from src.models.sftp_configuration import SftpConfiguration
from src.models.processing_schedule import ProcessingSchedule
from src.models.file_processing_log import FileProcessingLog, FileProcessingStatus
from src.models.validation_transaction import ValidationTransaction, ValidationStatus, SourceType
from src.services.sftp_file_processor import SftpFileProcessor
from src.services.sftp_scheduler import get_scheduler
from tests.e2e.e2e_utils import get_user_token

pytestmark = [pytest.mark.asyncio, pytest.mark.e2e]


# Fixture to provide temporary SFTP directory structure used by several tests
@pytest.fixture
async def temp_sftp_structure(setup_tenant_partners_and_configs):
    """
    Creates a temporary SFTP directory structure for all configs created in
    setup_tenant_partners_and_configs and returns (sftp_root, configs).
    """
    test_data = await setup_tenant_partners_and_configs
    configs = test_data["configs"]

    tmpdir = tempfile.mkdtemp()
    sftp_root = Path(tmpdir) / "sftp" / "tenants"

    for config in configs.values():
        tenant_dir = sftp_root / config.tenant_id / config.sftp_username
        (tenant_dir / "in").mkdir(parents=True, exist_ok=True)
        (tenant_dir / "out").mkdir(parents=True, exist_ok=True)
        archive_dir = sftp_root / config.tenant_id / ".archive" / config.sftp_username
        archive_dir.mkdir(parents=True, exist_ok=True)

    # Yield to caller and ensure cleanup after the test completes
    try:
        yield sftp_root, configs
    finally:
        import shutil
        shutil.rmtree(sftp_root.parent.parent, ignore_errors=True)


class TestMultiTenantSftpE2E:
    """End-to-end tests for multi-tenant SFTP functionality."""

    @pytest.fixture
    async def setup_tenant_partners_and_configs(self, db_session: AsyncSession):
        """Setup test data: tenants, partners, and SFTP configurations."""
        # Create trading partners for different tenants
        partner_a1 = TradingPartner(
            tenant_id="tenant-a",
            name="Healthcare Corp Main",
            description="Main healthcare partner"
        )
        partner_a2 = TradingPartner(
            tenant_id="tenant-a", 
            name="Healthcare Corp Branch",
            description="Branch healthcare partner"
        )
        partner_b1 = TradingPartner(
            tenant_id="tenant-b",
            name="Logistics Inc Warehouse",
            description="Logistics partner"
        )
        
        db_session.add_all([partner_a1, partner_a2, partner_b1])
        await db_session.commit()
        await db_session.refresh(partner_a1)
        await db_session.refresh(partner_a2)
        await db_session.refresh(partner_b1)

        # Create processing schedule
        schedule = ProcessingSchedule(
            name="Every 5 Minutes",
            description="Process files every 5 minutes for testing",
            cron_expression="*/5 * * * *",  # Every 5 minutes
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
            sftp_username="healthcare-main",
            authentication_type="PASSWORD",
            password_hash="hashed_test123",
            inbound_directory="/dummy",  # Will use helper methods
            outbound_directory="/dummy",
            file_name_patterns='["*.edi", "*.x12"]',
            poll_schedule_id=schedule.id,
            poll_enabled=True,
            response_filename_template="{original_name}_ack_{timestamp}.edi",
            response_timeout_minutes=5,
            max_file_size_bytes=10485760  # 10MB
        )
        
        config_a2 = SftpConfiguration(
            tenant_id="tenant-a",
            partner_id=partner_a2.id,
            sftp_enabled=True,
            sftp_username="healthcare-branch", 
            authentication_type="PASSWORD",
            password_hash="hashed_test456",
            inbound_directory="/dummy",
            outbound_directory="/dummy",
            file_name_patterns='["*.edi"]',
            poll_schedule_id=schedule.id,
            poll_enabled=True,
            response_filename_template="{original_name}_response.edi",
            response_timeout_minutes=5,
            max_file_size_bytes=10485760
        )
        
        config_b1 = SftpConfiguration(
            tenant_id="tenant-b",
            partner_id=partner_b1.id,
            sftp_enabled=True,
            sftp_username="logistics-warehouse",
            authentication_type="PASSWORD", 
            password_hash="hashed_test789",
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
            "healthcare_claim_837.edi": """ISA*00*          *00*          *ZZ*HEALTHCORP   *ZZ*CLEARHOUSE *{date}*{time}*^*00501*{isa_control}*0*P*>~
GS*HC*HEALTHCORP*CLEARHOUSE*{date}*{time}*{gs_control}*X*005010X222A1~
ST*837*0001*005010X222A1~
BHT*0019*00*{claim_id}*{date}*{time}*CH~
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
DTP*431*D8*{date}~
PWK*OZ*BM***AC*CONTROL123~
HI*BK>87340~
LX*1~
SV1*HC>99213*125*UN*1***1**Y~
DTP*472*D8*{date}~
SE*25*0001~
GE*1*{gs_control}~
IEA*1*{isa_control}~""",
            
            "logistics_invoice_810.edi": """ISA*00*          *00*          *ZZ*LOGISTICS   *ZZ*CUSTOMER   *{date}*{time}*U*00501*{isa_control}*0*P*>~
GS*IN*LOGISTICS*CUSTOMER*{date}*{time}*{gs_control}*X*004010~
ST*810*0001~
BIG*{date}*INV001*{date}*PO12345~
N1*BY*CUSTOMER NAME*92*CUST001~
N1*ST*SHIP TO ADDRESS*92*SHIP001~
IT1*1*10*EA*50.00**UP*SKU12345*VP*PRODUCT001~
TDS*500.00~
SE*8*0001~
GE*1*{gs_control}~
IEA*1*{isa_control}~""",
            
            "branch_eligibility_270.edi": """ISA*00*          *00*          *ZZ*BRANCH     *ZZ*PAYER      *{date}*{time}*U*00501*{isa_control}*0*P*>~
GS*HS*BRANCH*PAYER*{date}*{time}*{gs_control}*X*005010X279A1~
ST*270*0001*005010X279A1~
BHT*0022*13*{claim_id}*{date}*{time}~
HL*1**20*1~
NM1*PR*2*PAYER NAME*****PI*PAYER001~
HL*2*1*21*1~
NM1*1P*2*BRANCH NAME*****XX*1234567890~
HL*3*2*22*0~
TRN*1*{claim_id}*9876543210~
NM1*IL*1*DOE*JANE****MI*987654321~
SE*11*0001~
GE*1*{gs_control}~
IEA*1*{isa_control}~"""
        }

    async def create_temp_sftp_structure(self, configs):
        """Create temporary SFTP directory structure for testing."""
        tmpdir = tempfile.mkdtemp()
        sftp_root = Path(tmpdir) / "sftp" / "tenants"
        
        # Create directory structure for each configuration
        for config_name, config in configs.items():
            tenant_dir = sftp_root / config.tenant_id / config.sftp_username
            (tenant_dir / "in").mkdir(parents=True)
            (tenant_dir / "out").mkdir(parents=True)
            
            # Create archive directory
            archive_dir = sftp_root / config.tenant_id / ".archive" / config.sftp_username
            archive_dir.mkdir(parents=True)
        
        return sftp_root, tmpdir

    async def _create_edi_file_with_placeholders(self, content_template: str, file_path: Path):
        """Create an EDI file with dynamic placeholders filled in."""
        now = datetime.utcnow()
        date_str = now.strftime("%Y%m%d")
        time_str = now.strftime("%H%M")
        isa_control = f"{now.microsecond:09d}"[:9]
        gs_control = f"{now.microsecond:06d}"[:6]
        claim_id = f"CLM{uuid.uuid4().hex[:8].upper()}"
        
        content = content_template.format(
            date=date_str,
            time=time_str,
            isa_control=isa_control,
            gs_control=gs_control,
            claim_id=claim_id
        )
        
        file_path.write_text(content)
        return content

    @pytest.mark.asyncio
    async def test_complete_sftp_workflow_tenant_a_main(
        self,
        setup_tenant_partners_and_configs,
        sample_edi_files,
        db_session: AsyncSession
    ):
        """Test complete SFTP workflow for tenant-a main partner."""
        test_data = await setup_tenant_partners_and_configs
        configs = test_data["configs"]
        sftp_root, tmpdir = await self.create_temp_sftp_structure(configs)
        config = configs["tenant_a_main"]
        partner = test_data["partners"]["tenant_a_main"]
        
        # 1. Simulate partner uploading file via SFTP
        inbound_dir = sftp_root / config.tenant_id / config.sftp_username / "in"
        test_file = inbound_dir / "healthcare_claim_001.edi"
        edi_content = await self._create_edi_file_with_placeholders(
            sample_edi_files["healthcare_claim_837.edi"], test_file
        )
        
        # 2. Run file processor (simulates scheduled job)
        processor = SftpFileProcessor()
        # Update discovery service to use our test directory
        processor.discovery_service.sftp_root = sftp_root
        
        await processor.process_files_for_config(config, db_session)
        
        # 3. Assert database state - FileProcessingLog
        processing_log_result = await db_session.execute(
            select(FileProcessingLog).where(
                and_(
                    FileProcessingLog.tenant_id == config.tenant_id,
                    FileProcessingLog.partner_id == partner.id,
                    FileProcessingLog.source_filename == "healthcare_claim_001.edi"
                )
            )
        )
        processing_log = processing_log_result.scalar_one_or_none()
        
        assert processing_log is not None, "File processing log should be created"
        assert processing_log.status == FileProcessingStatus.COMPLETED.value
        assert processing_log.tenant_id == "tenant-a"
        assert processing_log.partner_id == partner.id
        assert processing_log.sftp_config_id == config.id
        assert processing_log.source_filename == "healthcare_claim_001.edi"
        assert processing_log.processing_started_at is not None
        assert processing_log.processing_completed_at is not None
        assert processing_log.response_filename is not None
        assert processing_log.response_delivered_at is not None
        
        # 4. Assert database state - ValidationTransaction
        validation_result = await db_session.execute(
            select(ValidationTransaction).where(
                ValidationTransaction.id == processing_log.validation_transaction_id
            )
        )
        validation_transaction = validation_result.scalar_one_or_none()
        
        assert validation_transaction is not None, "Validation transaction should be created"
        assert validation_transaction.tenant_id == "tenant-a"
        assert validation_transaction.original_filename == "healthcare_claim_001.edi"
        assert validation_transaction.source_type == SourceType.SFTP
        assert validation_transaction.source_partner_id == partner.id
        assert validation_transaction.status in [ValidationStatus.COMPLETE, ValidationStatus.FAILED]
        assert validation_transaction.request_object_key is not None
        assert validation_transaction.ta1_object_key is not None
        
        # 5. Assert object storage state
        original_content = storage_client.download(validation_transaction.request_object_key)
        assert original_content is not None
        assert original_content.decode('utf-8') == edi_content
        
        ta1_content = storage_client.download(validation_transaction.ta1_object_key)
        assert ta1_content is not None
        ta1_str = ta1_content.decode('utf-8')
        assert "ISA*" in ta1_str  # Should be a valid TA1
        assert "TA1*" in ta1_str  # Should contain TA1 segment
        
        # 6. Assert response file delivery
        outbound_dir = sftp_root / config.tenant_id / config.sftp_username / "out"
        response_files = list(outbound_dir.glob("*.edi"))
        assert len(response_files) == 1, "Response file should be delivered"
        
        response_file = response_files[0]
        assert processing_log.response_filename == response_file.name
        response_content = response_file.read_text()
        assert response_content == ta1_str
        
        # 7. Assert original file is archived
        assert not test_file.exists(), "Original file should be moved to archive"
        archive_dir = sftp_root / config.tenant_id / ".archive" / config.sftp_username
        archived_files = list(archive_dir.glob("*healthcare_claim_001.edi"))
        assert len(archived_files) == 1, "Original file should be archived"
        
        # Cleanup
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_tenant_isolation_in_processing(
        self,
        setup_tenant_partners_and_configs,
        temp_sftp_structure,
        sample_edi_files,
        db_session: AsyncSession
    ):
        """Test that file processing maintains strict tenant isolation."""
        test_data = await setup_tenant_partners_and_configs
        sftp_root, configs = temp_sftp_structure
        
        # Upload files for different tenants
        config_a = configs["tenant_a_main"]
        config_b = configs["tenant_b_warehouse"]
        
        # Create files in both tenant directories
        file_a = sftp_root / config_a.tenant_id / config_a.sftp_username / "in" / "tenant_a_file.edi"
        file_b = sftp_root / config_b.tenant_id / config_b.sftp_username / "in" / "tenant_b_file.edi"
        
        await self._create_edi_file_with_placeholders(sample_edi_files["healthcare_claim_837.edi"], file_a)
        await self._create_edi_file_with_placeholders(sample_edi_files["logistics_invoice_810.edi"], file_b)
        
        # Process files for both configurations
        processor = SftpFileProcessor()
        processor.discovery_service.sftp_root = sftp_root
        
        await processor.process_files_for_config(config_a, db_session)
        await processor.process_files_for_config(config_b, db_session)
        
        # Assert tenant-a processing logs only contain tenant-a data
        logs_a_result = await db_session.execute(
            select(FileProcessingLog).where(FileProcessingLog.tenant_id == "tenant-a")
        )
        logs_a = logs_a_result.scalars().all()
        
        assert len(logs_a) == 1
        assert all(log.tenant_id == "tenant-a" for log in logs_a)
        assert logs_a[0].source_filename == "tenant_a_file.edi"
        
        # Assert tenant-b processing logs only contain tenant-b data
        logs_b_result = await db_session.execute(
            select(FileProcessingLog).where(FileProcessingLog.tenant_id == "tenant-b")
        )
        logs_b = logs_b_result.scalars().all()
        
        assert len(logs_b) == 1
        assert all(log.tenant_id == "tenant-b" for log in logs_b)
        assert logs_b[0].source_filename == "tenant_b_file.edi"
        
        # Assert validation transactions are properly isolated
        validations_a_result = await db_session.execute(
            select(ValidationTransaction).where(ValidationTransaction.tenant_id == "tenant-a")
        )
        validations_a = validations_a_result.scalars().all()
        assert len(validations_a) == 1
        assert validations_a[0].source_partner_id == test_data["partners"]["tenant_a_main"].id
        
        validations_b_result = await db_session.execute(
            select(ValidationTransaction).where(ValidationTransaction.tenant_id == "tenant-b")
        )
        validations_b = validations_b_result.scalars().all()
        assert len(validations_b) == 1
        assert validations_b[0].source_partner_id == test_data["partners"]["tenant_b_warehouse"].id
        
        # Assert response files are delivered to correct tenant directories
        outbound_a = sftp_root / config_a.tenant_id / config_a.sftp_username / "out"
        outbound_b = sftp_root / config_b.tenant_id / config_b.sftp_username / "out"
        
        files_a = list(outbound_a.glob("*.edi"))
        files_b = list(outbound_b.glob("*.edi"))
        
        assert len(files_a) == 1, "Tenant A should have one response file"
        assert len(files_b) == 1, "Tenant B should have one response file"
        
        # Ensure no cross-tenant file leakage
        assert not any("tenant_b" in f.name for f in files_a)
        assert not any("tenant_a" in f.name for f in files_b)

    @pytest.mark.asyncio
    async def test_concurrent_processing_multiple_partners(
        self,
        setup_tenant_partners_and_configs,
        temp_sftp_structure,
        sample_edi_files,
        db_session: AsyncSession
    ):
        """Test concurrent processing of files from multiple partners."""
        test_data = await setup_tenant_partners_and_configs
        sftp_root, configs = temp_sftp_structure
        
        # Create files for all partners
        files_to_process = []
        
        # Tenant A - Main partner
        file_a1 = sftp_root / configs["tenant_a_main"].tenant_id / configs["tenant_a_main"].sftp_username / "in" / "claim_main_001.edi"
        await self._create_edi_file_with_placeholders(sample_edi_files["healthcare_claim_837.edi"], file_a1)
        files_to_process.append(("tenant_a_main", file_a1))
        
        # Tenant A - Branch partner
        file_a2 = sftp_root / configs["tenant_a_branch"].tenant_id / configs["tenant_a_branch"].sftp_username / "in" / "eligibility_branch_001.edi"
        await self._create_edi_file_with_placeholders(sample_edi_files["branch_eligibility_270.edi"], file_a2)
        files_to_process.append(("tenant_a_branch", file_a2))
        
        # Tenant B - Warehouse partner  
        file_b1 = sftp_root / configs["tenant_b_warehouse"].tenant_id / configs["tenant_b_warehouse"].sftp_username / "in" / "invoice_warehouse_001.edi"
        await self._create_edi_file_with_placeholders(sample_edi_files["logistics_invoice_810.edi"], file_b1)
        files_to_process.append(("tenant_b_warehouse", file_b1))
        
        # Process all configurations concurrently
        processor = SftpFileProcessor()
        processor.discovery_service.sftp_root = sftp_root
        
        tasks = []
        for config_name in configs.keys():
            task = processor.process_files_for_config(configs[config_name], db_session)
            tasks.append(task)
        
        # Run all processing tasks concurrently
        await asyncio.gather(*tasks)
        
        # Assert all files were processed successfully
        for config_name, file_path in files_to_process:
            config = configs[config_name]
            partner = test_data["partners"][config_name]
            
            # Check processing log
            log_result = await db_session.execute(
                select(FileProcessingLog).where(
                    and_(
                        FileProcessingLog.tenant_id == config.tenant_id,
                        FileProcessingLog.partner_id == partner.id,
                        FileProcessingLog.source_filename == file_path.name
                    )
                )
            )
            log = log_result.scalar_one_or_none()
            
            assert log is not None, f"Processing log missing for {config_name}"
            assert log.status == FileProcessingStatus.COMPLETED.value, f"Processing failed for {config_name}"
            
            # Check validation transaction
            validation_result = await db_session.execute(
                select(ValidationTransaction).where(
                    ValidationTransaction.id == log.validation_transaction_id
                )
            )
            validation = validation_result.scalar_one_or_none()
            
            assert validation is not None, f"Validation transaction missing for {config_name}"
            assert validation.tenant_id == config.tenant_id
            assert validation.source_partner_id == partner.id
            
            # Check response file delivery
            outbound_dir = sftp_root / config.tenant_id / config.sftp_username / "out"
            response_files = list(outbound_dir.glob("*.edi"))
            assert len(response_files) == 1, f"Response file missing for {config_name}"
            
            # Check original file is archived
            assert not file_path.exists(), f"Original file not archived for {config_name}"

    @pytest.mark.asyncio
    async def test_scheduler_integration_e2e(
        self,
        setup_tenant_partners_and_configs,
        temp_sftp_structure,
        sample_edi_files,
        db_session: AsyncSession
    ):
        """Test integration with SFTP scheduler service."""
        test_data = await setup_tenant_partners_and_configs
        sftp_root, configs = temp_sftp_structure
        
        # Create test files
        config = configs["tenant_a_main"]
        partner = test_data["partners"]["tenant_a_main"]
        
        inbound_dir = sftp_root / config.tenant_id / config.sftp_username / "in"
        test_file = inbound_dir / "scheduled_processing_test.edi"
        await self._create_edi_file_with_placeholders(
            sample_edi_files["healthcare_claim_837.edi"], test_file
        )
        
        # Get scheduler and configure it to use our test directory
        scheduler = await get_scheduler()
        
        # Update the file processor in scheduler to use test directory
        scheduler.file_processor.discovery_service.sftp_root = sftp_root
        
        # Manually trigger processing for the partner
        success = await scheduler.process_partner_manually(partner.id)
        assert success, "Manual processing should succeed"
        
        # Verify processing occurred
        log_result = await db_session.execute(
            select(FileProcessingLog).where(
                and_(
                    FileProcessingLog.tenant_id == config.tenant_id,
                    FileProcessingLog.partner_id == partner.id,
                    FileProcessingLog.source_filename == "scheduled_processing_test.edi"
                )
            )
        )
        log = log_result.scalar_one_or_none()
        
        assert log is not None, "Scheduler should have processed the file"
        assert log.status == FileProcessingStatus.COMPLETED.value
        
        # Verify response was delivered
        outbound_dir = sftp_root / config.tenant_id / config.sftp_username / "out"
        response_files = list(outbound_dir.glob("*.edi"))
        assert len(response_files) == 1, "Scheduler should have delivered response"

    @pytest.mark.asyncio 
    async def test_sftp_api_integration_with_processing(
        self,
        setup_tenant_partners_and_configs,
        temp_sftp_structure,
        sample_edi_files,
        db_session: AsyncSession
    ):
        """Test SFTP API endpoints integration with file processing."""
        test_data = await setup_tenant_partners_and_configs
        sftp_root, configs = temp_sftp_structure
        
        # Get authentication token
        token = await get_user_token("superuser@edilens.com")
        headers = {"Authorization": f"Bearer {token}", "X-Tenant-ID": "tenant-a"}
        base_url = f"http://{settings.BACKEND_HOST}:8000/api/v1/sftp"
        
        config = configs["tenant_a_main"]
        partner = test_data["partners"]["tenant_a_main"]
        
        # 1. Create a file and process it
        inbound_dir = sftp_root / config.tenant_id / config.sftp_username / "in"
        test_file = inbound_dir / "api_integration_test.edi"
        await self._create_edi_file_with_placeholders(
            sample_edi_files["healthcare_claim_837.edi"], test_file
        )
        
        processor = SftpFileProcessor()
        processor.discovery_service.sftp_root = sftp_root
        await processor.process_files_for_config(config, db_session)
        
        # 2. Test API endpoints after processing
        async with httpx.AsyncClient() as client:
            # Get enhanced SFTP configuration
            response = await client.get(
                f"{base_url}/configurations/{partner.id}/enhanced",
                headers=headers
            )
            assert response.status_code == 200
            config_data = response.json()
            assert config_data["tenant_partner_username"] == f"{config.tenant_id}_{config.sftp_username}"
            assert config_data["inbound_directory_path"] is not None
            assert config_data["outbound_directory_path"] is not None
            
            # Validate partner directories
            response = await client.get(
                f"{base_url}/directories/{partner.id}",
                headers=headers
            )
            assert response.status_code == 200
            dir_info = response.json()
            assert dir_info["tenant_id"] == "tenant-a"
            assert dir_info["partner_name"] == partner.name
            assert dir_info["directory_exists"] == True  # Our test directories exist
            
            # Get processing logs
            response = await client.get(
                f"{base_url}/processing-logs?partner_id={partner.id}",
                headers=headers
            )
            assert response.status_code == 200
            logs = response.json()
            assert len(logs) >= 1
            
            # Find our test file's log
            test_log = next((log for log in logs if log["source_filename"] == "api_integration_test.edi"), None)
            assert test_log is not None
            assert test_log["tenant_id"] == "tenant-a"
            assert test_log["partner_id"] == partner.id
            assert test_log["status"] == "COMPLETED"
            assert test_log["response_filename"] is not None

    @pytest.mark.asyncio
    async def test_error_handling_and_retry_logic(
        self,
        setup_tenant_partners_and_configs,
        temp_sftp_structure,
        db_session: AsyncSession
    ):
        """Test error handling and retry logic in file processing."""
        test_data = await setup_tenant_partners_and_configs
        sftp_root, configs = temp_sftp_structure
        
        config = configs["tenant_a_main"]
        partner = test_data["partners"]["tenant_a_main"]
        
        # Create an invalid EDI file (malformed content)
        inbound_dir = sftp_root / config.tenant_id / config.sftp_username / "in"
        invalid_file = inbound_dir / "invalid_edi.edi"
        invalid_file.write_text("This is not valid EDI content")
        
        # Process the invalid file
        processor = SftpFileProcessor()
        processor.discovery_service.sftp_root = sftp_root
        await processor.process_files_for_config(config, db_session)
        
        # Check that processing failed and was logged properly
        log_result = await db_session.execute(
            select(FileProcessingLog).where(
                and_(
                    FileProcessingLog.tenant_id == config.tenant_id,
                    FileProcessingLog.partner_id == partner.id,
                    FileProcessingLog.source_filename == "invalid_edi.edi"
                )
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
            if validation:
                assert validation.status == ValidationStatus.FAILED
        
        # Verify no response file was created
        outbound_dir = sftp_root / config.tenant_id / config.sftp_username / "out"
        response_files = list(outbound_dir.glob("*.edi"))
        assert len(response_files) == 0, "No response file should be created for failed processing"
        
        # Verify original file is still in inbound (not archived on failure)
        assert invalid_file.exists(), "Failed file should remain in inbound directory"
