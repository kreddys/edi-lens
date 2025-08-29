# FILE: backend/src/api/schemas.py

from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional, Literal



# --- REMOVED: Unused imports from the now-deleted criteria model ---


# ... (ValidationFinding and related models are unchanged) ...
class FindingLocation(BaseModel):
    """Specifies the exact location of a validation finding within the EDI document."""
    loop_id: Optional[str] = None
    segment_id: str
    segment_instance: int # 1-based index of the segment within its loop
    element_position: int
    line_number: int
    value: Optional[str] = None

class ValidationFinding(BaseModel):
    """Represents a single validation issue found in the EDI document."""
    level: str # 'error', 'warning', 'info'
    code: str  # A unique code for the rule that was violated
    message: str
    location: FindingLocation

# --- Schemas for Creating Data ---

# --- REMOVED: ProfileCriterionCreate is no longer needed ---

# --- SFTP Webhook Schemas ---

class SftpUploadWebhook(BaseModel):
    """Schema for SFTPGo upload webhook data."""
    
    # Core file information
    name: str = Field(..., description="Name of the uploaded file")
    size: int = Field(..., description="File size in bytes")
    
    # User and path information
    username: str = Field(..., description="SFTP username who uploaded the file")
    path: str = Field(..., description="Full path where file was uploaded")
    
    # Upload metadata
    timestamp: Optional[str] = Field(None, description="Upload timestamp")
    action: str = Field(default="upload", description="Type of action (upload, pre-upload)")
    
    # S3/Storage information
    fs_provider: Optional[int] = Field(None, description="Filesystem provider (1=S3)")
    bucket: Optional[str] = Field(None, description="S3 bucket name") 
    object_name: Optional[str] = Field(None, description="S3 object key/path")
    
    class Config:
        # Allow extra fields in case SFTPGo sends additional data
        extra = "allow"

class PartnerProfileCreate(BaseModel):
    name: str
    priority: int = 10
    validation_schema_name: Optional[str] = None
    # --- ADDED: The new field for SFTP filename matching ---
    file_name_patterns: Optional[str] = Field(None, description='JSON array of filename patterns, e.g., \'["claims_*.edi"]\'')
    # Enhanced validation configuration
    snip_level: str = "SNIP3"
    generate_ta1: bool = True
    generate_999: bool = False
    custom_validation_rules: Optional[dict] = None
    # --- REMOVED: The old criteria field ---
    # criteria: List[ProfileCriterionCreate]

class TradingPartnerCreate(BaseModel):
    name: str
    description: Optional[str] = None
    profiles: List[PartnerProfileCreate]
    # --- SIMPLIFIED SFTP CONFIG ---
    sftp_enabled: bool = False
    sftp_username: Optional[str] = None

# --- Schemas for Updating Data ---

# --- REMOVED: ProfileCriterionUpdate is no longer needed ---

class PartnerProfileUpdate(PartnerProfileCreate):
    id: Optional[int] = None
    # --- REMOVED: The old criteria field ---
    # criteria: List[ProfileCriterionUpdate]

class TradingPartnerUpdate(BaseModel):
    name: str
    description: Optional[str] = None
    profiles: List[PartnerProfileUpdate]
    # --- SIMPLIFIED SFTP CONFIG ---
    sftp_enabled: bool = False
    sftp_username: Optional[str] = None

# --- Schemas for Reading Data (Response Models) ---

# --- REMOVED: ProfileCriterion response model is no longer needed ---

class PartnerProfile(PartnerProfileCreate):
    id: int
    partner_id: int
    tenant_id: str
    model_config = ConfigDict(from_attributes=True)

class TradingPartner(TradingPartnerCreate):
    id: int
    tenant_id: str
    profiles: List[PartnerProfile]
    model_config = ConfigDict(from_attributes=True)

# --- EDI & Validation Schemas ---
# ... (EdiElement and EdiSegment are unchanged) ...
class EdiElement(BaseModel):
    value: str

class EdiSegment(BaseModel):
    id: str
    elements: List[EdiElement]
    line_number: int

class ValidationRequest(BaseModel):
    edi_data: str
    #file_name: Optional[str] = None
    # --- CHANGED: profile_name is now REQUIRED for all API validations ---
    profile_name: str = Field(..., description="The name of the validation profile to use.")

# ... (ValidationResponse and all Enrichment models are unchanged) ...
class ValidationResponse(BaseModel):
    valid: bool
    status: str
    findings: List[ValidationFinding] = []
    errors: List[ValidationFinding] = []
    ta1_content: Optional[str] = None
    ta1_999_content: Optional[str] = None
    processing_time_ms: Optional[int] = None
    matched_profile: Optional[str] = None
    schema_used: Optional[str] = None
    snip_level_used: Optional[str] = None
    detection_method: Optional[str] = None
    ta1_acknowledgement: Optional[str] = None
    ack999_acknowledgement: Optional[str] = None



