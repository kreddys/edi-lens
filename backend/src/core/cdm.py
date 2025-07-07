from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

# Canonical Data Model (CDM) for representing a parsed EDI transaction.
# This hierarchical structure allows for easier validation, conversion, and data access.

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

class CdmLoop(BaseModel):
    """
    Represents a hierarchical loop within an EDI transaction (e.g., 2000A, 2400).
    It can contain segments and other nested loops.
    """
    loop_id: str
    segments: List[CdmSegment] = Field(default_factory=list)
    loops: Dict[str, List['CdmLoop']] = Field(default_factory=dict) # Keyed by loop_id for easy access

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

# Rebuild the model to resolve the forward reference for nested loops.
CdmLoop.model_rebuild()