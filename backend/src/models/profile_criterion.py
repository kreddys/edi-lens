from sqlalchemy import Column, Integer, String, ForeignKey, Enum as SQLAlchemyEnum
from sqlalchemy.orm import relationship
import enum
from src.core.database import Base

class FieldSource(enum.Enum):
    ISA = "ISA"
    GS = "GS"
    FILENAME = "FILENAME"

class Operator(enum.Enum):
    EQUALS = "EQUALS"
    STARTS_WITH = "STARTS_WITH"
    CONTAINS = "CONTAINS"

class ProfileCriterion(Base):
    __tablename__ = 'profile_criteria'

    id = Column(Integer, primary_key=True, index=True)
    # tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False)
    profile_id = Column(Integer, ForeignKey('partner_profiles.id'), nullable=False)
    
    field_source = Column(SQLAlchemyEnum(FieldSource), nullable=False)
    field_identifier = Column(String, nullable=False)
    operator = Column(SQLAlchemyEnum(Operator), nullable=False)
    value = Column(String, nullable=False)

    # tenant = relationship("Tenant")
    profile = relationship("PartnerProfile")