class MessageResponse(BaseModel):
    message: str

# ==============================================================================
# EDI Processing Schemas (NiFi Integration)
# ==============================================================================

from datetime import datetime

class RealtimeEDIValidationRequest(BaseModel):
    """Request schema for real-time EDI validation (synchronous processing)."""
    edi_content: str = Field(..., description="EDI document content to validate")
    tenant_id: str = Field(..., description="Tenant identifier for isolation")
    workflow_id: str = Field(..., description="Workflow identifier")
    validation_schema: str = Field(..., description="EDI schema to validate against")
    snip_level: int = Field(default=3, description="SNIP validation level (1-5)")

class RealtimeEDIValidationResponse(BaseModel):
    """Response schema for real-time EDI validation."""
    valid: bool = Field(..., description="Whether the EDI document is valid")
    validation_results: List[ValidationFinding] = Field(default=[], description="Validation findings")
    processing_time_ms: int = Field(..., description="Processing time in milliseconds")
    schema_used: str = Field(..., description="Schema used for validation")
    snip_level_used: int = Field(..., description="SNIP level used for validation")
    ta1_content: Optional[str] = Field(None, description="Generated TA1 acknowledgment content")
    workflow_id: str = Field(..., description="Workflow identifier")
    processed_at: datetime = Field(..., description="Processing timestamp")

class BatchEDIValidationRequest(BaseModel):
    """Request schema for batch EDI validation (asynchronous processing)."""
    edi_content: str = Field(..., description="EDI document content to validate (ONE file only)")
    tenant_id: str = Field(..., description="Tenant identifier for isolation")
    workflow_id: str = Field(..., description="Workflow identifier")
    validation_schema: str = Field(..., description="EDI schema to validate against")
    snip_level: int = Field(default=3, description="SNIP validation level (1-5)")
    file_name: Optional[str] = Field(None, description="Original file name")
    callback_url: str = Field(..., description="Webhook endpoint for completion notification")
    generate_ta1: bool = Field(default=False, description="Generate TA1 acknowledgment")
    generate_999: bool = Field(default=False, description="Generate 999 acknowledgment")

class BatchEDIValidationResponse(BaseModel):
    """Response schema for batch EDI validation (job creation)."""
    job_id: str = Field(..., description="Job tracking ID")
    status: str = Field(..., description="Job status: QUEUED, PROCESSING, COMPLETED, FAILED")
    workflow_id: str = Field(..., description="Workflow identifier")
    file_name: Optional[str] = Field(None, description="Original file name")
    estimated_processing_time_ms: int = Field(..., description="Estimated processing time")
    created_at: datetime = Field(..., description="Job creation timestamp")

class BatchJobStatusResponse(BaseModel):
    """Response schema for batch job status queries."""
    job_id: str = Field(..., description="Job tracking ID")
    workflow_id: str = Field(..., description="Workflow identifier")
    tenant_id: str = Field(..., description="Tenant identifier")
    status: str = Field(..., description="Job status: QUEUED, PROCESSING, COMPLETED, FAILED")
    file_name: Optional[str] = Field(None, description="Original file name")
    validation_schema: str = Field(..., description="Schema used for validation")
    created_at: datetime = Field(..., description="Job creation timestamp")
    started_at: Optional[datetime] = Field(None, description="Processing start timestamp")
    completed_at: Optional[datetime] = Field(None, description="Processing completion timestamp")
    processing_time_ms: Optional[int] = Field(None, description="Total processing time")
    results: Optional['RealtimeEDIValidationResponse'] = Field(None, description="Validation results if completed")
    callback_sent: bool = Field(default=False, description="Whether webhook callback was sent")
    callback_sent_at: Optional[datetime] = Field(None, description="Webhook callback timestamp")
    errors: List[str] = Field(default=[], description="Any processing errors")

class BatchJobCompletionWebhook(BaseModel):
    """Webhook payload structure for batch job completion."""
    job_id: str = Field(..., description="Job tracking ID")
    status: str = Field(..., description="Final job status: COMPLETED or FAILED")
    workflow_id: str = Field(..., description="Workflow identifier")
    file_name: Optional[str] = Field(None, description="Original file name")
    results: Optional['RealtimeEDIValidationResponse'] = Field(None, description="Validation results if successful")
    error_message: Optional[str] = Field(None, description="Error message if failed")

class TA1GenerationRequest(BaseModel):
    """Request schema for TA1 acknowledgment generation."""
    edi_content: str = Field(..., description="Original EDI document content containing ISA header")
    tenant_id: str = Field(..., description="Tenant identifier")
    workflow_id: str = Field(..., description="NiFi workflow identifier")
    acknowledgment_code: str = Field(
        ..., 
        pattern="^[ARE]$", 
        description="A=Accept, R=Reject, E=Error"
    )
    error_code: Optional[str] = Field(
        None, 
        description="IK901 error code (required if acknowledgment_code=E)"
    )
    error_note: Optional[str] = Field(
        None, 
        description="Human-readable error description"
    )
    file_name: Optional[str] = Field(None, description="Original file name")

