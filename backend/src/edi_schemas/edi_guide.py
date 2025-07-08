from pydantic import BaseModel, Field
from typing import List, Optional, Union, Dict, Any, Annotated, Literal

# --- THIS IS THE FIX ---
# Updated `StructureLoopDefinition` to allow `repeat` to be a string or integer.

class ValidCodes(BaseModel):
    """Defines the list of valid codes for a specific element."""
    code: List[Union[str, int]]

class ElementDefinition(BaseModel):
    """Defines a single data element within a segment."""
    xid: str
    data_ele: Union[str, int]
    name: str
    usage: str
    seq: str
    valid_codes: Optional[ValidCodes] = None
    elements: Optional[List['ElementDefinition']] = None

class SegmentDefinition(BaseModel):
    """Defines the structure and rules for a single segment (e.g., NM1, CLM)."""
    name: str
    usage: str
    pos: str
    max_use: int
    elements: List[ElementDefinition]
    elementsByXid: Dict[str, ElementDefinition] = Field(..., alias='elementsByXid')
    syntax: Optional[List[Optional[str]]] = None

class StructureLoopDefinition(BaseModel):
    """Represents a loop within the EDI structure (e.g., 2000A)."""
    type: Literal['loop']
    xid: str
    name: str
    usage: str
    pos: str
    repeat: Union[str, int] # Changed from str to Union[str, int]
    children: List['StructureChild']

class StructureSegmentDefinition(BaseModel):
    """Represents a segment's position within the EDI structure."""
    type: Literal['segment']
    xid: str
    pos: str
    usage: str
    max_use: int = Field(..., alias='max_use')
    name: str
    definitionId: Optional[str] = None

StructureChild = Annotated[
    Union[StructureLoopDefinition, StructureSegmentDefinition],
    Field(discriminator='type')
]

# Rebuild the model to resolve the forward references.
StructureLoopDefinition.model_rebuild()
ElementDefinition.model_rebuild()


class ImplementationGuideSchema(BaseModel):
    """
    The top-level model representing a complete implementation guide schema,
    parsed from a JSON definition file.
    """
    transactionName: str = Field(..., alias='transactionName')
    segmentDefinitions: Dict[str, SegmentDefinition] = Field(..., alias='segmentDefinitions')
    structure: List[StructureChild]

    def get_gs08_version(self) -> Optional[str]:
        """
        Helper method to extract the GS08 version identifier from the schema,
        which is used as the primary key for loading guides.
        """
        gs_def = self.segmentDefinitions.get("GS")
        if gs_def:
            gs08_def = gs_def.elementsByXid.get("GS08")
            if gs08_def and gs08_def.valid_codes:
                return str(gs08_def.valid_codes.code[0])
        return None