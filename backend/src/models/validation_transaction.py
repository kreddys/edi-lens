# FILE: backend/src/models/validation_transaction.py

import uuid
import enum
from sqlalchemy import Column, String, DateTime, Enum as SQLAlchemyEnum, ForeignKey, Integer, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from src.core.database import Base

class ValidationStatus(str, enum.Enum):
    PENDING = "PENDING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"

class SourceType(str, enum.Enum):
    API = "API"
    SFTP = "SFTP"
    MANUAL = "MANUAL"

class ValidationTransaction(Base):
    __tablename__ = 'validation_transactions'
    __table_args__ = {'schema': 'public'}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String, nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    username = Column(String, nullable=True)
    
    
    
    status = Column(SQLAlchemyEnum(ValidationStatus), nullable=False, default=ValidationStatus.PENDING)
    original_filename = Column(String, nullable=False)
    
    request_object_key = Column(String, nullable=False)
    ta1_object_key = Column(String, nullable=True)
    response_999_object_key = Column(String, nullable=True)
    
    source_type = Column(SQLAlchemyEnum(SourceType), nullable=False, default=SourceType.API)
    
    source_file_path = Column(String, nullable=True)
    response_delivered = Column(Boolean, nullable=False, default=False)
    response_delivery_attempts = Column(Integer, nullable=False, default=0)
    response_delivered_at = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships removed due to refactoring
    # profile = relationship("PartnerProfile")
    # source_partner = relationship("TradingPartner")
    
    # --- THIS IS THE FIX: Remove the relationship to the deleted model ---
    # file_processing_log = relationship("FileProcessingLog", back_populates="validation_transaction", uselist=False)
    # --- END OF FIX ---