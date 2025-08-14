# FILE: backend/src/api/schemas.py

from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional, Literal

from src.agents.models import UniversalAgentResponse, ElementEnrichment

# --- REMOVED: Unused imports from the now-deleted criteria model ---
# from src.models.profile_criterion import FieldSource, Operator

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

class EnrichmentAnalysisRequest(BaseModel):
    schema_name: str = Field(..., description="The name of the schema file to analyze, e.g., '837.5010.X222.A1.json'.")
    segment_id: str = Field(..., description="The segment ID to focus the analysis on, e.g., 'CLM'.")
    context_id: str = Field(..., description="The specific contextual ID for the segment, e.g., '2300.CLM'.")

class EnrichmentJobStartResponse(BaseModel):
    job_id: str

class EnrichmentJobStatusResponse(BaseModel):
    job_id: str
    status: Literal["running", "complete", "failed"]
    result: Optional[UniversalAgentResponse] = None
    error: Optional[str] = None

class EnrichmentApplyRequest(BaseModel):
    schema_name: str
    patch: ElementEnrichment

class FullEnrichmentAnalysisRequest(BaseModel):
    schema_name: str = Field(..., description="The name of the schema file to analyze, e.g., '837.5010.X222.A1.json'.")

class EnrichmentApplyBatchRequest(BaseModel):
    schema_name: str
    patches: List[ElementEnrichment]

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
    generate_ta1: bool = Field(default=False, description="Generate TA1 acknowledgment")
    generate_999: bool = Field(default=False, description="Generate 999 acknowledgment")

class RealtimeEDIValidationResponse(BaseModel):
    """Response schema for real-time EDI validation."""
    valid: bool = Field(..., description="Whether the EDI document is valid")
    validation_results: List[ValidationFinding] = Field(default=[], description="Validation findings")
    processing_time_ms: int = Field(..., description="Processing time in milliseconds")
    schema_used: str = Field(..., description="Schema used for validation")
    snip_level_used: int = Field(..., description="SNIP level used for validation")
    ta1_content: Optional[str] = Field(None, description="TA1 acknowledgment content if generated")
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