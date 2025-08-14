from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from src.core.database import Base


class ProcessingLog(Base):
    """
    General processing log for EDI validation transactions.
    This table tracks all validation processing regardless of source (API, SFTP, Manual).
    
    Note: This is separate from FileProcessingLog which handles SFTP-specific file processing.
    """
    __tablename__ = 'processing_logs'
    __table_args__ = {'schema': 'public'}

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(50), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Source information
    source = Column(String(20), nullable=False)  # 'API', 'SFTP', 'SFTP_WEBHOOK', 'MANUAL'
    file_name = Column(String(255), nullable=True)  # Only populated for file-based processing
    file_size_bytes = Column(Integer, nullable=True)
    
    # Validation results
    validation_result = Column(String(10), nullable=False)  # 'VALID', 'INVALID', 'ERROR'
    processing_time_ms = Column(Integer, nullable=True)
    error_count = Column(Integer, nullable=False, default=0)
    
    # Schema and profile information
    schema_name = Column(String(255), nullable=True)
    snip_level_used = Column(String(10), nullable=True)  # SNIP1-SNIP5
    # profile_id = Column(Integer, ForeignKey('public.partner_profiles.id'), nullable=True)
    
    # Acknowledgment generation
    ta1_generated = Column(Boolean, nullable=False, default=False)
    ta1_999_generated = Column(Boolean, nullable=False, default=False)
    
    # Object storage paths for processed content
    original_content_path = Column(String(500), nullable=True)  # MinIO object key
    ta1_content_path = Column(String(500), nullable=True)       # MinIO object key for TA1
    ta1_999_content_path = Column(String(500), nullable=True)   # MinIO object key for 999

    def __init__(self, **kwargs):
        """Initialize with proper defaults for non-database testing"""
        # Set Python defaults for model instances (not just database defaults)
        kwargs.setdefault('error_count', 0)
        kwargs.setdefault('ta1_generated', False)
        kwargs.setdefault('ta1_999_generated', False)
        super().__init__(**kwargs)
    
    # Relationships removed due to refactoring
    # profile = relationship("PartnerProfile", back_populates="processing_logs")
    
    def __repr__(self):
        return (f"<ProcessingLog(id={self.id}, tenant='{self.tenant_id}', "
                f"source='{self.source}', result='{self.validation_result}', "
                f"snip_level='{self.snip_level_used}')>")