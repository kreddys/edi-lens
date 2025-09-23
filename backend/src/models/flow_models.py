"""Pydantic models for improved flow management API."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class FlowDefinition(BaseModel):
    """Flow definition model."""
    name: str = Field(..., description="Flow name")
    description: str = Field("", description="Flow description")
    processors: List[Dict[str, Any]] = Field(default_factory=list, description="List of processors")
    connections: List[Dict[str, Any]] = Field(default_factory=list, description="List of connections")
    process_groups: List[Dict[str, Any]] = Field(default_factory=list, description="List of nested process groups")


class DeployAndStoreFlowRequest(BaseModel):
    """Request model for deploy-and-store operation."""
    bucket_id: str = Field(..., description="Registry bucket ID")
    flow_definition: FlowDefinition = Field(..., description="Flow definition")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Flow parameters")
    parent_group_id: str = Field("root", description="Parent process group ID")
    flow_name: Optional[str] = Field(None, description="Override flow name")
    flow_description: str = Field("", description="Flow description for Registry")


class DeploymentSummary(BaseModel):
    """Summary of deployment results."""
    total_processors: int = Field(0, description="Total processors in definition")
    created_processors: int = Field(0, description="Successfully created processors")
    failed_processors: int = Field(0, description="Failed processor creations")
    total_connections: int = Field(0, description="Total connections in definition")
    created_connections: int = Field(0, description="Successfully created connections")
    failed_connections: int = Field(0, description="Failed connection creations")


class DeployAndStoreFlowResponse(BaseModel):
    """Response model for deploy-and-store operation."""
    success: bool = Field(..., description="Whether operation succeeded")
    stage: str = Field(..., description="Stage where operation completed/failed")
    flow_id: Optional[str] = Field(None, description="Registry flow ID")
    version: Optional[int] = Field(None, description="Registry flow version")
    process_group_id: Optional[str] = Field(None, description="NiFi process group ID")
    parameter_context_id: Optional[str] = Field(None, description="NiFi parameter context ID")
    message: str = Field(..., description="Operation result message")
    deployment_summary: Optional[DeploymentSummary] = Field(None, description="Deployment summary")


class UpdateDeployedFlowRequest(BaseModel):
    """Request model for updating deployed flows."""
    flow_definition: Optional[FlowDefinition] = Field(None, description="Updated flow definition")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Updated parameters")
    commit_changes: bool = Field(True, description="Whether to commit changes to Registry")
    comments: str = Field("Updated flow", description="Commit comments")


class FlowStatusResponse(BaseModel):
    """Response model for flow status."""
    process_group_id: str = Field(..., description="Process group ID")
    status: str = Field(..., description="Overall flow status")
    processor_count: int = Field(0, description="Total number of processors")
    running_count: int = Field(0, description="Number of running processors")
    stopped_count: int = Field(0, description="Number of stopped processors")
    invalid_count: int = Field(0, description="Number of invalid processors")
    version_control: Optional[Dict[str, Any]] = Field(None, description="Version control information")


class VersionControlOperationResponse(BaseModel):
    """Response model for version control operations."""
    success: bool = Field(..., description="Whether operation succeeded")
    process_group_id: str = Field(..., description="Process group ID")
    message: str = Field(..., description="Operation result message")
    committed: bool = Field(False, description="Whether changes were committed")


class ErrorDetail(BaseModel):
    """Error detail model."""
    error_type: str = Field(..., description="Error type")
    user_message: str = Field(..., description="User-friendly error message")
    action_required: str = Field(..., description="Suggested action")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")


class ComponentFailure(BaseModel):
    """Component failure model."""
    component_type: str = Field(..., description="Type of component (processor, connection, etc.)")
    component_name: str = Field(..., description="Name of the component")
    error_type: str = Field(..., description="Type of error")
    message: str = Field(..., description="Error message")
    details: Dict[str, Any] = Field(default_factory=dict, description="Additional error details")


class ValidationResult(BaseModel):
    """Validation result model."""
    success: bool = Field(..., description="Whether validation passed")
    summary: DeploymentSummary = Field(..., description="Validation summary")
    failures: List[ComponentFailure] = Field(default_factory=list, description="Validation failures")
    process_group_id: Optional[str] = Field(None, description="Process group ID if created")
    parameter_context_id: Optional[str] = Field(None, description="Parameter context ID if created")


class FlowParameter(BaseModel):
    """Flow parameter model."""
    name: str = Field(..., description="Parameter name")
    value: str = Field(..., description="Parameter value")
    description: str = Field("", description="Parameter description")
    sensitive: bool = Field(False, description="Whether parameter is sensitive")


class ParameterContextInfo(BaseModel):
    """Parameter context information."""
    context_id: str = Field(..., description="Parameter context ID")
    name: str = Field(..., description="Parameter context name")
    description: str = Field("", description="Parameter context description")
    parameters: List[FlowParameter] = Field(default_factory=list, description="Context parameters")


class VersionControlInfo(BaseModel):
    """Version control information."""
    registry_id: str = Field(..., description="Registry client ID")
    bucket_id: str = Field(..., description="Registry bucket ID")
    flow_id: str = Field(..., description="Registry flow ID")
    version: int = Field(..., description="Current version")
    flow_name: str = Field(..., description="Flow name in Registry")
    has_local_changes: bool = Field(False, description="Whether there are uncommitted local changes")
    latest_version: Optional[int] = Field(None, description="Latest version available in Registry")


class ProcessorInfo(BaseModel):
    """Processor information."""
    processor_id: str = Field(..., description="Processor ID")
    name: str = Field(..., description="Processor name")
    type: str = Field(..., description="Processor type")
    state: str = Field(..., description="Processor state")
    validation_status: str = Field(..., description="Validation status")
    validation_errors: List[str] = Field(default_factory=list, description="Validation errors")


class ConnectionInfo(BaseModel):
    """Connection information."""
    connection_id: str = Field(..., description="Connection ID")
    name: str = Field(..., description="Connection name")
    source_name: str = Field(..., description="Source processor name")
    destination_name: str = Field(..., description="Destination processor name")
    queued_count: int = Field(0, description="Number of queued FlowFiles")
    queued_size: str = Field("0 bytes", description="Size of queued data")


class DetailedFlowStatus(BaseModel):
    """Detailed flow status model."""
    process_group_id: str = Field(..., description="Process group ID")
    name: str = Field(..., description="Flow name")
    status: str = Field(..., description="Overall flow status")
    processors: List[ProcessorInfo] = Field(default_factory=list, description="Processor details")
    connections: List[ConnectionInfo] = Field(default_factory=list, description="Connection details")
    parameter_context: Optional[ParameterContextInfo] = Field(None, description="Parameter context info")
    version_control: Optional[VersionControlInfo] = Field(None, description="Version control info")
    last_modified: Optional[str] = Field(None, description="Last modification timestamp")


class BulkOperationRequest(BaseModel):
    """Request model for bulk operations."""
    process_group_ids: List[str] = Field(..., description="List of process group IDs")
    operation: str = Field(..., description="Operation to perform (start, stop, delete)")
    options: Dict[str, Any] = Field(default_factory=dict, description="Operation options")


class BulkOperationResponse(BaseModel):
    """Response model for bulk operations."""
    success: bool = Field(..., description="Whether all operations succeeded")
    results: Dict[str, Dict[str, Any]] = Field(..., description="Results per process group ID")
    summary: Dict[str, int] = Field(..., description="Summary of successes/failures")