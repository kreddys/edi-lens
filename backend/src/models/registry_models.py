"""
Registry-first models for NiFi workflow management.

This module contains models that treat NiFi Registry as the source of truth
for flow definitions, with the database storing only references and metadata.
"""

from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    Boolean, CheckConstraint, Column, DateTime, ForeignKey, 
    Integer, String, Text
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import relationship, foreign
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
    workflow_instances = relationship(
        "WorkflowInstance", 
        back_populates="template",
        cascade="all, delete-orphan",
        primaryjoin="RegistryTemplate.template_id == foreign(WorkflowInstance.template_id)"
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
        self.deprecated_at = datetime.utcnow()


class WorkflowInstance(Base):
    """
    Deployed instance of a Registry template.
    
    This model tracks deployed NiFi process groups that were created
    from Registry templates, along with their configuration and status.
    """
    __tablename__ = "workflow_instances"
    
    # Instance identification
    workflow_id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    tenant_id = Column(String, nullable=False)
    
    # Registry template reference
    template_id = Column(PG_UUID(as_uuid=True), nullable=False)
    template_version = Column(Integer, nullable=False)  # Specific version deployed
    
    # Instance configuration (simple key-value pairs for parameters)
    configuration = Column(JSONB, nullable=False, default=dict)
    
    # NiFi deployment tracking
    nifi_process_group_id = Column(PG_UUID(as_uuid=True), nullable=True)
    nifi_parameter_context_id = Column(PG_UUID(as_uuid=True), nullable=True)
    nifi_registry_client_id = Column(String, nullable=True)  # NiFi's registry client ID
    
    # Version control information from NiFi
    version_control_info = Column(JSONB, nullable=True)  # NiFi version control metadata
    
    # Status and lifecycle
    status = Column(String, nullable=False, default='CREATED')  # CREATED, DEPLOYED, RUNNING, STOPPED, ERROR, DELETED
    
    # Metadata
    created_by = Column(String, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    deployed_at = Column(DateTime(timezone=True), nullable=True)
    last_started_at = Column(DateTime(timezone=True), nullable=True)
    last_stopped_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    template = relationship(
        "RegistryTemplate", 
        back_populates="workflow_instances",
        primaryjoin="foreign(WorkflowInstance.template_id) == RegistryTemplate.template_id"
    )
    
    # Constraints
    __table_args__ = (
        CheckConstraint(
            "status IN ('CREATED', 'DEPLOYED', 'RUNNING', 'STOPPED', 'ERROR', 'DELETED')", 
            name='valid_status'
        ),
        {'schema': 'public'}
    )

    def __repr__(self) -> str:
        return f"<WorkflowInstance(id={self.workflow_id}, name={self.name}, tenant={self.tenant_id})>"

    @property
    def is_deployed(self) -> bool:
        """Check if workflow is deployed to NiFi."""
        return self.nifi_process_group_id is not None

    @property
    def is_running(self) -> bool:
        """Check if workflow is currently running."""
        return self.status == 'RUNNING'

    def mark_deployed(self, process_group_id: str, parameter_context_id: Optional[str] = None) -> None:
        """Mark workflow as deployed with NiFi IDs."""
        self.nifi_process_group_id = process_group_id
        self.nifi_parameter_context_id = parameter_context_id
        self.status = 'DEPLOYED'
        self.deployed_at = datetime.utcnow()

    def mark_running(self) -> None:
        """Mark workflow as running."""
        self.status = 'RUNNING'
        self.last_started_at = datetime.utcnow()

    def mark_stopped(self) -> None:
        """Mark workflow as stopped."""
        self.status = 'STOPPED'
        self.last_stopped_at = datetime.utcnow()

    def mark_error(self) -> None:
        """Mark workflow as having an error."""
        self.status = 'ERROR'

    def mark_deleted(self) -> None:
        """Mark workflow as deleted."""
        self.status = 'DELETED'

    def update_version_control_info(self, version_info: dict) -> None:
        """Update version control information from NiFi."""
        self.version_control_info = version_info


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