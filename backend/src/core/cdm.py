from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

# Canonical Data Model (CDM) for representing a parsed EDI transaction.
# This hierarchical structure allows for easier validation, conversion, and data access.

class CdmValidationError(BaseModel):
    """Represents a validation error found during parsing."""
    message: str
    line_number: Optional[int] = None
    segment_id: Optional[str] = None

class CdmElement(BaseModel):
    """Represents a single data element within a segment."""
    value: str
    position: int

class CdmSegment(BaseModel):
    """Represents a single EDI segment."""
    segment_id: str
    elements: List[CdmElement]
    line_number: int
    raw_segment: str # Store the original segment string for reference
    errors: List[CdmValidationError] = Field(default_factory=list)


class CdmLoop(BaseModel):
    """
    Represents a hierarchical loop within an EDI transaction (e.g., 2000A, 2400).
    It can contain segments and other nested loops.
    """
    loop_id: str
    segments: List[CdmSegment] = Field(default_factory=list)
    loops: Dict[str, List['CdmLoop']] = Field(default_factory=dict) # Keyed by loop_id for easy access
    errors: List[CdmValidationError] = Field(default_factory=list)


    def add_loop(self, loop: 'CdmLoop'):
        """Adds a nested loop to this loop."""
        if loop.loop_id not in self.loops:
            self.loops[loop.loop_id] = []
        self.loops[loop.loop_id].append(loop)

class CdmTransaction(BaseModel):
    """The root of the Canonical Data Model, representing a single transaction set (ST/SE)."""
    header: CdmSegment  # The ST segment
    trailer: CdmSegment # The SE segment
    body: CdmLoop       # A virtual root loop containing all transaction content
    errors: List[CdmValidationError] = Field(default_factory=list)

# --- THIS IS THE NEW CODE ---
class CdmFunctionalGroup(BaseModel):
    """Represents a single functional group (GS/GE)."""
    header: CdmSegment  # The GS segment
    trailer: CdmSegment # The GE segment
    transactions: List[CdmTransaction] = Field(default_factory=list)
    errors: List[CdmValidationError] = Field(default_factory=list)

class CdmInterchange(BaseModel):
    """The absolute root of the file, representing the interchange (ISA/IEA)."""
    header: CdmSegment # The ISA segment
    trailer: CdmSegment # The IEA segment
    functional_groups: List[CdmFunctionalGroup] = Field(default_factory=list)
    errors: List[CdmValidationError] = Field(default_factory=list)
# --- END OF NEW CODE ---


# Rebuild the model to resolve the forward reference for nested loops.
CdmLoop.model_rebuild()