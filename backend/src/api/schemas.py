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

class TradingPartnerCreate(BaseModel):
    name: str
    description: Optional[str] = None
    profiles: List[PartnerProfileCreate]

# --- Schemas for Updating Data ---

class ProfileCriterionUpdate(ProfileCriterionCreate):
    id: Optional[int] = None

class PartnerProfileUpdate(PartnerProfileCreate):
    id: Optional[int] = None
    criteria: List[ProfileCriterionUpdate]
    validation_schema_name: Optional[str] = None

class TradingPartnerUpdate(BaseModel):
    name: str
    description: Optional[str] = None
    profiles: List[PartnerProfileUpdate]


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
    validation_schema_name: Optional[str] = None # And add this
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

# --- THIS RESPONSE IS NOW UPDATED ---
class ValidationResponse(BaseModel):
    status: str
    findings: List[ValidationFinding] # Changed from a simple string
    ta1_acknowledgement: Optional[str] = None
    ack999_acknowledgement: Optional[str] = None
    # parsed_segments is no longer needed as the CDM is an internal structure

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