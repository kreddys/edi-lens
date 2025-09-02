"""
Workflow models for NiFi workflow management.

This module contains models for deployed workflows that reference
Registry templates, along with their configuration and runtime status.
"""

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint, Column, DateTime, 
    Integer, String, Text
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import relationship, foreign
from sqlalchemy.sql import func

from src.core.database import Base


class Workflow(Base):
    """
    Deployed workflow based on a Registry template.
    
    This model tracks deployed NiFi process groups that were created
    from Registry templates, along with their configuration and status.
    """
    __tablename__ = "workflows"
    
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
        back_populates="workflows",
        primaryjoin="foreign(Workflow.template_id) == RegistryTemplate.template_id"
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
        return f"<Workflow(id={self.workflow_id}, name={self.name}, tenant={self.tenant_id})>"

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
        self.deployed_at = datetime.now(timezone.utc)

    def mark_running(self) -> None:
        """Mark workflow as running."""
        self.status = 'RUNNING'
        self.last_started_at = datetime.now(timezone.utc)

    def mark_stopped(self) -> None:
        """Mark workflow as stopped."""
        self.status = 'STOPPED'
        self.last_stopped_at = datetime.now(timezone.utc)

    def mark_error(self) -> None:
        """Mark workflow as having an error."""
        self.status = 'ERROR'

    def mark_deleted(self) -> None:
        """Mark workflow as deleted."""
        self.status = 'DELETED'

    def update_version_control_info(self, version_info: dict) -> None:
        """Update version control information from NiFi."""
        self.version_control_info = version_info