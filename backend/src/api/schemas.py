from pydantic import BaseModel, ConfigDict
from typing import List, Optional

from src.models.profile_criterion import FieldSource, Operator

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

class TradingPartnerCreate(BaseModel):
    name: str
    description: Optional[str] = None
    # Each partner must be created with at least one profile
    profiles: List[PartnerProfileCreate]

# --- Schemas for Reading Data (Response Models) ---
# These include IDs and use from_attributes to map from ORM models.

class ProfileCriterion(ProfileCriterionCreate):
    id: int
    profile_id: int
    model_config = ConfigDict(from_attributes=True)

class PartnerProfile(PartnerProfileCreate):
    id: int
    partner_id: int
    criteria: List[ProfileCriterion]
    model_config = ConfigDict(from_attributes=True)

class TradingPartner(TradingPartnerCreate):
    id: int
    name: str
    description: Optional[str] = None
    profiles: List[PartnerProfile]
    model_config = ConfigDict(from_attributes=True)


# --- EDI & Validation Schemas (Unchanged) ---
class EdiElement(BaseModel):
    value: str

class EdiSegment(BaseModel):
    id: str
    elements: List[EdiElement]
    line_number: int

class ValidationRequest(BaseModel):
    edi_data: str
    file_name: Optional[str] = None

class FindingLocation(BaseModel):
    loop_id: Optional[str] = None
    segment_id: str
    segment_instance: int
    element_position: int
    line_number: int
    value: Optional[str] = None

class ValidationFinding(BaseModel):
    level: str
    code: str
    message: str
    location: FindingLocation

class ValidationResponse(BaseModel):
    status: str
    findings: List[ValidationFinding]
    ta1_acknowledgement: Optional[str] = None
    ack999_acknowledgement: Optional[str] = None
    parsed_segments: List[EdiSegment]