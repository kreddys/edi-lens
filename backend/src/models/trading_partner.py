# FILE: backend/src/models/trading_partner.py

from sqlalchemy import Column, Integer, String, Text, UniqueConstraint, Boolean
from sqlalchemy.orm import relationship
from src.core.database import Base

class TradingPartner(Base):
    __tablename__ = 'trading_partners'

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=True)

    # --- SIMPLIFIED SFTP FIELDS ---
    sftp_enabled = Column(Boolean, nullable=False, default=False, server_default='false')
    sftp_username = Column(String, nullable=True, unique=True)
    
    # Relationships
    profiles = relationship("PartnerProfile", back_populates="partner", cascade="all, delete-orphan")
    
    # --- THIS IS THE FIX: Remove the relationships to the deleted models ---
    # sftp_configuration = relationship("SftpConfiguration", back_populates="partner", uselist=False, cascade="all, delete-orphan")
    # file_processing_logs = relationship("FileProcessingLog", back_populates="partner")
    # --- END OF FIX ---

    __table_args__ = (
        UniqueConstraint('tenant_id', 'name', name='_tenant_partner_name_uc'),
        {'schema': 'public'}
    )