class TA1GenerationResponse(BaseModel):
    """Response schema for TA1 acknowledgment generation."""
    ta1_content: str = Field(..., description="Generated TA1 acknowledgment content")
    control_number: str = Field(..., description="TA1 control number")
    acknowledgment_code: str = Field(..., description="Acknowledgment code used")
    workflow_id: str = Field(..., description="Original workflow identifier")
    generated_at: datetime = Field(..., description="Generation timestamp")
    processing_time_ms: int = Field(..., description="Processing time in milliseconds")

class SchemaValidationRequest(BaseModel):
    """Request schema for schema validation."""
    schema_name: str = Field(..., description="The name of the schema to validate")
    tenant_id: str = Field(..., description="Tenant identifier for isolation")

class SchemaValidationResponse(BaseModel):
    """Response schema for schema validation."""
    is_valid: bool = Field(..., description="Whether the schema is valid")

class EdiParsingRequest(BaseModel):
    """Request schema for EDI parsing."""
    edi_content: str = Field(..., description="EDI document content to parse")
    tenant_id: str = Field(..., description="Tenant identifier for isolation")
    schema_name: str = Field(..., description="EDI schema to use for parsing")

class Ack999GenerationRequest(BaseModel):
    """Request schema for 999 functional acknowledgment generation."""
    edi_content: str = Field(..., description="Original EDI document content")
    tenant_id: str = Field(..., description="Tenant identifier")
    workflow_id: str = Field(..., description="Workflow identifier")
    validation_errors: List[ValidationFinding] = Field(default=[], description="Validation findings")
    file_name: Optional[str] = Field(None, description="Original file name")

class Ack999GenerationResponse(BaseModel):
    """Response schema for 999 functional acknowledgment generation."""
    ack999_content: Optional[str] = Field(None, description="Generated 999 acknowledgment content")
    acknowledgment_status: str = Field(..., description="Acknowledgment status: A (Accept), E (Error), R (Reject)")
    error_code: Optional[str] = Field(None, description="Error code if rejection")
    processing_time_ms: int = Field(..., description="Processing time in milliseconds")


# ==============================================================================
# Workflow Template Management Schemas
# ==============================================================================

from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID as PyUUID


class TemplateScope(str, Enum):
    """Template scope enumeration."""
    GLOBAL = "GLOBAL"
    TENANT = "TENANT"


class TemplateCategory(str, Enum):
    """Template category enumeration."""
    BATCH = "BATCH"
    REALTIME = "REALTIME"
    TRANSFORMATION = "TRANSFORMATION"
    INTEGRATION = "INTEGRATION"


class TemplateStatus(str, Enum):
    """Template status enumeration."""
    ACTIVE = "ACTIVE"
    DEPRECATED = "DEPRECATED"
    ARCHIVED = "ARCHIVED"


class WorkflowStatus(str, Enum):
    """Workflow status enumeration."""
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    ERROR = "ERROR"
    DELETED = "DELETED"
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    FAILED = "FAILED"
    PENDING = "PENDING"
    UNKNOWN = "UNKNOWN"


class DeploymentMethod(str, Enum):
    """Deployment method enumeration."""
    REGISTRY = "registry"
    XML = "xml"


class TemplateAction(str, Enum):
    """Template usage action enumeration."""
    DEPLOY = "DEPLOY"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    CLONE = "CLONE"


# Base schemas for common fields
class TemplateBase(BaseModel):
    """Base template schema with common fields."""
    name: str = Field(..., description="Template name")
    description: Optional[str] = Field(None, description="Template description")
    category: TemplateCategory = Field(..., description="Template category")
    tags: Optional[List[str]] = Field(None, description="Template tags")
    features: Optional[List[str]] = Field(None, description="Template features")
    documentation: Optional[str] = Field(None, description="Usage documentation")
    examples: Optional[Dict[str, Any]] = Field(None, description="Example configurations")


class TemplateCreate(TemplateBase):
    """Schema for creating a new template."""
    template_id: Optional[str] = Field(None, description="Template ID (auto-generated if not provided)")
    scope: TemplateScope = Field(TemplateScope.TENANT, description="Template scope")
    tenant_id: Optional[str] = Field(None, description="Tenant ID (required for tenant templates)")
    based_on: Optional[str] = Field(None, description="Parent template ID")
    version: str = Field("1.0", description="Template version")
    flow_definition: Dict[str, Any] = Field(..., description="NiFi flow definition")
    configuration_schema: Dict[str, Any] = Field(..., description="Configuration schema")
    deployment_method: DeploymentMethod = Field(DeploymentMethod.REGISTRY, description="Deployment method")
    is_featured: bool = Field(False, description="Whether template is featured")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Custom Claims Processor",
                "description": "Specialized 837P claims processing workflow",
                "category": "BATCH",
                "scope": "TENANT",
                "tenant_id": "tenant-a",
                "based_on": "global-sftp-edi-processor-v1.0",
                "tags": ["healthcare", "claims", "837p"],
                "features": ["validation", "acknowledgments", "archival"],
                "flow_definition": {
                    "processors": [],
                    "connections": [],
                    "parameter_contexts": []
                },
                "configuration_schema": {
                    "type": "object",
                    "properties": {
                        "input_path": {"type": "string"}
                    }
                }
            }
        }
    )


