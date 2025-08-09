from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional, Literal

from src.agents.models import UniversalAgentResponse, ElementEnrichment
from src.models.profile_criterion import FieldSource, Operator

# --- THIS IS THE NEW SECTION ---

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

# --- END OF NEW SECTION ---


# --- Schemas for Creating Data ---

class ProfileCriterionCreate(BaseModel):
    field_source: FieldSource
    field_identifier: str
    operator: Operator
    value: str

class PartnerProfileCreate(BaseModel):
    name: str
    implementation_guide: str
    priority: int = 10
    criteria: List[ProfileCriterionCreate]
    validation_schema_name: Optional[str] = None
    # Enhanced validation configuration
    snip_level: str = "SNIP3"
    generate_ta1: bool = True
    generate_999: bool = False
    custom_validation_rules: Optional[dict] = None

class TradingPartnerCreate(BaseModel):
    name: str
    description: Optional[str] = None
    profiles: List[PartnerProfileCreate]
    # SFTP Configuration (optional)
    sftp_enabled: Optional[bool] = False
    sftp_username: Optional[str] = None
    sftp_password: Optional[str] = None
    authentication_type: Optional[str] = "PASSWORD"
    ssh_public_key: Optional[str] = None
    file_name_patterns: Optional[str] = '["*.edi", "*.x12"]'
    poll_schedule_id: Optional[int] = None
    poll_enabled: Optional[bool] = True
    response_filename_template: Optional[str] = None
    response_timeout_minutes: Optional[int] = 5
    max_file_size_bytes: Optional[int] = 52428800

# --- Schemas for Updating Data ---

class ProfileCriterionUpdate(ProfileCriterionCreate):
    id: Optional[int] = None

class PartnerProfileUpdate(PartnerProfileCreate):
    id: Optional[int] = None
    criteria: List[ProfileCriterionUpdate]
    validation_schema_name: Optional[str] = None
    # Enhanced validation configuration (inherited from PartnerProfileCreate)

class TradingPartnerUpdate(BaseModel):
    name: str
    description: Optional[str] = None
    profiles: List[PartnerProfileUpdate]
    # SFTP Configuration (optional)
    sftp_enabled: Optional[bool] = False
    sftp_username: Optional[str] = None
    sftp_password: Optional[str] = None
    authentication_type: Optional[str] = "PASSWORD"
    ssh_public_key: Optional[str] = None
    file_name_patterns: Optional[str] = '["*.edi", "*.x12"]'
    poll_schedule_id: Optional[int] = None
    poll_enabled: Optional[bool] = True
    response_filename_template: Optional[str] = None
    response_timeout_minutes: Optional[int] = 5
    max_file_size_bytes: Optional[int] = 52428800


# --- Schemas for Reading Data (Response Models) ---

class ProfileCriterion(ProfileCriterionCreate):
    id: int
    profile_id: int
    tenant_id: str
    model_config = ConfigDict(from_attributes=True)

class PartnerProfile(PartnerProfileCreate):
    id: int
    partner_id: int
    tenant_id: str
    criteria: List[ProfileCriterion]
    validation_schema_name: Optional[str] = None
    # Enhanced validation configuration (inherited from PartnerProfileCreate)
    model_config = ConfigDict(from_attributes=True)

class TradingPartner(TradingPartnerCreate):
    id: int
    tenant_id: str
    name: str
    description: Optional[str] = None
    profiles: List[PartnerProfile]
    model_config = ConfigDict(from_attributes=True)


# --- EDI & Validation Schemas (Partially Updated) ---
class EdiElement(BaseModel):
    value: str

class EdiSegment(BaseModel):
    id: str
    elements: List[EdiElement]
    line_number: int

class ValidationRequest(BaseModel):
    edi_data: str
    file_name: Optional[str] = None
    profile_name: Optional[str] = None  # Optional manual profile override

# --- THIS RESPONSE IS NOW UPDATED ---
class ValidationResponse(BaseModel):
    valid: bool
    status: str  # Keep for backwards compatibility
    findings: List[ValidationFinding] = []
    errors: List[ValidationFinding] = []  # Alias for findings for compatibility
    ta1_content: Optional[str] = None
    ta1_999_content: Optional[str] = None
    processing_time_ms: Optional[int] = None
    matched_profile: Optional[str] = None
    schema_used: Optional[str] = None
    snip_level_used: Optional[str] = None
    detection_method: Optional[str] = None  # "auto" or "manual"
    # Legacy fields for backwards compatibility
    ta1_acknowledgement: Optional[str] = None
    ack999_acknowledgement: Optional[str] = None

class EnrichmentAnalysisRequest(BaseModel):
    """Request to start a new schema enrichment analysis job."""
    schema_name: str = Field(..., description="The name of the schema file to analyze, e.g., '837.5010.X222.A1.json'.")
    segment_id: str = Field(..., description="The segment ID to focus the analysis on, e.g., 'CLM'.")
    context_id: str = Field(..., description="The specific contextual ID for the segment, e.g., '2300.CLM'.")

class EnrichmentJobStartResponse(BaseModel):
    """Response containing the ID of the started analysis job."""
    job_id: str

class EnrichmentJobStatusResponse(BaseModel):
    """Response describing the status and result of an analysis job."""
    job_id: str
    status: Literal["running", "complete", "failed"]
    result: Optional[UniversalAgentResponse] = None # We need to import UniversalAgentResponse
    error: Optional[str] = None    

class EnrichmentApplyRequest(BaseModel):
    """Request to apply a single JSON patch to a schema."""
    schema_name: str
    patch: ElementEnrichment    

class FullEnrichmentAnalysisRequest(BaseModel):
    """Request to start a new full schema analysis job."""
    schema_name: str = Field(..., description="The name of the schema file to analyze, e.g., '837.5010.X222.A1.json'.")

class EnrichmentApplyBatchRequest(BaseModel):
    """Request to apply a batch of JSON patches to a schema."""
    schema_name: str
    patches: List[ElementEnrichment]


class MessageResponse(BaseModel):
    """Simple response with a message."""
    message: str