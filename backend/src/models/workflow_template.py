"""
Workflow Template models for NiFi workflow management.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from sqlalchemy import (
    ARRAY, Boolean, CheckConstraint, Column, DateTime, ForeignKey, 
    Integer, String, Text, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import relationship, backref, foreign
from sqlalchemy.sql import func

from src.core.database import Base


class WorkflowTemplate(Base):
    """
    Workflow template model for storing reusable NiFi workflow definitions.
    
    Templates can be global (platform-managed) or tenant-specific (user-managed).
    They contain the NiFi flow definition and configuration schema for dynamic UI generation.
    """
    __tablename__ = "workflow_templates"

    # Primary identification
    template_id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String, nullable=False)  # BATCH, REALTIME, TRANSFORMATION, INTEGRATION
    
    # Template scope and ownership
    scope = Column(String, nullable=False)  # GLOBAL, TENANT
    tenant_id = Column(String, nullable=True)  # NULL for global templates
    maintainer = Column(String, nullable=True)  # 'edi-lens-platform' for global, user ID for tenant
    
    # Template lineage
    based_on = Column(String, nullable=True)
    version = Column(String, nullable=False, default='1.0')
    
    # Template definition
    flow_definition = Column(JSONB, nullable=False)
    configuration_schema = Column(JSONB, nullable=False)
    
    # NiFi deployment information
    deployment_method = Column(String, nullable=False, default='registry')  # 'registry' or 'xml'
    nifi_registry_flow_id = Column(String, nullable=True)
    nifi_registry_bucket_id = Column(String, nullable=True)
    
    # Template metadata
    tags = Column(ARRAY(Text), nullable=True)
    features = Column(ARRAY(Text), nullable=True)  # Capabilities provided by template
    documentation = Column(Text, nullable=True)  # Usage instructions
    examples = Column(JSONB, nullable=True)  # Example configurations
    
    # Status and lifecycle
    status = Column(String, nullable=False, default='ACTIVE')  # ACTIVE, DEPRECATED, ARCHIVED
    is_featured = Column(Boolean, nullable=False, default=False)  # Show in featured templates
    usage_count = Column(Integer, nullable=False, default=0)  # Track popularity
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    deprecated_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships using primaryjoin with foreign annotation for deferred resolution
    versions = relationship(
        "TemplateVersion", 
        back_populates="template", 
        cascade="all, delete-orphan",
        primaryjoin="WorkflowTemplate.template_id == foreign(TemplateVersion.template_id)"
    )
    usage_records = relationship(
        "TemplateUsage", 
        back_populates="template", 
        cascade="all, delete-orphan",
        primaryjoin="WorkflowTemplate.template_id == foreign(TemplateUsage.template_id)"
    )
    workflows = relationship(
        "Workflow", 
        back_populates="template",
        primaryjoin="WorkflowTemplate.template_id == foreign(Workflow.template_id)"
    )
    
    # Self-referencing relationship will be configured after class definition
    
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
        return f"<WorkflowTemplate(id={self.template_id}, name={self.name}, scope={self.scope})>"

    @property
    def is_global(self) -> bool:
        """Check if this is a global platform template."""
        return self.scope == 'GLOBAL'

    @property
    def is_tenant_template(self) -> bool:
        """Check if this is a tenant-specific template."""
        return self.scope == 'TENANT'

    @property
    def is_derived(self) -> bool:
        """Check if this template is based on another template."""
        return self.based_on is not None

    def can_be_modified_by_tenant(self, tenant_id: str) -> bool:
        """Check if a tenant can modify this template."""
        return self.is_tenant_template and self.tenant_id == tenant_id

    def increment_usage_count(self) -> None:
        """Increment the usage counter for this template."""
        self.usage_count += 1


class TemplateVersion(Base):
    """
    Template version model for tracking changes to workflow templates.
    
    Each template can have multiple versions for rollback and change tracking.
    """
    __tablename__ = "template_versions"

    # Primary identification
    version_id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    template_id = Column(String, nullable=False)
    version = Column(String, nullable=False)
    
    # Version content
    flow_definition = Column(JSONB, nullable=False)
    configuration_schema = Column(JSONB, nullable=False)
    
    # Change tracking
    changes = Column(Text, nullable=True)  # Description of changes
    created_by = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    # Version metadata
    is_current = Column(Boolean, nullable=False, default=False)
    deployment_count = Column(Integer, nullable=False, default=0)
    
    # Relationships using primaryjoin with foreign annotation for deferred resolution
    template = relationship(
        "WorkflowTemplate", 
        back_populates="versions",
        primaryjoin="foreign(TemplateVersion.template_id) == WorkflowTemplate.template_id"
    )
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('template_id', 'version', name='uq_template_version'),
        {'schema': 'public'}
    )

    def __repr__(self) -> str:
        return f"<TemplateVersion(id={self.version_id}, template={self.template_id}, version={self.version})>"

    def make_current(self) -> None:
        """Mark this version as the current version."""
        self.is_current = True

    def increment_deployment_count(self) -> None:
        """Increment the deployment counter for this version."""
        self.deployment_count += 1


class TemplateUsage(Base):
    """
    Template usage model for tracking template operations and analytics.
    
    Tracks how templates are used across tenants for analytics and audit purposes.
    """
    __tablename__ = "template_usage"

    # Primary identification
    usage_id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    template_id = Column(String, nullable=False)
    template_version = Column(String, nullable=True)
    tenant_id = Column(String, nullable=False)
    
    # Usage context
    workflow_id = Column(String, nullable=True)  # Which workflow used this template
    action = Column(String, nullable=False)  # DEPLOY, UPDATE, DELETE, CLONE
    
    # Usage metadata
    configuration_hash = Column(String, nullable=True)  # Hash of configuration used
    success = Column(Boolean, nullable=True)
    error_message = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships using primaryjoin with foreign annotation for deferred resolution
    template = relationship(
        "WorkflowTemplate", 
        back_populates="usage_records",
        primaryjoin="foreign(TemplateUsage.template_id) == WorkflowTemplate.template_id"
    )
    
    __table_args__ = (
        {'schema': 'public'}
    )

    def __repr__(self) -> str:
        return f"<TemplateUsage(id={self.usage_id}, action={self.action}, tenant={self.tenant_id})>"

    @classmethod
    def create_usage_record(
        cls,
        template_id: str,
        tenant_id: str,
        action: str,
        workflow_id: Optional[str] = None,
        template_version: Optional[str] = None,
        configuration_hash: Optional[str] = None,
        success: Optional[bool] = None,
        error_message: Optional[str] = None
    ) -> "TemplateUsage":
        """Create a new usage record."""
        return cls(
            template_id=template_id,
            template_version=template_version,
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            action=action,
            configuration_hash=configuration_hash,
            success=success,
            error_message=error_message
        )


class Workflow(Base):
    """
    Workflow model for storing running instances of templates.
    
    Workflows are deployed NiFi process groups based on templates with specific configurations.
    """
    __tablename__ = "workflows"

    # Primary identification
    workflow_id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(String, nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    tags = Column(ARRAY(Text), nullable=True)
    
    # Template reference
    template_id = Column(String, nullable=False)
    configuration = Column(JSONB, nullable=False)
    
    # Workflow state
    status = Column(String, nullable=False, default='ACTIVE')  # ACTIVE, PAUSED, ERROR, DELETED
    
    # NiFi deployment information
    nifi_process_group_id = Column(String, nullable=True)  # NiFi process group ID
    nifi_parameter_context_id = Column(String, nullable=True)  # NiFi parameter context ID
    deployment_method = Column(String, nullable=True)  # How it was deployed (registry/xml)
    flow_version = Column(Integer, nullable=True)  # Version of the flow deployed
    
    # Metadata
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    
    # Relationships using primaryjoin with foreign annotation for deferred resolution
    template = relationship(
        "WorkflowTemplate", 
        back_populates="workflows",
        primaryjoin="foreign(Workflow.template_id) == WorkflowTemplate.template_id"
    )
    
    __table_args__ = (
        {'schema': 'public'}
    )

    def __repr__(self) -> str:
        return f"<Workflow(id={self.workflow_id}, name={self.name}, tenant={self.tenant_id})>"

    @property
    def is_active(self) -> bool:
        """Check if workflow is currently active."""
        return self.status == 'ACTIVE'

    @property
    def is_deployed(self) -> bool:
        """Check if workflow is deployed to NiFi."""
        return self.nifi_process_group_id is not None

    def pause(self) -> None:
        """Pause the workflow."""
        self.status = 'PAUSED'

    def resume(self) -> None:
        """Resume the workflow."""
        self.status = 'ACTIVE'

    def mark_error(self) -> None:
        """Mark workflow as having an error."""
        self.status = 'ERROR'

    def mark_deleted(self) -> None:
        """Mark workflow as deleted."""
        self.status = 'DELETED'

    def update_nifi_deployment(
        self,
        process_group_id: str,
        parameter_context_id: Optional[str] = None,
        deployment_method: str = 'registry',
        flow_version: Optional[int] = None
    ) -> None:
        """Update NiFi deployment information."""
        self.nifi_process_group_id = process_group_id
        self.nifi_parameter_context_id = parameter_context_id
        self.deployment_method = deployment_method
        self.flow_version = flow_version


# Configure self-referencing relationship without foreign key constraint
# Database-level foreign key constraints are maintained by Alembic migrations
# SQLAlchemy relationships work without explicit ForeignKey() definitions when using primaryjoin
WorkflowTemplate.children = relationship(
    "WorkflowTemplate",
    backref=backref("parent", remote_side=[WorkflowTemplate.template_id]),
    primaryjoin="foreign(WorkflowTemplate.based_on) == WorkflowTemplate.template_id"
)


