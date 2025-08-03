"""
SFTP File Processor Service
This service handles automated processing of files uploaded via SFTP.
"""

import asyncio
import logging
import re
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from src.models.sftp_configuration import SftpConfiguration
from src.models.file_processing_log import FileProcessingLog, FileProcessingStatus
from src.models.processing_schedule import ProcessingSchedule
from src.models.validation_transaction import ValidationTransaction, SourceType
from src.services.validation_service import ValidationService
from src.core.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


class FileDiscoveryService:
    """Service for discovering files in multi-tenant SFTP directories."""
    
    def __init__(self, sftp_root: str = "/sftp/tenants"):
        self.sftp_root = Path(sftp_root)
    
    async def discover_files(self, config: SftpConfiguration) -> List[Path]:
        """Discover files in a partner's inbound directory that match their patterns."""
        # Use the multi-tenant inbound directory path
        inbound_dir = Path(config.get_inbound_directory_path(str(self.sftp_root)))
        
        if not inbound_dir.exists():
            logger.warning(f"Inbound directory does not exist: {inbound_dir}")
            return []
        
        discovered_files = []
        patterns = self._parse_file_patterns(config.file_name_patterns)
        
        try:
            for file_path in inbound_dir.iterdir():
                if file_path.is_file() and self._matches_patterns(file_path.name, patterns):
                    # Check file size limit
                    if file_path.stat().st_size <= config.max_file_size_bytes:
                        discovered_files.append(file_path)
                    else:
                        logger.warning(f"File {file_path} exceeds size limit: {file_path.stat().st_size} > {config.max_file_size_bytes}")
        except Exception as e:
            logger.error(f"Error discovering files in {inbound_dir}: {e}")
        
        return discovered_files
    
    def _parse_file_patterns(self, patterns_json: Optional[str]) -> List[str]:
        """Parse JSON file patterns into a list."""
        if not patterns_json:
            return ["*.edi", "*.x12"]  # Default patterns
        
        try:
            import json
            patterns = json.loads(patterns_json)
            return patterns if isinstance(patterns, list) else [patterns]
        except Exception as e:
            logger.error(f"Error parsing file patterns {patterns_json}: {e}")
            return ["*.edi", "*.x12"]
    
    def _matches_patterns(self, filename: str, patterns: List[str]) -> bool:
        """Check if filename matches any of the patterns."""
        import fnmatch
        return any(fnmatch.fnmatch(filename, pattern) for pattern in patterns)


