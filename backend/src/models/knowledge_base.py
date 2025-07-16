# FILE: backend/src/models/knowledge_base.py
import enum
from sqlalchemy import (
    Column, Integer, String, Text, Enum as SQLAlchemyEnum,
    ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import relationship
from src.core.database import Base

class NodeType(str, enum.Enum):
    """Enum for the different types of nodes in our knowledge graph."""
    GUIDE = "GUIDE"
    LOOP = "LOOP"
    SEGMENT = "SEGMENT"
    ELEMENT = "ELEMENT"
    COMPOSITE = "COMPOSITE"
    RULE = "RULE"

class KnowledgeBaseGuide(Base):
    """Stores metadata about a single implementation guide."""
    __tablename__ = "kb_guides"
    __table_args__ = {'schema': 'public'}

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True, comment="e.g., Health Care Claim: Professional (X222A1)")
    version = Column(String, nullable=False, comment="e.g., 005010X222A1")

    nodes = relationship("KnowledgeBaseNode", back_populates="guide", cascade="all, delete-orphan")

class KnowledgeBaseNode(Base):
    """Represents a single node (a piece of knowledge) in the guide's graph."""
    __tablename__ = "kb_nodes"
    __table_args__ = (
        UniqueConstraint('guide_id', 'node_key', name='_guide_node_key_uc'),
        {'schema': 'public'}
    )

    id = Column(Integer, primary_key=True, index=True)
    guide_id = Column(Integer, ForeignKey("public.kb_guides.id"), nullable=False)
    parent_id = Column(Integer, ForeignKey("public.kb_nodes.id"), nullable=True, index=True)

    node_type = Column(SQLAlchemyEnum(NodeType), nullable=False)
    node_key = Column(String, nullable=False, index=True, comment="e.g., 2010AA.NM1.NM102")
    name = Column(String, nullable=False, comment="e.g., Billing Provider Name")
    raw_text = Column(Text, nullable=False, comment="The full text content of this specific node.")
    
    guide = relationship("KnowledgeBaseGuide", back_populates="nodes")
    parent = relationship("KnowledgeBaseNode", remote_side=[id], back_populates="children")
    children = relationship("KnowledgeBaseNode", back_populates="parent", cascade="all, delete-orphan")
    vector_map = relationship("KnowledgeBaseVectorMap", back_populates="node", uselist=False, cascade="all, delete-orphan")

class KnowledgeBaseVectorMap(Base):
    """Maps a knowledge base node to its vector embedding in Pinecone."""
    __tablename__ = "kb_node_vectors"
    __table_args__ = {'schema': 'public'}

    id = Column(Integer, primary_key=True, index=True)
    node_id = Column(Integer, ForeignKey("public.kb_nodes.id"), nullable=False, unique=True)
    pinecone_vector_id = Column(String, nullable=False, unique=True, index=True)
    
    node = relationship("KnowledgeBaseNode", back_populates="vector_map")