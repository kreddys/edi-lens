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