# FILE: backend/src/services/sftp_file_processor.py

import logging
import os
import shutil
import json
import fnmatch
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.models.trading_partner import TradingPartner
from src.services.validation_service import ValidationService
from src.core.profile_matcher import ProfileMatcher
from src.repositories.processing_log_repo import ProcessingLogRepository

logger = logging.getLogger(__name__)

class SftpFileProcessor:
    """
    A service to discover and process files for all SFTP-enabled trading partners.
    This service is designed to be run as a single, atomic task.
    """
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self.validation_service = ValidationService(self.db)
        self.profile_matcher = ProfileMatcher(self.db)
        self.log_repo = ProcessingLogRepository(self.db)

    async def process_all_sftp_partners(self):
        """
        Main entry point. Finds all SFTP-enabled partners and processes their files.
        """
        logger.info("Starting SFTP processing run for all enabled partners.")
        sftp_partners = await self._get_sftp_enabled_partners()
        logger.info(f"Found {len(sftp_partners)} SFTP-enabled trading partners to process.")

        for partner in sftp_partners:
            await self._process_files_for_partner(partner)

    async def _get_sftp_enabled_partners(self) -> List[TradingPartner]:
        """
        --- CHANGED ---
        Fetches all trading partners directly where sftp_enabled is True.
        """
        query = select(TradingPartner).where(TradingPartner.sftp_enabled == True)
        result = await self.db.execute(query)
        return result.scalars().all()

    def _discover_files(self, partner: TradingPartner) -> List[Path]:
        """Discovers files in a partner's designated SFTP inbound directory."""
        if not partner.sftp_username:
            return []
        
        # This path is relative to the Docker container's filesystem
        sftp_root = Path(os.getenv("SFTP_TENANT_ROOT", "/sftp/tenants"))
        inbound_dir = sftp_root / partner.tenant_id / partner.sftp_username / "in"

        if not inbound_dir.is_dir():
            logger.debug(f"Inbound directory does not exist for partner '{partner.name}': {inbound_dir}")
            return []

        try:
            return [file_path for file_path in inbound_dir.iterdir() if file_path.is_file()]
        except Exception as e:
            logger.error(f"Error discovering files in {inbound_dir}: {e}")
            return []

    async def _process_files_for_partner(self, partner: TradingPartner):
        """Processes all discoverable files for a single trading partner."""
        files_to_process = self._discover_files(partner)
        if not files_to_process:
            logger.info(f"No new files to process for partner '{partner.name}'.")
            return

        logger.info(f"Found {len(files_to_process)} files for partner '{partner.name}'.")
        for file_path in files_to_process:
            await self._process_single_file(partner, file_path)

    async def _process_single_file(self, partner: TradingPartner, file_path: Path):
        """Handles the validation, logging, and archiving of one file."""
        logger.info(f"Processing file '{file_path.name}' for partner '{partner.name}'.")
        
        # First, match the file to a profile.
        matched_profile = await self.profile_matcher.match_by_filename(partner.tenant_id, file_path.name)
        
        if not matched_profile:
            error_msg = f"No matching profile found for filename '{file_path.name}'."
            logger.error(error_msg)
            # Log the failure in our unified log table
            await self.log_repo.create_log(
                tenant_id=partner.tenant_id, source="SFTP", file_name=file_path.name,
                validation_result="ERROR", error_count=1,
                original_content_path=str(file_path) # Log path for traceability
            )
            await self._archive_file(file_path, is_error=True)
            return

        try:
            # If a profile is matched, proceed with validation.
            file_content = file_path.read_text(encoding='utf-8', errors='replace')
            
            # The validation service will create its own ProcessingLog entry upon success/failure.
            await self.validation_service.process_edi_file(
                edi_data=file_content,
                tenant_id=partner.tenant_id,
                user_id="sftp-system",
                username=partner.sftp_username,
                profile_name=matched_profile.name,
                file_name=file_path.name,
                source="SFTP"
            )
            await self._archive_file(file_path, is_error=False)

        except Exception as e:
            logger.error(f"Critical error processing file {file_path.name}: {e}", exc_info=True)
            # Log a generic error if the validation service itself fails unexpectedly.
            await self.log_repo.create_log(
                tenant_id=partner.tenant_id, source="SFTP", file_name=file_path.name,
                validation_result="ERROR", error_count=1,
                original_content_path=str(file_path)
            )
            await self._archive_file(file_path, is_error=True)

    async def _archive_file(self, file_path: Path, is_error: bool):
        """Moves a processed file to a co-located archive or error directory."""
        if not file_path.exists():
            return
        
        try:
            archive_sub_dir = ".error" if is_error else ".archive"
            archive_dir = file_path.parent / archive_sub_dir
            archive_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            archive_path = archive_dir / f"{timestamp}_{file_path.name}"
        
            shutil.move(str(file_path), str(archive_path))
            logger.info(f"Archived file '{file_path.name}' to '{archive_path}'.")
        except Exception as e:
            logger.error(f"Failed to archive file {file_path}: {e}")