class TemplateUpdate(BaseModel):
    """Schema for updating an existing template."""
    name: Optional[str] = Field(None, description="Template name")
    description: Optional[str] = Field(None, description="Template description")
    tags: Optional[List[str]] = Field(None, description="Template tags")
    features: Optional[List[str]] = Field(None, description="Template features")
    documentation: Optional[str] = Field(None, description="Usage documentation")
    examples: Optional[Dict[str, Any]] = Field(None, description="Example configurations")
    flow_definition: Optional[Dict[str, Any]] = Field(None, description="NiFi flow definition")
    configuration_schema: Optional[Dict[str, Any]] = Field(None, description="Configuration schema")
    status: Optional[TemplateStatus] = Field(None, description="Template status")
    is_featured: Optional[bool] = Field(None, description="Whether template is featured")


class TemplateClone(BaseModel):
    """Schema for cloning a template."""
    source_template_id: str = Field(..., description="Source template ID to clone")
    new_template: TemplateCreate = Field(..., description="New template configuration")
    customizations: Optional[Dict[str, Any]] = Field(None, description="Template customizations")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "source_template_id": "global-sftp-edi-processor-v1.0",
                "new_template": {
                    "name": "Custom Claims Processor",
                    "description": "Specialized for our healthcare claims workflow",
                    "category": "BATCH",
                    "scope": "TENANT",
                    "tenant_id": "tenant-a"
                },
                "customizations": {
                    "add_processors": [],
                    "modify_configuration_schema": {},
                    "add_validation_rules": []
                }
            }
        }
    )


class TemplateResponse(TemplateBase):
    """Schema for template response."""
    template_id: str = Field(..., description="Template ID")
    scope: TemplateScope = Field(..., description="Template scope")
    tenant_id: Optional[str] = Field(None, description="Tenant ID")
    maintainer: Optional[str] = Field(None, description="Template maintainer")
    based_on: Optional[str] = Field(None, description="Parent template ID")
    version: str = Field(..., description="Template version")
    flow_definition: Dict[str, Any] = Field(..., description="NiFi flow definition")
    configuration_schema: Dict[str, Any] = Field(..., description="Configuration schema")
    deployment_method: DeploymentMethod = Field(..., description="Deployment method")
    nifi_registry_flow_id: Optional[str] = Field(None, description="NiFi Registry flow ID")
    nifi_registry_bucket_id: Optional[str] = Field(None, description="NiFi Registry bucket ID")
    status: TemplateStatus = Field(..., description="Template status")
    is_featured: bool = Field(..., description="Whether template is featured")
    usage_count: int = Field(..., description="Template usage count")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    deprecated_at: Optional[datetime] = Field(None, description="Deprecation timestamp")

    model_config = ConfigDict(from_attributes=True)


class TemplateListResponse(BaseModel):
    """Schema for template list response."""
    templates: List[TemplateResponse] = Field(..., description="List of templates")
    total: int = Field(..., description="Total number of templates")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Page size")


class TemplateVersionCreate(BaseModel):
    """Schema for creating a new template version."""
    version: str = Field(..., description="Version identifier")
    changes: Optional[str] = Field(None, description="Description of changes")
    flow_definition: Dict[str, Any] = Field(..., description="NiFi flow definition")
    configuration_schema: Dict[str, Any] = Field(..., description="Configuration schema")


