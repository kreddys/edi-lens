# FILE: backend/src/services/sftp_webhook_processor.py

import logging
import asyncio
import re
from datetime import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.api.schemas import SftpUploadWebhook
from src.models.trading_partner import TradingPartner
from src.services.validation_service import ValidationService
from src.core.profile_matcher import ProfileMatcher
from src.core.storage import storage_client
from src.repositories.processing_log_repo import ProcessingLogRepository

logger = logging.getLogger(__name__)

class SftpWebhookProcessor:
    """
    Real-time SFTP file processor that handles webhook events from SFTPGo.
    Implements rate limiting and queue fallback for high-volume protection.
    """
    
    # Rate limiting configuration
    MAX_CONCURRENT_PROCESSING = 5
    PROCESSING_TIMEOUT_SECONDS = 30
    
    # Class-level tracking of current processing load
    _current_processing_count = 0
    _processing_lock = asyncio.Lock()
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self.validation_service = ValidationService(self.db)
        self.profile_matcher = ProfileMatcher(self.db)
        self.log_repo = ProcessingLogRepository(self.db)

    async def process_upload_event(self, webhook_data: SftpUploadWebhook) -> bool:
        """
        Process SFTPGo upload webhook event.
        
        Returns:
            bool: True if processed immediately, False if queued for later
        """
        # Extract partner information from the upload path
        partner_info = self._extract_partner_info(webhook_data)
        if not partner_info:
            logger.error(f"Could not extract partner info from path: {webhook_data.path}")
            return False
            
        # Check if we can process immediately or need to queue
        async with self._processing_lock:
            if self._current_processing_count < self.MAX_CONCURRENT_PROCESSING:
                self._current_processing_count += 1
                try:
                    # Process immediately
                    await self._process_file_immediately(webhook_data, partner_info)
                    return True
                finally:
                    self._current_processing_count -= 1
            else:
                # Queue for later processing
                await self._queue_for_processing(webhook_data, partner_info)
                return False

    def _extract_partner_info(self, webhook_data: SftpUploadWebhook) -> Optional[dict]:
        """
        Extract tenant_id and partner_id from the S3 object path.
        
        Supports two formats:
        - New format: tenants/tenant-a/partners/3/in/filename.edi
        - Legacy format: tenants/tenant-a/partners/test123/in/filename.edi
        """
        if not webhook_data.object_name:
            logger.error(f"No object_name in webhook data for file: {webhook_data.name}")
            return None
            
        # Try new format first (partner ID as number)
        pattern_new = r"tenants/([^/]+)/partners/(\d+)/in/.*"
        match = re.match(pattern_new, webhook_data.object_name)
        
        if match:
            tenant_id = match.group(1)
            partner_id = int(match.group(2))
            return {
                "tenant_id": tenant_id,
                "partner_id": partner_id,
                "file_path": webhook_data.object_name,
                "lookup_method": "id"
            }
            
        # Try legacy format (partner username)
        pattern_legacy = r"tenants/([^/]+)/partners/([^/]+)/in/.*"
        match = re.match(pattern_legacy, webhook_data.object_name)
        
        if match:
            tenant_id = match.group(1)
            username = match.group(2)
            return {
                "tenant_id": tenant_id,
                "username": username,
                "file_path": webhook_data.object_name,
                "lookup_method": "username"
            }
            
        logger.error(f"Object path does not match any expected pattern: {webhook_data.object_name}")
        return None

    async def _process_file_immediately(self, webhook_data: SftpUploadWebhook, partner_info: dict):
        """Process the uploaded file immediately."""
        try:
            # Get the trading partner using appropriate lookup method
            if partner_info["lookup_method"] == "id":
                partner = await self._get_partner_by_id(partner_info["tenant_id"], partner_info["partner_id"])
                if not partner:
                    logger.error(f"Partner not found by ID: tenant={partner_info['tenant_id']}, partner_id={partner_info['partner_id']}")
                    return
            else:  # lookup_method == "username"
                partner = await self._get_partner_by_username(partner_info["tenant_id"], partner_info["username"])
                if not partner:
                    logger.error(f"Partner not found by username: tenant={partner_info['tenant_id']}, username={partner_info['username']}")
                    return
                
            # Download file content from S3
            file_content = storage_client.download(partner_info["file_path"])
            if file_content is None:
                logger.error(f"Could not download file from S3: {partner_info['file_path']}")
                return
                
            file_content_str = file_content.decode('utf-8', errors='replace')
            
            # Match file to a profile
            matched_profile = await self.profile_matcher.match_by_filename(
                partner_info["tenant_id"], 
                webhook_data.name
            )
            
            if not matched_profile:
                logger.warning(f"No matching profile found for file: {webhook_data.name}")
                # Use default processing or skip
                return
            
            logger.info(f"Processing file {webhook_data.name} with profile {matched_profile.name}")
            
            # Process the file using the validation service
            await self.validation_service.process_edi_file(
                edi_data=file_content_str,
                tenant_id=partner_info["tenant_id"],
                user_id="sftp-webhook",
                username=webhook_data.username,
                profile_name=matched_profile.name,
                file_name=webhook_data.name,
                source="SFTP_WEBHOOK"
            )
            
            # Archive the original file
            await self._archive_processed_file(partner_info["file_path"], webhook_data.name)
            
            logger.info(f"Successfully processed SFTP upload: {webhook_data.name}")
            
        except Exception as e:
            logger.error(f"Error processing file {webhook_data.name}: {e}", exc_info=True)
            raise

    async def _get_partner_by_id(self, tenant_id: str, partner_id: int) -> Optional[TradingPartner]:
        """Get trading partner by tenant and ID."""
        query = select(TradingPartner).filter_by(
            tenant_id=tenant_id,
            id=partner_id,
            sftp_enabled=True
        )
        result = await self.db.execute(query)
        return result.scalars().first()
        
    async def _get_partner_by_username(self, tenant_id: str, username: str) -> Optional[TradingPartner]:
        """Get trading partner by tenant and SFTP username."""
        query = select(TradingPartner).filter_by(
            tenant_id=tenant_id,
            sftp_username=username,
            sftp_enabled=True
        )
        result = await self.db.execute(query)
        return result.scalars().first()

    async def _archive_processed_file(self, original_path: str, file_name: str):
        """Move processed file to archive folder."""
        try:
            # Generate archive path: tenants/tenant-a/partners/3/in/archive/20250810_143022_filename.edi
            path_parts = original_path.split('/')
            archive_path = '/'.join(path_parts[:-1]) + '/archive/'
            
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            archive_file_path = f"{archive_path}{timestamp}_{file_name}"
            
            # Copy file to archive location
            file_content = storage_client.download(original_path)
            if file_content:
                storage_client.upload(file_content, archive_file_path)
                logger.info(f"Archived file to: {archive_file_path}")
                
                # TODO: Delete original file after successful archive
                # For now, we'll leave it for safety
            
        except Exception as e:
            logger.error(f"Error archiving file {original_path}: {e}")

    async def _queue_for_processing(self, webhook_data: SftpUploadWebhook, partner_info: dict):
        """Queue file for later processing when system is overloaded."""
        try:
            # TODO: Implement database queue table for overflow processing
            # For now, just log that it would be queued
            logger.warning(f"File {webhook_data.name} would be queued - queue system not yet implemented")
            
        except Exception as e:
            logger.error(f"Error queuing file {webhook_data.name}: {e}", exc_info=True)