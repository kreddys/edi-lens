# FILE: backend/tests/e2e/test_e2e_workflows.py

import pytest
import pytest_asyncio
import httpx
import tempfile
import json
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid

from src.core.config import settings
from src.models import (
    TradingPartner, PartnerProfile, ProcessingLog
)
# --- THIS IS THE FIX: Remove imports for deleted models ---
from src.services.sftp_file_processor import SftpFileProcessor
from tests.e2e.e2e_utils import get_user_token

pytestmark = [pytest.mark.asyncio, pytest.mark.e2e]

@pytest_asyncio.fixture(scope="module")
async def superuser_token():
    """Provides a superuser token for the entire test module."""
    return await get_user_token("superuser@edilens.com")

@pytest_asyncio.fixture(scope="function")
async def setup_partner_and_profiles(db_session: AsyncSession, superuser_token: str):
    """
    E2E Fixture: Creates a new, unique partner and profiles for EACH test function.
    """
    tenant_id = "tenant-a"
    headers = {"Authorization": f"Bearer {superuser_token}", "X-Tenant-ID": tenant_id}
    partner_name = f"e2e-partner-{uuid.uuid4()}"
    
    partner_data = {
        "name": partner_name,
        "sftp_enabled": True,
        "sftp_username": f"e2e-user-{uuid.uuid4().hex[:12]}",
        "profiles": [
            {
                "name": "E2E Claims Profile",
                "file_name_patterns": '["claims_*.edi", "837_*"]',
                "generate_ta1": True,
                "implementation_guide": "837P",
                "validation_schema_name": "837.5010.X222.A1.json",
            },
            {
                "name": "E2E Remits Profile",
                "file_name_patterns": '["remit_*.x12"]',
                "generate_ta1": False,
                "implementation_guide": "835",
                "validation_schema_name": "837.5010.X222.A1.json",
            }
        ]
    }
    
    base_url = f"http://{settings.BACKEND_HOST}:8000/api/v1/trading-partners"
    async with httpx.AsyncClient() as client:
        response = await client.post(base_url, headers=headers, json=partner_data)
        assert response.status_code == 201, f"Setup failed: {response.text}"
        partner_id = response.json()["id"]

    result = await db_session.execute(
        select(TradingPartner).where(TradingPartner.id == partner_id)
    )
    partner = result.scalars().one()
    
    return {
        "partner": partner,
        "claims_profile_name": "E2E Claims Profile",
        "remits_profile_name": "E2E Remits Profile"
    }


class TestValidationE2E:
    async def test_validation_e2e_successful_ack_requested(
        self, superuser_token: str, edi_with_ack_requested: str, setup_partner_and_profiles
    ):
        tenant_id = setup_partner_and_profiles["partner"].tenant_id
        headers = {"Authorization": f"Bearer {superuser_token}", "X-Tenant-ID": tenant_id}
        backend_url = f"http://{settings.BACKEND_HOST}:8000/api/v1/validate"
        payload = {
            "edi_data": edi_with_ack_requested,
            "profile_name": setup_partner_and_profiles["claims_profile_name"]
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(backend_url, headers=headers, json=payload)

        assert response.status_code == 200, f"API call failed: {response.text}"
        data = response.json()
        assert data["valid"] is True
        assert "*A*000~" in data["ta1_content"]


class TestSftpWorkflowE2E:
    async def test_sftp_workflow_with_filename_matching(
        self, db_session: AsyncSession, setup_partner_and_profiles, valid_837p_edi_string: str
    ):
        """
        Validates the full SFTP workflow from file drop to the unified ProcessingLog.
        """
        partner = setup_partner_and_profiles["partner"]
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # 1. Arrange: Setup SFTP file structure and drop files
            sftp_root = Path(tmpdir)
            inbound_dir = sftp_root / partner.tenant_id / partner.sftp_username / "in"
            inbound_dir.mkdir(parents=True, exist_ok=True)
            
            (inbound_dir / "claims_123.edi").write_text(valid_837p_edi_string)
            (inbound_dir / "unmatched.txt").write_text("some data")

            # 2. Act: Run the processor
            processor = SftpFileProcessor(db_session)
            # Override the discovery path to use our temporary directory
            processor._discover_files = lambda p: [fp for fp in inbound_dir.iterdir() if fp.is_file()]
            await processor.process_all_sftp_partners()

            # 3. Assert: Check the unified ProcessingLog for correct entries
            proc_logs_result = await db_session.execute(
                select(ProcessingLog)
                .where(ProcessingLog.source == "SFTP")
                .order_by(ProcessingLog.file_name)
            )
            proc_logs = proc_logs_result.scalars().all()
            
            assert len(proc_logs) == 2
            
            claims_log = proc_logs[0]
            unmatched_log = proc_logs[1]

            assert claims_log.file_name == "claims_123.edi"
            assert claims_log.validation_result == "VALID"
            
            assert unmatched_log.file_name == "unmatched.txt"
            assert unmatched_log.validation_result == "ERROR"