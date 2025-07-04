from sqlalchemy import Column, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from src.core.database import Base

class TradingPartner(Base):
    __tablename__ = 'trading_partners'

    id = Column(Integer, primary_key=True, index=True)
    # The tenant_id concept is managed by Keycloak realms/groups, not a direct FK.
    # We remove this to match the simplified architecture.
    # tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False)
    name = Column(String, nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)

    profiles = relationship("PartnerProfile", back_populates="partner", cascade="all, delete-orphan")

    # The name is now globally unique
    __table_args__ = (
        UniqueConstraint('name', name='_partner_name_uc'),
    )