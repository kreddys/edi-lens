from sqlalchemy import Column, Integer, String, UniqueConstraint
from src.core.database import Base

class TradingPartner(Base):
    __tablename__ = 'trading_partners'

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True, index=True)
    edi_sender_id = Column(String, nullable=False, unique=True)

    __table_args__ = (UniqueConstraint('name', name='uq_partner_name'),)