class TemplateVersionResponse(BaseModel):
    """Schema for template version response."""
    version_id: PyUUID = Field(..., description="Version ID")
    template_id: str = Field(..., description="Template ID")
    version: str = Field(..., description="Version identifier")
    flow_definition: Dict[str, Any] = Field(..., description="NiFi flow definition")
    configuration_schema: Dict[str, Any] = Field(..., description="Configuration schema")
    changes: Optional[str] = Field(None, description="Description of changes")
    created_by: str = Field(..., description="Creator user ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    is_current: bool = Field(..., description="Whether this is the current version")
    deployment_count: int = Field(..., description="Number of deployments")

    model_config = ConfigDict(from_attributes=True)


class TemplateUsageResponse(BaseModel):
    """Schema for template usage response."""
    usage_id: PyUUID = Field(..., description="Usage ID")
    template_id: str = Field(..., description="Template ID")
    template_version: Optional[str] = Field(None, description="Template version")
    tenant_id: str = Field(..., description="Tenant ID")
    workflow_id: Optional[str] = Field(None, description="Workflow ID")
    action: TemplateAction = Field(..., description="Action performed")
    configuration_hash: Optional[str] = Field(None, description="Configuration hash")
    success: Optional[bool] = Field(None, description="Whether action succeeded")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    created_at: datetime = Field(..., description="Creation timestamp")

    model_config = ConfigDict(from_attributes=True)


class WorkflowCreate(BaseModel):
    """Schema for creating a new workflow."""
    name: str = Field(..., description="Workflow name")
    description: Optional[str] = Field(None, description="Workflow description")
    tags: Optional[List[str]] = Field(None, description="Workflow tags")
    template_id: str = Field(..., description="Template ID")
    configuration: Dict[str, Any] = Field(..., description="Workflow configuration")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Production Claims Processing",
                "description": "Production workflow for processing healthcare claims",
                "tags": ["production", "claims"],
                "template_id": "tenant-a-custom-claims-v1.0",
                "configuration": {
                    "input_path": "/sftp/tenants/tenant-a/claims/in/",
                    "validation": {
                        "schema": "837.5010.X222.A1.json",
                        "snip_level": 3
                    },
                    "acknowledgments": {
                        "generate_ta1": True,
                        "generate_999": True
                    }
                }
            }
        }
    )


class WorkflowUpdate(BaseModel):
    """Schema for updating a workflow."""
    name: Optional[str] = Field(None, description="Workflow name")
    description: Optional[str] = Field(None, description="Workflow description")
    tags: Optional[List[str]] = Field(None, description="Workflow tags")
    configuration: Optional[Dict[str, Any]] = Field(None, description="Workflow configuration")
    status: Optional[WorkflowStatus] = Field(None, description="Workflow status")


class WorkflowResponse(BaseModel):
    """Schema for workflow response."""
    workflow_id: PyUUID = Field(..., description="Workflow ID")
    tenant_id: str = Field(..., description="Tenant ID")
    name: str = Field(..., description="Workflow name")
    description: Optional[str] = Field(None, description="Workflow description")
    tags: Optional[List[str]] = Field(None, description="Workflow tags")
    template_id: str = Field(..., description="Template ID")
    configuration: Dict[str, Any] = Field(..., description="Workflow configuration")
    status: WorkflowStatus = Field(..., description="Workflow status")
    nifi_process_group_id: Optional[str] = Field(None, description="NiFi process group ID")
    nifi_parameter_context_id: Optional[str] = Field(None, description="NiFi parameter context ID")
    deployment_method: Optional[DeploymentMethod] = Field(None, description="Deployment method")
    flow_version: Optional[int] = Field(None, description="Flow version")
    created_by: Optional[str] = Field(None, description="Creator user ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    is_deployed: bool = Field(..., description="Whether the workflow is deployed to NiFi")

    model_config = ConfigDict(from_attributes=True)


class WorkflowListResponse(BaseModel):
    """Schema for workflow list response."""
    workflows: List[WorkflowResponse] = Field(..., description="List of workflows")
    total: int = Field(..., description="Total number of workflows")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Page size")


class TemplateExport(BaseModel):
    """Schema for template export."""
    template: TemplateResponse = Field(..., description="Template data")
    versions: List[TemplateVersionResponse] = Field(..., description="Template versions")
    metadata: Dict[str, Any] = Field(..., description="Export metadata")


class TemplateImport(BaseModel):
    """Schema for template import."""
    template_data: Dict[str, Any] = Field(..., description="Template data to import")
    import_options: Dict[str, Any] = Field(
        default_factory=dict,
        description="Import options"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "template_data": {
                    "template": {},
                    "versions": [],
                    "metadata": {}
                },
                "import_options": {
                    "overwrite_existing": False,
                    "validate_before_import": True,
                    "assign_new_id": True
                }
            }
        }
    )


class WorkflowActionRequest(BaseModel):
    """Schema for workflow action requests."""
    action: str = Field(..., description="Action to perform")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Action parameters")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "action": "pause",
                "parameters": {
                    "reason": "Maintenance window"
                }
            }
        }
    )


class TemplateSearchRequest(BaseModel):
    """Schema for template search requests."""
    query: Optional[str] = Field(None, description="Search query")
    scope: Optional[TemplateScope] = Field(None, description="Template scope filter")
    category: Optional[TemplateCategory] = Field(None, description="Category filter")
    tags: Optional[List[str]] = Field(None, description="Tags filter")
    status: Optional[TemplateStatus] = Field(None, description="Status filter")
    featured_only: bool = Field(False, description="Show only featured templates")
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(20, ge=1, le=100, description="Page size")


class WorkflowSearchRequest(BaseModel):
    """Schema for workflow search requests."""
    query: Optional[str] = Field(None, description="Search query")
    template_id: Optional[str] = Field(None, description="Template ID filter")
    status: Optional[WorkflowStatus] = Field(None, description="Status filter")
    tags: Optional[List[str]] = Field(None, description="Tags filter")
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(20, ge=1, le=100, description="Page size")


