from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from src.core.database import Base

class PartnerConfiguration(Base):
    __tablename__ = 'partner_configurations'

    id = Column(Integer, primary_key=True, index=True)
    partner_id = Column(Integer, ForeignKey('trading_partners.id'), nullable=False)
    implementation_guide = Column(String, nullable=False)
    snip_level_enabled = Column(Integer, nullable=False, default=1)

    partner = relationship("TradingPartner")