"""Pydantic models for flow management API."""

from __future__ import annotations

import logging
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, validator

log = logging.getLogger(__name__)


class DeploymentStatus(str, Enum):
    """Flow deployment status."""
    NOT_DEPLOYED = "NOT_DEPLOYED"
    DEPLOYED = "DEPLOYED"
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


class FlowProcessor(BaseModel):
    """Flow processor definition."""
    id: str
    name: str
    type: str
    properties: Dict[str, Any] = Field(default_factory=dict)
    relationships: List[str] = Field(default_factory=list)


class FlowConnection(BaseModel):
    """Flow connection definition."""
    source: str
    destination: str
    relationships: List[str]
    
    
class FlowDefinition(BaseModel):
    """Complete flow definition."""
    name: str
    description: Optional[str] = None
    processors: List[FlowProcessor] = Field(default_factory=list)
    connections: List[FlowConnection] = Field(default_factory=list)
    parameters: Dict[str, Any] = Field(default_factory=dict)


class Flow(BaseModel):
    """Represents a versioned flow in NiFi Registry."""
    
    # Registry identifiers (persistent)
    bucket_id: str
    flow_id: str
    version: int = 1
    name: str
    description: Optional[str] = None
    created: Optional[datetime] = None
    modified: Optional[datetime] = None
    
    # Runtime deployment state (ephemeral)
    process_group_id: Optional[str] = None
    parameter_context_id: Optional[str] = None
    deployment_status: DeploymentStatus = DeploymentStatus.NOT_DEPLOYED


class FlowVersion(BaseModel):
    """Flow version information."""
    version: int
    created: datetime
    created_by: str
    comments: Optional[str] = None


class ValidationError(BaseModel):
    """Validation error details."""
    field: str
    message: str
    code: str


class APIErrorResponse(BaseModel):
    """Standardized API error response."""
    error_type: str
    user_message: str
    action_required: str
    validation_errors: Optional[List[ValidationError]] = None
    technical_details: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# Request Models
class CreateFlowRequest(BaseModel):
    """Request to create a new flow."""
    bucket_id: str
    flow_definition: FlowDefinition
    parameters: Dict[str, Any] = Field(default_factory=dict)


class UpdateFlowRequest(BaseModel):
    """Request to update an existing flow."""
    flow_definition: Optional[FlowDefinition] = None
    parameters: Optional[Dict[str, Any]] = None


class DeployFlowRequest(BaseModel):
    """Request to deploy a flow."""
    parameters: Dict[str, Any] = Field(default_factory=dict)
    version: Optional[int] = None


class UpdateParametersRequest(BaseModel):
    """Request to update flow parameters."""
    parameters: Dict[str, Any]


# Response Models
class FlowCreationResponse(BaseModel):
    """Response from flow creation."""
    success: bool
    flow_id: Optional[str] = None
    version: Optional[int] = None
    message: str
    error: Optional[APIErrorResponse] = None


class FlowDeploymentResponse(BaseModel):
    """Response from flow deployment."""
    success: bool
    process_group_id: Optional[str] = None
    parameter_context_id: Optional[str] = None
    message: str
    error: Optional[APIErrorResponse] = None


class FlowStatusResponse(BaseModel):
    """Flow status response."""
    flow_id: str
    bucket_id: str
    deployment_status: DeploymentStatus
    process_group_id: Optional[str] = None
    parameter_context_id: Optional[str] = None
    active_processors: int = 0
    stopped_processors: int = 0
    invalid_processors: int = 0


class FlowListResponse(BaseModel):
    """List of flows response."""
    flows: List[Flow]
    total: int


class BucketInfo(BaseModel):
    """Registry bucket information."""
    identifier: str
    name: str
    description: Optional[str] = None
    created: datetime


class BucketListResponse(BaseModel):
    """List of buckets response."""
    buckets: List[BucketInfo]
    total: int


# Result Models (for service layer)
class FlowCreationResult(BaseModel):
    """Internal result from flow creation."""
    success: bool
    flow_id: Optional[str] = None
    version: Optional[int] = None
    error: Optional[APIErrorResponse] = None


class FlowDeploymentResult(BaseModel):
    """Internal result from flow deployment."""
    success: bool
    process_group_id: Optional[str] = None
    parameter_context_id: Optional[str] = None
    error: Optional[APIErrorResponse] = None
    deployment_details: Optional[Dict[str, Any]] = None