# ==============================================================================
# Workflow Execution Schemas
# ==============================================================================

class WorkflowExecutionRequest(BaseModel):
    """Request schema for executing a workflow."""
    request_id: Optional[str] = Field(default=None, description="Optional request ID for tracking")
    enable_monitoring: bool = Field(default=True, description="Enable background monitoring")
    monitoring_interval_seconds: int = Field(default=30, description="Monitoring check interval")
    execution_parameters: Optional[Dict[str, Any]] = Field(None, description="Additional execution parameters")

class WorkflowExecutionResponse(BaseModel):
    """Response schema for workflow execution."""
    workflow_id: str = Field(..., description="Workflow ID")
    execution_id: str = Field(..., description="Execution ID")
    status: WorkflowStatus = Field(..., description="Current execution status")
    nifi_process_group_id: Optional[str] = Field(None, description="NiFi process group ID")
    nifi_status: Optional[str] = Field(None, description="NiFi status")
    deployment_method: Optional[str] = Field(None, description="Deployment method")
    started_at: Optional[datetime] = Field(None, description="Start timestamp")
    stopped_at: Optional[datetime] = Field(None, description="Stop timestamp")
    restarted_at: Optional[datetime] = Field(None, description="Restart timestamp")
    message: str = Field(..., description="Status message")
    monitoring_enabled: Optional[bool] = Field(None, description="Whether monitoring is enabled")
    health_check: Optional[Dict[str, Any]] = Field(None, description="Health check results")

# ==============================================================================
# Original Workflow Execution Schemas
# ==============================================================================

class ProcessingOutput(BaseModel):
    """Represents an output generated by workflow processing."""
    name: str = Field(..., description="Output identifier")
    type: str = Field(..., description="Output type: 'download', 'display', 'status'")
    label: str = Field(..., description="Human-readable label")
    content: Optional[str] = Field(None, description="Text content for display")
    download_filename: Optional[str] = Field(None, description="Suggested download filename")
    mime_type: Optional[str] = Field(None, description="MIME type for downloads")
    file_extension: Optional[str] = Field(None, description="File extension for downloads")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional output metadata")

class GenericWorkflowExecutionRequest(BaseModel):
    """Generic workflow execution request for content processing."""
    content: str = Field(..., description="File content to process")
    file_type: Optional[str] = Field(None, description="Content type hint (e.g., 'edi', 'json', 'csv', 'xml')")
    request_id: Optional[str] = Field(None, description="Client request ID for tracking")
    processing_options: Dict[str, Any] = Field(
        default_factory=dict,
        description="Workflow-specific processing options"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Additional file metadata (encoding, source, etc.)"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "title": "EDI Processing",
                    "content": "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *250816*1030*U*00401*000000001*0*P*>~",
                    "file_type": "edi",
                    "processing_options": {
                        "generate_ta1": True,
                        "generate_999": False,
                        "validate_syntax": True
                    }
                },
                {
                    "title": "JSON Transformation",
                    "content": '{"customer": {"name": "John Doe", "orders": [{"id": 1, "amount": 100}]}}',
                    "file_type": "json",
                    "processing_options": {
                        "output_format": "csv",
                        "include_headers": True,
                        "flatten_nested": True
                    }
                },
                {
                    "title": "CSV Processing",
                    "content": "name,age,city\nJohn,30,NYC\nJane,25,LA",
                    "file_type": "csv",
                    "processing_options": {
                        "has_headers": True,
                        "delimiter": ",",
                        "output_format": "json"
                    }
                }
            ]
        }
    )


class GenericWorkflowExecutionResponse(BaseModel):
    """Generic workflow execution response for content processing."""
    success: bool = Field(..., description="Whether processing succeeded")
    outputs: List[ProcessingOutput] = Field(
        default=[], 
        description="Generated outputs from processing"
    )
    processing_time_ms: int = Field(..., description="Processing duration")
    workflow_id: str = Field(..., description="Workflow that processed the request")
    processed_at: datetime = Field(..., description="Processing timestamp")
    validation_results: Optional[List[ValidationFinding]] = Field(
        default=None, 
        description="Validation results if applicable"
    )
    request_id: Optional[str] = Field(None, description="Client request ID")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "title": "EDI Processing Result",
                    "success": True,
                    "outputs": [
                        {
                            "name": "ta1_acknowledgment",
                            "type": "download",
                            "label": "TA1 Response",
                            "content": "ISA*00*          *00*          *ZZ*RECEIVER       *ZZ*SENDER         *250816*1031*U*00401*000000001*0*P*>~TA1*000000001*250816*1031*A*000~IEA*1*000000001~",
                            "download_filename": "ta1_response.edi",
                            "mime_type": "text/plain",
                            "file_extension": ".edi"
                        },
                        {
                            "name": "validation_report",
                            "type": "display",
                            "label": "Validation Results",
                            "content": "Document is valid. No errors found."
                        }
                    ],
                    "processing_time_ms": 180,
                    "workflow_id": "workflow-uuid-123",
                    "processed_at": "2025-08-16T10:31:00Z"
                },
                {
                    "title": "JSON to CSV Conversion Result",
                    "success": True,
                    "outputs": [
                        {
                            "name": "converted_file",
                            "type": "download",
                            "label": "Converted CSV",
                            "content": "name,age,city\nJohn Doe,30,NYC",
                            "download_filename": "converted_data.csv",
                            "mime_type": "text/csv",
                            "file_extension": ".csv"
                        },
                        {
                            "name": "conversion_summary",
                            "type": "display",
                            "label": "Conversion Summary", 
                            "content": "Successfully converted 1 JSON object to CSV format with 3 columns"
                        }
                    ],
                    "processing_time_ms": 45,
                    "workflow_id": "workflow-uuid-456",
                    "processed_at": "2025-08-16T10:32:00Z"
                }
            ]
        }
    )


