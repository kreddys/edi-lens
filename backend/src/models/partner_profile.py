from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, DateTime, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from src.core.database import Base

class PartnerProfile(Base):
    __tablename__ = 'partner_profiles'
    __table_args__ = {'schema': 'public'}

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String, nullable=False, index=True)
    partner_id = Column(Integer, ForeignKey('public.trading_partners.id'), nullable=False)
    
    name = Column(String, nullable=False)
    implementation_guide = Column(String, nullable=False, index=True)
    
    # Schema configuration
    validation_schema_name = Column(String, nullable=True)
    
    # Enhanced validation configuration
    snip_level = Column(String(10), nullable=False, default='SNIP3')
    generate_ta1 = Column(Boolean, nullable=False, default=True)
    generate_999 = Column(Boolean, nullable=False, default=False)
    custom_validation_rules = Column(JSON, nullable=True)
    
    # Legacy fields (keep for backwards compatibility)
    priority = Column(Integer, nullable=False, default=10)
    snip_level_enabled = Column(Integer, nullable=False, default=1)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def __init__(self, **kwargs):
        """Initialize with proper defaults for non-database testing"""
        # Set Python defaults for model instances (not just database defaults)
        kwargs.setdefault('snip_level', 'SNIP3')
        kwargs.setdefault('generate_ta1', True)
        kwargs.setdefault('generate_999', False)
        kwargs.setdefault('priority', 10)
        kwargs.setdefault('snip_level_enabled', 1)
        super().__init__(**kwargs)

    # Relationships
    partner = relationship("TradingPartner", back_populates="profiles")
    criteria = relationship("ProfileCriterion", back_populates="profile", cascade="all, delete-orphan")
    processing_logs = relationship("ProcessingLog", back_populates="profile", lazy="select")
    
    def __repr__(self):
        return f"<PartnerProfile(id={self.id}, name='{self.name}', snip_level='{self.snip_level}', ta1={self.generate_ta1}, ta1_999={self.generate_999})>"