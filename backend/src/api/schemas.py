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