# ==============================================================================
# UI Configuration Schemas
# ==============================================================================

class ProcessingOption(BaseModel):
    """Configuration for a processing option in the UI."""
    name: str = Field(..., description="Option identifier")
    type: str = Field(..., description="Option type: 'boolean', 'string', 'number', 'select'")
    label: str = Field(..., description="Human-readable label")
    description: Optional[str] = Field(None, description="Help text")
    default_value: Optional[Any] = Field(None, description="Default value")
    options: Optional[List[str]] = Field(None, description="Options for select type")
    required: bool = Field(False, description="Whether option is required")
    min_value: Optional[float] = Field(None, description="Minimum value for number type")
    max_value: Optional[float] = Field(None, description="Maximum value for number type")
    pattern: Optional[str] = Field(None, description="Regex pattern for string validation")

class InputConfiguration(BaseModel):
    """Configuration for the input section of the UI."""
    title: str = Field(..., description="Input section title")
    accepted_file_types: List[str] = Field(default=[], description="Accepted file extensions")
    placeholder_text: str = Field(..., description="Placeholder text for input area")
    supports_text_input: bool = Field(True, description="Allow direct text input")
    supports_file_upload: bool = Field(True, description="Allow file upload")
    max_file_size_mb: Optional[int] = Field(None, description="Maximum file size in MB")
    input_validation: Optional[str] = Field(None, description="Input validation regex")

class OutputConfiguration(BaseModel):
    """Configuration for an output in the UI."""
    name: str = Field(..., description="Output identifier")
    label: str = Field(..., description="Human-readable label")
    type: str = Field(..., description="Output type: 'download', 'display', 'status'")
    description: Optional[str] = Field(None, description="Output description")
    file_extension: Optional[str] = Field(None, description="File extension for downloads")
    icon: Optional[str] = Field(None, description="Icon name for UI display")

class WorkflowUIConfiguration(BaseModel):
    """Complete UI configuration for dynamic interface generation."""
    input: InputConfiguration
    processing_options: List[ProcessingOption] = Field(default=[], description="Available processing options")
    outputs: List[OutputConfiguration] = Field(default=[], description="Expected outputs")
    theme: Optional[Dict[str, str]] = Field(None, description="UI theme customization")
    help_text: Optional[str] = Field(None, description="General help text for the workflow")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "title": "EDI Processing UI Config",
                    "input": {
                        "title": "📄 EDI Document Input",
                        "accepted_file_types": [".edi", ".x12", ".txt"],
                        "placeholder_text": "Paste your EDI content here or upload a file...",
                        "supports_text_input": True,
                        "supports_file_upload": True,
                        "max_file_size_mb": 10
                    },
                    "processing_options": [
                        {
                            "name": "generate_ta1",
                            "type": "boolean",
                            "label": "Generate TA1 Acknowledgment",
                            "description": "Generate technical acknowledgment",
                            "default_value": True
                        },
                        {
                            "name": "validation_level",
                            "type": "select",
                            "label": "Validation Level",
                            "options": ["basic", "strict", "comprehensive"],
                            "default_value": "basic"
                        }
                    ],
                    "outputs": [
                        {
                            "name": "ta1_acknowledgment",
                            "label": "TA1 Response",
                            "type": "download",
                            "file_extension": ".edi"
                        },
                        {
                            "name": "validation_report",
                            "label": "Validation Results",
                            "type": "display"
                        }
                    ]
                },
                {
                    "title": "CSV Processing UI Config",
                    "input": {
                        "title": "📊 CSV Data Input",
                        "accepted_file_types": [".csv", ".tsv"],
                        "placeholder_text": "Upload your CSV file or paste data here...",
                        "supports_text_input": True,
                        "supports_file_upload": True,
                        "max_file_size_mb": 100
                    },
                    "processing_options": [
                        {
                            "name": "has_headers",
                            "type": "boolean",
                            "label": "File has headers",
                            "description": "First row contains column names",
                            "default_value": True
                        },
                        {
                            "name": "delimiter",
                            "type": "select",
                            "label": "Field delimiter",
                            "options": [",", ";", "|", "\\t"],
                            "default_value": ","
                        },
                        {
                            "name": "output_format",
                            "type": "select",
                            "label": "Output format",
                            "options": ["json", "xml", "parquet", "excel"],
                            "default_value": "json"
                        }
                    ],
                    "outputs": [
                        {
                            "name": "converted_data",
                            "label": "Converted Data",
                            "type": "download"
                        },
                        {
                            "name": "processing_summary",
                            "label": "Processing Summary",
                            "type": "display"
                        }
                    ]
                }
            ]
        }
    )


