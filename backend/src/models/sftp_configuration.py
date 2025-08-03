import enum
from sqlalchemy import Column, Integer, String, Boolean, Text, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from src.core.database import Base


class AuthenticationType(str, enum.Enum):
    PASSWORD = "PASSWORD"
    SSH_KEY = "SSH_KEY"
    BOTH = "BOTH"


class SftpConfiguration(Base):
    __tablename__ = 'sftp_configurations'
    __table_args__ = (
        UniqueConstraint('tenant_id', 'partner_id', name='_tenant_partner_sftp_uc'),
        {'schema': 'public'}
    )

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String, nullable=False, index=True)
    partner_id = Column(Integer, ForeignKey('public.trading_partners.id'), nullable=False)
    
    # SFTP Access Configuration
    sftp_enabled = Column(Boolean, nullable=False, default=False)
    sftp_username = Column(String, nullable=False)
    authentication_type = Column(String, nullable=False, default=AuthenticationType.PASSWORD.value)
    password_hash = Column(String, nullable=True)  # Hashed password
    ssh_public_key = Column(Text, nullable=True)   # SSH public key content
    
    # Directory Configuration
    inbound_directory = Column(String, nullable=False)   # e.g., "/partners/acme-corp/inbound"
    outbound_directory = Column(String, nullable=False)  # e.g., "/partners/acme-corp/outbound"
    archive_directory = Column(String, nullable=True)    # e.g., "/partners/acme-corp/archive"
    
    # File Processing Rules
    file_name_patterns = Column(Text, nullable=True)     # JSON array of regex patterns
    poll_schedule_id = Column(Integer, ForeignKey('public.processing_schedules.id'), nullable=True)
    poll_enabled = Column(Boolean, nullable=False, default=True)
    
    # Response Configuration
    response_filename_template = Column(String, nullable=True)  # Template: "{original_name}_ack"
    response_filename_regex = Column(String, nullable=True)     # Advanced regex-based naming
    response_timeout_minutes = Column(Integer, nullable=False, default=5)
    
    # File Size Limits (in bytes)
    max_file_size_bytes = Column(Integer, nullable=False, default=52428800)  # 50MB default
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    partner = relationship("TradingPartner", back_populates="sftp_configuration")
    schedule = relationship("ProcessingSchedule")
    processing_logs = relationship("FileProcessingLog", back_populates="sftp_config")
    
    def get_tenant_partner_username(self) -> str:
        """Generate the SFTP username in format: tenant_partner"""
        return f"{self.tenant_id}_{self.sftp_username}"
    
    def get_partner_directory_path(self, sftp_root: str = "/sftp/tenants") -> str:
        """Get the full path to the partner's chroot directory"""
        return f"{sftp_root}/{self.tenant_id}/{self.sftp_username}"
    
    def get_inbound_directory_path(self, sftp_root: str = "/sftp/tenants") -> str:
        """Get the full path to the partner's inbound directory"""
        return f"{self.get_partner_directory_path(sftp_root)}/in"
    
    def get_outbound_directory_path(self, sftp_root: str = "/sftp/tenants") -> str:
        """Get the full path to the partner's outbound directory"""
        return f"{self.get_partner_directory_path(sftp_root)}/out"