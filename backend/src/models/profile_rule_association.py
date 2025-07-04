from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, JSON, Enum as SQLAlchemyEnum
from sqlalchemy.orm import relationship
import enum
from src.core.database import Base

class SeverityLevel(enum.Enum):
    error = "error"
    warning = "warning"
    info = "info"

class ProfileRuleAssociation(Base):
    __tablename__ = 'profile_rule_associations'

    id = Column(Integer, primary_key=True, index=True)
    # tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False)
    profile_id = Column(Integer, ForeignKey('partner_profiles.id'), nullable=False)
    rule_id = Column(Integer, ForeignKey('rules.id'), nullable=False)

    is_enabled = Column(Boolean, default=True, nullable=False)
    override_severity = Column(SQLAlchemyEnum(SeverityLevel), nullable=True)
    override_params = Column(JSON, nullable=True)

    # tenant = relationship("Tenant")
    profile = relationship("PartnerProfile")
    rule = relationship("Rule")