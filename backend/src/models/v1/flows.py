"""RESTful API models for flows."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from datetime import datetime

from pydantic import BaseModel, Field


class FlowStatus(str, Enum):
    """Flow execution status."""
    RUNNING = "running"
    STOPPED = "stopped"
    INVALID = "invalid" 
    UNKNOWN = "unknown"


class DeploymentStatus(str, Enum):
    """Flow deployment status."""
    DEPLOYED = "deployed"
    UNDEPLOYED = "undeployed"
    DEPLOYING = "deploying"
    FAILED = "failed"


class FlowDefinition(BaseModel):
    """Flow definition structure."""
    name: str = Field(..., description="Flow name")
    description: str = Field("", description="Flow description")
    processors: List[Dict[str, Any]] = Field(default_factory=list, description="List of processors")
    connections: List[Dict[str, Any]] = Field(default_factory=list, description="List of connections")
    process_groups: List[Dict[str, Any]] = Field(default_factory=list, description="List of nested process groups")


class FlowBase(BaseModel):
    """Base flow model."""
    name: str = Field(..., description="Flow name")
    description: str = Field("", description="Flow description")
    definition: Optional[FlowDefinition] = Field(None, description="Flow definition")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Flow parameters")


class FlowCreate(FlowBase):
    """Model for creating a new flow."""
    bucket_id: Optional[str] = Field(None, description="Registry bucket ID for versioning")
    parent_group_id: str = Field("root", description="Parent process group ID")


class FlowUpdate(BaseModel):
    """Model for updating an existing flow."""
    name: Optional[str] = Field(None, description="Flow name")
    description: Optional[str] = Field(None, description="Flow description")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Flow parameters")


class FlowResponse(FlowBase):
    """Model for flow response."""
    id: str = Field(..., description="Flow ID (process group ID)")
    status: FlowStatus = Field(..., description="Flow execution status")
    deployment_status: DeploymentStatus = Field(..., description="Flow deployment status")
    processor_count: int = Field(0, description="Total number of processors")
    running_count: int = Field(0, description="Number of running processors")
    stopped_count: int = Field(0, description="Number of stopped processors") 
    invalid_count: int = Field(0, description="Number of invalid processors")
    created_at: Optional[str] = Field(None, description="Creation timestamp")
    updated_at: Optional[str] = Field(None, description="Last update timestamp")
    version_control: Optional[Dict[str, Any]] = Field(None, description="Version control information")


class FlowListResponse(BaseModel):
    """Model for flow list response."""
    flows: List[FlowResponse] = Field(..., description="List of flows")
    total: int = Field(..., description="Total number of flows")
    page: int = Field(1, description="Current page")
    size: int = Field(50, description="Page size")


class ExecutionRequest(BaseModel):
    """Model for flow execution requests."""
    process_group_id: str = Field(..., description="Process group ID to control")
    action: str = Field(..., description="Action to perform (start/stop)")
    force: bool = Field(False, description="Force the action even if components are invalid")


class ExecutionResponse(BaseModel):
    """Model for flow execution response."""
    success: bool = Field(..., description="Whether the action succeeded")
    message: str = Field(..., description="Result message")
    status: FlowStatus = Field(..., description="Flow execution status")
    details: Dict[str, Any] = Field(default_factory=dict, description="Additional execution details")


class DeploymentRequest(BaseModel):
    """Model for flow deployment requests."""
    bucket_id: Optional[str] = Field(None, description="Registry bucket ID for version control")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Deployment parameters")
    auto_start: bool = Field(False, description="Whether to start the flow after deployment")


class DeploymentResponse(BaseModel):
    """Model for flow deployment response."""
    success: bool = Field(..., description="Whether deployment succeeded")
    deployment_id: str = Field(..., description="Deployment ID")
    status: DeploymentStatus = Field(..., description="Deployment status")
    message: str = Field(..., description="Deployment message")
    flow_id: Optional[str] = Field(None, description="Registry flow ID if versioned")
    version: Optional[int] = Field(None, description="Registry version if versioned")
    summary: Optional[Dict[str, Any]] = Field(None, description="Deployment summary")


class VersionRequest(BaseModel):
    """Model for version control requests."""
    action: str = Field(..., description="Version action (commit/sync/revert)")
    message: str = Field("", description="Commit message")
    force: bool = Field(False, description="Force the action")


class VersionResponse(BaseModel):
    """Model for version control response."""
    success: bool = Field(..., description="Whether the action succeeded")
    message: str = Field(..., description="Result message")
    version: Optional[int] = Field(None, description="Current version after operation")
    previous_version: Optional[int] = Field(None, description="Previous version before operation")
    timestamp: Optional[int] = Field(None, description="Operation timestamp (milliseconds)")
    modifications: Optional[Dict[str, Any]] = Field(None, description="Modification details")


class FlowVersion(BaseModel):
    """Model for flow version information."""
    version: int = Field(..., description="Version number")
    created_at: str = Field(..., description="Version creation timestamp")
    author: Optional[str] = Field(None, description="Version author")
    comments: str = Field("", description="Version comments")
    is_current: bool = Field(False, description="Whether this is the current version")