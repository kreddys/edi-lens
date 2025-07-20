# FILE: backend/src/edi_schemas/edi_guide.py
from pydantic import BaseModel, Field
from typing import List, Optional, Union, Dict, Any, Literal, Annotated

class RuleDefinition(BaseModel):
    """Represents a single, codified complex validation rule."""
    ruleId: str
    description: str
    type: str
    target: Optional[Dict[str, Any]] = None
    conditions: Optional[List[Dict[str, Any]]] = None
    action: Dict[str, Any]

class CodeDefinition(BaseModel):
    """Represents a single valid code and its optional description."""
    code: Any
    description: Optional[str] = None

class ValidCodes(BaseModel):
    """A container for a list of valid code definitions."""
    codes: List[CodeDefinition]

class ContextualElementOverride(BaseModel):
    """Defines the properties of an element that can be overridden in a specific context."""
    valid_codes: Optional[ValidCodes] = None
    description: Optional[str] = None
    usage: Optional[str] = None

class ContextualDefinition(BaseModel):
    """Defines a set of overrides for a segment within a specific loop context."""
    name: str
    description: Optional[str] = None
    elements: Dict[str, ContextualElementOverride]

class BaseElement(BaseModel):
    """Defines a single data element within a base segment definition."""
    xid: str
    data_ele: Union[str, int]
    name: str
    usage: str
    seq: str
    dataType: str
    description: Optional[str] = None
    minLength: Optional[int] = None
    maxLength: Optional[int] = None
    format: Optional[str] = None
    valid_codes: Optional[ValidCodes] = None
    elements: Optional[List['BaseElement']] = None # For composite elements

class SegmentDefinition(BaseModel):
    """Defines the structure and rules for a single base segment (e.g., NM1, CLM)."""
    name: str
    description: str
    usage: str
    elements: List[BaseElement]
    syntax: Optional[List[str]] = None

class StructureSegment(BaseModel):
    """Represents a segment's position within the EDI structure."""
    type: Literal['segment']
    xid: str
    usage: str
    max_use: int
    baseDefinitionId: str
    contextId: Optional[str] = None

class StructureLoop(BaseModel):
    """Represents a loop within the EDI structure (e.g., 2000A)."""
    type: Literal['loop']
    xid: str
    name: str
    usage: str
    repeat: Union[str, int]
    children: List['StructureChild'] = Field(default_factory=list)

StructureChild = Annotated[
    Union[StructureLoop, StructureSegment],
    Field(discriminator='type')
]

class ImplementationGuideSchema(BaseModel):
    """
    The top-level model representing a complete implementation guide schema.
    """
    transactionName: str
    version: str
    description: str
    rules: List[RuleDefinition] = Field(default_factory=list)
    contextualDefinitions: Dict[str, ContextualDefinition] = Field(default_factory=dict)
    segmentDefinitions: Dict[str, SegmentDefinition] = Field(default_factory=dict)
    structure: List[StructureLoop]

    def get_version_key(self) -> str:
        """Helper to get the primary key for the schema manager."""
        return self.version

# Rebuild models for forward references.
BaseElement.model_rebuild()
StructureLoop.model_rebuild()