class FileLockingService:
    """Service for managing file processing locks."""
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
    
    async def acquire_lock(
        self, 
        config: SftpConfiguration, 
        file_path: Path,
        worker_id: str
    ) -> Optional[FileProcessingLog]:
        """Attempt to acquire a lock on a file for processing."""
        file_hash = self._calculate_file_hash(file_path)
        
        # Check if file is already being processed or completed
        result = await self.db.execute(
            select(FileProcessingLog).where(
                and_(
                    FileProcessingLog.sftp_config_id == config.id,
                    FileProcessingLog.source_filename == file_path.name,
                    FileProcessingLog.source_file_hash == file_hash
                )
            )
        )
        existing_log = result.scalar_one_or_none()
        
        if existing_log:
            if existing_log.status in [FileProcessingStatus.COMPLETED.value, FileProcessingStatus.ARCHIVED.value]:
                logger.info(f"File {file_path.name} already processed successfully")
                return None
            elif existing_log.is_locked and existing_log.lock_expires_at > datetime.utcnow():
                logger.info(f"File {file_path.name} is currently locked by {existing_log.locked_by}")
                return None
            elif existing_log.status == FileProcessingStatus.FAILED.value and not existing_log.can_retry:
                logger.info(f"File {file_path.name} has exceeded retry limit")
                return None
        
        # Create or update processing log with lock
        if existing_log:
            # Update existing log to acquire lock
            existing_log.status = FileProcessingStatus.LOCKED.value
            existing_log.locked_by = worker_id
            existing_log.locked_at = datetime.utcnow()
            existing_log.lock_expires_at = datetime.utcnow() + timedelta(minutes=30)  # 30 min lock
            processing_log = existing_log
        else:
            # Create new processing log
            processing_log = FileProcessingLog(
                tenant_id=config.tenant_id,
                partner_id=config.partner_id,
                sftp_config_id=config.id,
                source_filename=file_path.name,
                source_directory=str(file_path.parent),
                source_file_size=file_path.stat().st_size,
                source_file_hash=file_hash,
                status=FileProcessingStatus.LOCKED.value,
                locked_by=worker_id,
                locked_at=datetime.utcnow(),
                lock_expires_at=datetime.utcnow() + timedelta(minutes=30)
            )
            self.db.add(processing_log)
        
        try:
            await self.db.commit()
            await self.db.refresh(processing_log)
            logger.info(f"Acquired lock on file {file_path.name} for worker {worker_id}")
            return processing_log
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to acquire lock on file {file_path.name}: {e}")
            return None
    
    async def release_lock(self, processing_log: FileProcessingLog, status: FileProcessingStatus):
        """Release the lock on a file and update its status."""
        processing_log.status = status.value
        processing_log.locked_by = None
        processing_log.locked_at = None
        processing_log.lock_expires_at = None
        processing_log.processing_completed_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(processing_log)
        logger.info(f"Released lock on file {processing_log.source_filename} with status {status.value}")
    
    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of file for deduplication."""
        import hashlib
        
        hash_sha256 = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except Exception as e:
            logger.error(f"Error calculating hash for {file_path}: {e}")
            return f"error-{datetime.utcnow().timestamp()}"


class SftpFileProcessor:
    """Main service for processing SFTP files."""
    
    def __init__(self):
        self.discovery_service = FileDiscoveryService()
        self.worker_id = f"processor-{os.getpid()}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        logger.info(f"Initialized SFTP File Processor with worker ID: {self.worker_id}")
    
    async def process_files_for_config(self, config: SftpConfiguration):
        """Process files for a specific SFTP configuration."""
        async with AsyncSessionLocal() as db_session:
            locking_service = FileLockingService(db_session)
            validation_service = ValidationService(db_session)
            
            # Discover files
            files = await self.discovery_service.discover_files(config)
            logger.info(f"Discovered {len(files)} files for partner {config.partner_id}")
            
            for file_path in files:
                try:
                    # Attempt to acquire lock
                    processing_log = await locking_service.acquire_lock(config, file_path, self.worker_id)
                    if not processing_log:
                        continue
                    
                    # Update status to processing
                    processing_log.status = FileProcessingStatus.PROCESSING.value
                    processing_log.processing_started_at = datetime.utcnow()
                    await db_session.commit()
                    
                    # Read and process file
                    file_content = await self._read_file_content(file_path)
                    if not file_content:
                        await locking_service.release_lock(processing_log, FileProcessingStatus.FAILED)
                        continue
                    
                    # Process through validation service
                    validation_response = await validation_service.process_edi_file(
                        edi_data=file_content,
                        file_name=file_path.name,
                        tenant_id=config.tenant_id,
                        user_id="sftp-system",
                        username="sftp-processor"
                    )
                    
                    # Update validation transaction with SFTP source info
                    await self._update_validation_transaction_for_sftp(
                        db_session, processing_log, config
                    )
                    
                    # Handle response delivery
                    if validation_response.ta1_acknowledgement:
                        await self._deliver_response(
                            config, file_path, validation_response.ta1_acknowledgement, processing_log
                        )
                    
                    # Archive original file
                    await self._archive_file(file_path, config)
                    
                    # Mark as completed
                    await locking_service.release_lock(processing_log, FileProcessingStatus.COMPLETED)
                    logger.info(f"Successfully processed file {file_path.name}")
                    
                except Exception as e:
                    logger.error(f"Error processing file {file_path}: {e}")
                    if 'processing_log' in locals():
                        processing_log.error_message = str(e)[:1000]  # Truncate to fit DB field
                        processing_log.retry_count += 1
                        
                        if processing_log.can_retry:
                            await locking_service.release_lock(processing_log, FileProcessingStatus.FAILED)
                        else:
                            await locking_service.release_lock(processing_log, FileProcessingStatus.FAILED)
                            logger.error(f"File {file_path.name} exceeded retry limit")
    
    async def _read_file_content(self, file_path: Path) -> Optional[str]:
        """Read file content as string."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            # Try with latin-1 encoding for legacy files
            try:
                with open(file_path, 'r', encoding='latin-1') as f:
                    return f.read()
            except Exception as e:
                logger.error(f"Error reading file {file_path} with latin-1: {e}")
                return None
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            return None
    
    async def _update_validation_transaction_for_sftp(
        self, 
        db_session: AsyncSession, 
        processing_log: FileProcessingLog, 
        config: SftpConfiguration
    ):
        """Update the validation transaction with SFTP source information."""
        # Find the validation transaction created by the validation service
        # This is a bit of a workaround since we don't have direct access to the transaction ID
        result = await db_session.execute(
            select(ValidationTransaction).where(
                and_(
                    ValidationTransaction.tenant_id == config.tenant_id,
                    ValidationTransaction.original_filename == processing_log.source_filename,
                    ValidationTransaction.username == "sftp-processor"
                )
            ).order_by(ValidationTransaction.created_at.desc()).limit(1)
        )
        validation_transaction = result.scalar_one_or_none()
        
        if validation_transaction:
            validation_transaction.source_type = SourceType.SFTP
            validation_transaction.source_partner_id = config.partner_id
            validation_transaction.source_file_path = processing_log.source_directory + "/" + processing_log.source_filename
            
            # Link the processing log to the validation transaction
            processing_log.validation_transaction_id = validation_transaction.id
            
            await db_session.commit()
    
    async def _deliver_response(
        self, 
        config: SftpConfiguration, 
        original_file: Path, 
        response_content: str,
        processing_log: FileProcessingLog
    ):
        """Deliver response to partner's outbound directory."""
        outbound_dir = Path(config.get_outbound_directory_path())
        
        # Create outbound directory if it doesn't exist
        outbound_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate response filename
        response_filename = self._generate_response_filename(config, original_file.name)
        response_path = outbound_dir / response_filename
        
        try:
            with open(response_path, 'w', encoding='utf-8') as f:
                f.write(response_content)
            
            processing_log.response_filename = response_filename
            processing_log.response_directory = str(outbound_dir)
            processing_log.response_delivered_at = datetime.utcnow()
            processing_log.response_delivery_attempts += 1
            
            logger.info(f"Delivered response to {response_path}")
            
        except Exception as e:
            logger.error(f"Error delivering response to {response_path}: {e}")
            processing_log.response_delivery_attempts += 1
            raise
    
    def _generate_response_filename(self, config: SftpConfiguration, original_filename: str) -> str:
        """Generate response filename based on configuration."""
        if config.response_filename_template:
            # Replace placeholders in template
            template = config.response_filename_template
            base_name = Path(original_filename).stem
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            
            response_name = template.replace("{original_name}", base_name)
            response_name = response_name.replace("{timestamp}", timestamp)
            response_name = response_name.replace("{partner_id}", str(config.partner_id))
            
            # Ensure it has an extension
            if not response_name.endswith(('.edi', '.x12', '.txt')):
                response_name += '.edi'
            
            return response_name
        else:
            # Default naming: original_name_ack_timestamp.edi
            base_name = Path(original_filename).stem
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            return f"{base_name}_ack_{timestamp}.edi"
    
    async def _archive_file(self, file_path: Path, config: SftpConfiguration):
        """Move processed file to archive directory."""
        # Archive in the backend processing area, not accessible to partners
        archive_dir = Path(f"/sftp/tenants/{config.tenant_id}/.archive/{config.sftp_username}")
        
        # Create archive directory if it doesn't exist
        archive_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate archive filename with timestamp to avoid conflicts
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        archive_filename = f"{timestamp}_{file_path.name}"
        archive_path = archive_dir / archive_filename
        
        try:
            file_path.rename(archive_path)
            logger.info(f"Archived file to {archive_path}")
        except Exception as e:
            logger.error(f"Error archiving file {file_path} to {archive_path}: {e}")
            # Don't raise - archiving failure shouldn't stop processing