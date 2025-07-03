from sqlalchemy import Column, Integer, String, ForeignKey, JSON
from sqlalchemy.orm import relationship
from src.core.database import Base

class PartnerRuleOverride(Base):
    __tablename__ = 'partner_rule_overrides'

    id = Column(Integer, primary_key=True, index=True)
    config_id = Column(Integer, ForeignKey('partner_configurations.id'), nullable=False)
    rule_id = Column(Integer, ForeignKey('rules.id'), nullable=False)
    override_action = Column(String, nullable=False) # e.g., 'ignore', 'warn_only'
    modified_params = Column(JSON, nullable=True)

    configuration = relationship("PartnerConfiguration")
    rule = relationship("Rule")