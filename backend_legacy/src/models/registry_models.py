"""
Registry models for NiFi Registry integration.

This module contains models that treat NiFi Registry as the source of truth
for flow definitions, with the database storing only references and metadata.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean, CheckConstraint, Column, DateTime,
    Integer, String, Text
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.core.database import Base


class RegistryTemplate(Base):
    """
    Reference to NiFi Registry flow with metadata.
    
    This model stores references to flows in NiFi Registry along with
    business metadata. The actual flow definition lives in Registry.
    """
    __tablename__ = "registry_templates"
    
    # Registry references (UUIDs from NiFi Registry)
    template_id = Column(PG_UUID(as_uuid=True), primary_key=True)  # Registry flow ID
    bucket_id = Column(PG_UUID(as_uuid=True), nullable=False)      # Registry bucket ID
    current_version = Column(Integer, nullable=False, default=1)
    
    # Basic metadata
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    scope = Column(String, nullable=False)  # GLOBAL, TENANT
    tenant_id = Column(String, nullable=True)  # NULL for global templates
    
    # Status and lifecycle
    status = Column(String, nullable=False, default='ACTIVE')  # ACTIVE, DEPRECATED, ARCHIVED
    is_featured = Column(Boolean, nullable=False, default=False)  # Show in featured templates
    usage_count = Column(Integer, nullable=False, default=0)  # Track popularity
    
    # Metadata
    created_by = Column(String, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    deprecated_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    bucket = relationship(
        "RegistryBucket", 
        primaryjoin="RegistryTemplate.bucket_id == foreign(RegistryBucket.bucket_id)",
        uselist=False
    )
    workflows = relationship(
        "Workflow", 
        back_populates="template",
        cascade="all, delete-orphan",
        primaryjoin="RegistryTemplate.template_id == foreign(Workflow.template_id)"
    )
    
    # Constraints
    __table_args__ = (
        CheckConstraint("scope IN ('GLOBAL', 'TENANT')", name='valid_scope'),
        CheckConstraint(
            "(scope = 'GLOBAL' AND tenant_id IS NULL) OR (scope = 'TENANT' AND tenant_id IS NOT NULL)",
            name='tenant_scope_consistency'
        ),
        {'schema': 'public'}
    )

    def __repr__(self) -> str:
        return f"<RegistryTemplate(id={self.template_id}, name={self.name}, scope={self.scope})>"

    @property
    def is_global(self) -> bool:
        """Check if this is a global platform template."""
        return self.scope == 'GLOBAL'

    @property
    def is_tenant_template(self) -> bool:
        """Check if this is a tenant-specific template."""
        return self.scope == 'TENANT'

    def can_be_modified_by_tenant(self, tenant_id: str) -> bool:
        """Check if a tenant can modify this template."""
        return self.is_tenant_template and self.tenant_id == tenant_id

    def increment_usage_count(self) -> None:
        """Increment the usage counter for this template."""
        self.usage_count += 1

    def deprecate(self) -> None:
        """Mark template as deprecated."""
        self.status = 'DEPRECATED'
        self.deprecated_at = datetime.now(timezone.utc)


class RegistryBucket(Base):
    """
    Reference to NiFi Registry bucket with metadata.
    
    This model tracks Registry buckets used for organizing templates.
    """
    __tablename__ = "registry_buckets"
    
    # Registry reference
    bucket_id = Column(PG_UUID(as_uuid=True), primary_key=True)  # Registry bucket ID
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    
    # Bucket organization
    scope = Column(String, nullable=False)  # GLOBAL, TENANT
    tenant_id = Column(String, nullable=True)  # NULL for global buckets
    
    # Metadata
    created_by = Column(String, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    
    # Constraints
    __table_args__ = (
        CheckConstraint("scope IN ('GLOBAL', 'TENANT')", name='valid_bucket_scope'),
        CheckConstraint(
            "(scope = 'GLOBAL' AND tenant_id IS NULL) OR (scope = 'TENANT' AND tenant_id IS NOT NULL)",
            name='bucket_tenant_scope_consistency'
        ),
        {'schema': 'public'}
    )

    def __repr__(self) -> str:
        return f"<RegistryBucket(id={self.bucket_id}, name={self.name}, scope={self.scope})>"

    @property
    def is_global(self) -> bool:
        """Check if this is a global bucket."""
        return self.scope == 'GLOBAL'

    @property
    def is_tenant_bucket(self) -> bool:
        """Check if this is a tenant-specific bucket."""
        return self.scope == 'TENANT'