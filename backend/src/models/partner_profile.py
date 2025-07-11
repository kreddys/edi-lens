from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from src.core.database import Base

class PartnerProfile(Base):
    __tablename__ = 'partner_profiles'
    __table_args__ = {'schema': 'public'}

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String, nullable=False, index=True)
    partner_id = Column(Integer, ForeignKey('public.trading_partners.id'), nullable=False)
    
    name = Column(String, nullable=False)
    implementation_guide = Column(String, nullable=False, index=True)
    priority = Column(Integer, nullable=False, default=10)
    snip_level_enabled = Column(Integer, nullable=False, default=1)

    partner = relationship("TradingPartner", back_populates="profiles")
    criteria = relationship("ProfileCriterion", back_populates="profile", cascade="all, delete-orphan")