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


# NiFi Standard Models - following NiFi Registry API spec

class Position(BaseModel):
    """Position coordinates."""
    x: float
    y: float


class Bundle(BaseModel):
    """Component bundle information."""
    group: str
    artifact: str
    version: str


class ConnectableComponent(BaseModel):
    """Connectable component reference."""
    id: str
    type: str  # PROCESSOR, FUNNEL, INPUT_PORT, OUTPUT_PORT, etc.


class VersionedConnection(BaseModel):
    """NiFi versioned connection."""
    identifier: str
    name: str = ""
    source: ConnectableComponent
    destination: ConnectableComponent
    selectedRelationships: List[str]
    flowFileExpiration: str = "0 sec"
    backPressureDataSizeThreshold: str = "1 GB"
    backPressureObjectThreshold: int = 10000
    bends: List[Position] = Field(default_factory=list)
    prioritizers: List[str] = Field(default_factory=list)


class VersionedProcessor(BaseModel):
    """NiFi versioned processor."""
    identifier: str
    name: str
    type: str
    bundle: Bundle
    position: Position
    properties: Dict[str, str] = Field(default_factory=dict)
    schedulingPeriod: str = "0 sec"
    schedulingStrategy: str = "EVENT_DRIVEN"  # TIMER_DRIVEN, EVENT_DRIVEN, CRON_DRIVEN
    executionNode: str = "ALL"  # ALL, PRIMARY
    penaltyDuration: str = "30 sec"
    yieldDuration: str = "1 sec"
    bulletinLevel: str = "WARN"
    runDurationMillis: int = 0
    concurrentlySchedulableTaskCount: int = 1
    autoTerminatedRelationships: List[str] = Field(default_factory=list)


class VersionedProcessGroup(BaseModel):
    """NiFi versioned process group - this is the main flow definition."""
    identifier: str
    name: str
    comments: Optional[str] = None
    position: Position
    processGroups: List['VersionedProcessGroup'] = Field(default_factory=list)
    remoteProcessGroups: List[Dict[str, Any]] = Field(default_factory=list)
    processors: List[VersionedProcessor] = Field(default_factory=list)
    inputPorts: List[Dict[str, Any]] = Field(default_factory=list)
    outputPorts: List[Dict[str, Any]] = Field(default_factory=list)
    connections: List[VersionedConnection] = Field(default_factory=list)
    labels: List[Dict[str, Any]] = Field(default_factory=list)
    funnels: List[Dict[str, Any]] = Field(default_factory=list)
    controllerServices: List[Dict[str, Any]] = Field(default_factory=list)
    variables: Dict[str, str] = Field(default_factory=dict)
    parameterContextName: Optional[str] = None
    defaultFlowFileExpiration: str = "0 sec"
    defaultBackPressureObjectThreshold: int = 10000
    defaultBackPressureDataSizeThreshold: str = "1 GB"
    flowFileConcurrency: str = "UNBOUNDED"  # UNBOUNDED, SINGLE_FLOWFILE_PER_NODE
    flowFileOutboundPolicy: str = "STREAM_WHEN_AVAILABLE"  # STREAM_WHEN_AVAILABLE, BATCH_OUTPUT
    scheduledState: str = "DISABLED"  # ENABLED, DISABLED, RUNNING

# Update model references
VersionedProcessGroup.model_rebuild()


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
    flow_definition: VersionedProcessGroup
    parameters: Dict[str, Any] = Field(default_factory=dict)


class UpdateFlowRequest(BaseModel):
    """Request to update an existing flow."""
    flow_definition: Optional[VersionedProcessGroup] = None
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
    createdTimestamp: int
    
    @property
    def created(self) -> datetime:
        """Convert timestamp to datetime."""
        return datetime.fromtimestamp(self.createdTimestamp / 1000)


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