class WorkflowStatusResponse(BaseModel):
    """Response schema for detailed workflow status."""
    workflow_id: str = Field(..., description="Workflow ID")
    status: WorkflowStatus = Field(..., description="Current workflow status")
    nifi_status: Optional[str] = Field(None, description="NiFi process group status")
    deployment_status: Optional[str] = Field(None, description="Deployment status")
    last_execution: Optional[datetime] = Field(None, description="Last execution timestamp")
    execution_count: int = Field(0, description="Total execution count")
    error_count: int = Field(0, description="Total error count")
    success_rate: float = Field(0.0, description="Success rate (0.0 to 1.0)")
    process_group_id: Optional[str] = Field(None, description="NiFi process group ID")
    parameter_context_id: Optional[str] = Field(None, description="NiFi parameter context ID")
    flow_version: Optional[int] = Field(None, description="Current flow version")
    health_check: Dict[str, Any] = Field(
        default_factory=dict,
        description="Health check results"
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "workflow_id": "workflow-uuid-123",
                "status": "ACTIVE",
                "nifi_status": "RUNNING",
                "deployment_status": "DEPLOYED",
                "last_execution": "2025-08-16T10:30:00Z",
                "execution_count": 1547,
                "error_count": 12,
                "success_rate": 0.992,
                "process_group_id": "process-group-uuid",
                "parameter_context_id": "param-context-uuid",
                "flow_version": 3,
                "health_check": {
                    "status": "healthy",
                    "last_check": "2025-08-16T10:35:00Z",
                    "issues": []
                }
            }
        }
    )


# ==============================================================================
# Configuration Validation Schemas
# ==============================================================================

class ConfigurationValidationRequest(BaseModel):
    """Request schema for configuration validation."""
    configuration: Dict[str, Any] = Field(..., description="Configuration to validate")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "configuration": {
                    "input_path": "/sftp/tenants/tenant-a/claims/in/",
                    "file_patterns": ["*.edi", "*.x12"],
                    "validation": {
                        "schema": "837.5010.X222.A1.json",
                        "snip_level": 3
                    },
                    "acknowledgments": {
                        "generate_ta1": True,
                        "generate_999": False
                    }
                }
            }
        }
    )


class ValidationError(BaseModel):
    """Schema for validation error."""
    field: str = Field(..., description="Field with error")
    message: str = Field(..., description="Error message") 
    current_value: Optional[Any] = Field(None, description="Current value")
    expected_pattern: Optional[str] = Field(None, description="Expected pattern or format")
    available_options: Optional[List[str]] = Field(None, description="Available valid options")


class ValidationWarning(BaseModel):
    """Schema for validation warning."""
    field: str = Field(..., description="Field with warning")
    message: str = Field(..., description="Warning message")
    severity: str = Field(..., description="Warning severity level")


class ValidationRecommendation(BaseModel):
    """Schema for validation recommendation."""
    field: str = Field(..., description="Field for recommendation")
    message: str = Field(..., description="Recommendation message")
    suggestion: Optional[str] = Field(None, description="Suggested value")


class ConfigurationValidationResponse(BaseModel):
    """Response schema for configuration validation."""
    valid: bool = Field(..., description="Whether configuration is valid")
    errors: List[ValidationError] = Field(default=[], description="Validation errors")
    warnings: List[ValidationWarning] = Field(default=[], description="Validation warnings")
    recommendations: List[ValidationRecommendation] = Field(
        default=[], 
        description="Configuration recommendations"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "valid": False,
                "errors": [
                    {
                        "field": "input_path",
                        "message": "Path must start with /sftp/tenants/{tenant_id}/",
                        "current_value": "/invalid/path/",
                        "expected_pattern": "^/sftp/tenants/tenant-a/.+/$"
                    }
                ],
                "warnings": [
                    {
                        "field": "acknowledgments.generate_999",
                        "message": "999 acknowledgments are recommended for production workflows",
                        "severity": "low"
                    }
                ],
                "recommendations": [
                    {
                        "field": "output.archive_path",
                        "message": "Consider adding archive path for processed files",
                        "suggestion": "/sftp/tenants/tenant-a/claims/archive/"
                    }
                ]
            }
        }
    )