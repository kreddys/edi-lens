import uuid
import enum
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, BigInteger, Text, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from src.core.database import Base


class FileProcessingStatus(str, enum.Enum):
    DISCOVERED = "DISCOVERED"        # File found in directory
    LOCKED = "LOCKED"               # File locked for processing
    PROCESSING = "PROCESSING"       # Being processed by validation service
    COMPLETED = "COMPLETED"         # Successfully processed
    FAILED = "FAILED"              # Processing failed
    ARCHIVED = "ARCHIVED"          # Moved to archive
    RESPONSE_PENDING = "RESPONSE_PENDING"  # Waiting to deliver response
    RESPONSE_DELIVERED = "RESPONSE_DELIVERED"  # Response successfully delivered
    RESPONSE_FAILED = "RESPONSE_FAILED"  # Failed to deliver response


class FileProcessingLog(Base):
    __tablename__ = 'file_processing_logs'
    __table_args__ = {'schema': 'public'}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String, nullable=False, index=True)
    partner_id = Column(Integer, ForeignKey('public.trading_partners.id'), nullable=False)
    sftp_config_id = Column(Integer, ForeignKey('public.sftp_configurations.id'), nullable=False)
    validation_transaction_id = Column(UUID(as_uuid=True), ForeignKey('public.validation_transactions.id'), nullable=True)
    
    # File Information
    source_filename = Column(String, nullable=False)
    source_directory = Column(String, nullable=False)
    source_file_size = Column(BigInteger, nullable=True)
    source_file_hash = Column(String, nullable=True)  # For deduplication tracking
    
    # Processing Status and Timing
    status = Column(String, nullable=False, default=FileProcessingStatus.DISCOVERED.value)
    processing_started_at = Column(DateTime(timezone=True), nullable=True)
    processing_completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Lock Information (for concurrent processing prevention)
    locked_by = Column(String, nullable=True)      # Process/worker ID
    locked_at = Column(DateTime(timezone=True), nullable=True)
    lock_expires_at = Column(DateTime(timezone=True), nullable=True)  # Lock timeout
    
    # Response Information
    response_filename = Column(String, nullable=True)
    response_directory = Column(String, nullable=True)
    response_delivered_at = Column(DateTime(timezone=True), nullable=True)
    response_delivery_attempts = Column(Integer, nullable=False, default=0)
    
    # Error Handling
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    max_retries = Column(Integer, nullable=False, default=3)
    
    def __init__(self, **kwargs):
        """Initialize with proper defaults for non-database testing"""
        # Set defaults for Python instance creation (not just database defaults)
        kwargs.setdefault('status', FileProcessingStatus.DISCOVERED.value)
        kwargs.setdefault('retry_count', 0)
        kwargs.setdefault('max_retries', 3)
        kwargs.setdefault('response_delivery_attempts', 0)
        super().__init__(**kwargs)
    
    # Archive Information
    archived_at = Column(DateTime(timezone=True), nullable=True)
    archive_location = Column(String, nullable=True)  # Object storage key or file path
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    partner = relationship("TradingPartner")
    sftp_config = relationship("SftpConfiguration", back_populates="processing_logs")
    validation_transaction = relationship("ValidationTransaction")

    @property
    def is_locked(self) -> bool:
        """Check if file is currently locked"""
        if not self.locked_at:
            return False
        return self.lock_expires_at and self.lock_expires_at > func.now()
    
    @property
    def can_retry(self) -> bool:
        """Check if file can be retried after failure"""
        return self.retry_count < self.max_retries

    @property
    def processing_duration_seconds(self) -> int:
        """Calculate processing duration in seconds"""
        if self.processing_started_at and self.processing_completed_at:
            delta = self.processing_completed_at - self.processing_started_at
            return int(delta.total_seconds())
        return 0