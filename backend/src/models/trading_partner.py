from sqlalchemy import Column, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from src.core.database import Base

class TradingPartner(Base):
    __tablename__ = 'trading_partners'

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=True)

    # Relationships
    profiles = relationship("PartnerProfile", back_populates="partner", cascade="all, delete-orphan")
    sftp_configuration = relationship("SftpConfiguration", back_populates="partner", uselist=False, cascade="all, delete-orphan")
    file_processing_logs = relationship("FileProcessingLog", back_populates="partner")

    __table_args__ = (
        UniqueConstraint('tenant_id', 'name', name='_tenant_partner_name_uc'),
        {'schema': 'public'}
    )