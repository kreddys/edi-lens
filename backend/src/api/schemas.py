from pydantic import BaseModel
from typing import List, Optional

# --- Core EDI Data Structures ---
class EdiElement(BaseModel):
    value: str

class EdiSegment(BaseModel):
    id: str
    elements: List[EdiElement]
    line_number: int

# --- Validation Finding Structures ---
class FindingLocation(BaseModel):
    loop_id: Optional[str] = None
    segment_id: str
    segment_instance: int
    element_position: int
    line_number: int
    value: Optional[str] = None

class ValidationFinding(BaseModel):
    level: str  # 'error' | 'warning' | 'info'
    code: str
    message: str
    location: FindingLocation

# --- API Request/Response Schemas ---
class ValidationRequest(BaseModel):
    edi_data: str
    partner_id: Optional[int] = None # Will be used to fetch configs
    implementation_guide: str # e.g., "837.5010.X222.A1"

class ValidationResponse(BaseModel):
    status: str # e.g., "Accepted", "Accepted with Errors", "Rejected"
    findings: List[ValidationFinding]
    ta1_acknowledgement: Optional[str] = None
    ack999_acknowledgement: Optional[str] = None
    parsed_segments: List[EdiSegment] # For debugging