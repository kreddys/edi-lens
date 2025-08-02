import uuid
# --- THIS IS THE FIX ---
# Add 'Integer' to the list of imports from sqlalchemy
from sqlalchemy import Column, String, DateTime, Enum as SQLAlchemyEnum, ForeignKey, Integer
# --- END OF FIX ---
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import enum

from src.core.database import Base

class ValidationStatus(str, enum.Enum):
    PENDING = "PENDING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"

class ValidationTransaction(Base):
    __tablename__ = 'validation_transactions'
    __table_args__ = {'schema': 'public'}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String, nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    username = Column(String, nullable=True)
    
    partner_profile_id = Column(Integer, ForeignKey('public.partner_profiles.id'), nullable=True)
    
    status = Column(SQLAlchemyEnum(ValidationStatus), nullable=False, default=ValidationStatus.PENDING)
    original_filename = Column(String, nullable=False)
    
    request_object_key = Column(String, nullable=False)
    ta1_object_key = Column(String, nullable=True)
    response_999_object_key = Column(String, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    profile = relationship("PartnerProfile")