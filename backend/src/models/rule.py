from sqlalchemy import Column, Integer, String, Text, JSON
from src.core.database import Base

class Rule(Base):
    __tablename__ = 'rules'
    __table_args__ = {'schema': 'public'}

    id = Column(Integer, primary_key=True, index=True)
    rule_code = Column(String, unique=True, nullable=False, index=True)
    description = Column(Text, nullable=False)
    snip_level = Column(Integer, nullable=True)
    implementation_guide = Column(String, nullable=False, index=True)
    validation_logic = Column(JSON, nullable=False)