# FILE: backend/src/edi_schemas/edi_guide.py
from pydantic import BaseModel, Field
from typing import List, Optional, Union, Dict, Any, Literal, Annotated

class CodeDefinition(BaseModel):
    """Represents a single valid code and its optional description."""
    code: Any
    description: Optional[str] = None

class ValidCodes(BaseModel):
    """A container for a list of valid code definitions."""
    codes: List[CodeDefinition]

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
    # For composite elements, which are nested lists of BaseElement
    elements: Optional[List['BaseElement']] = None

class SegmentDefinition(BaseModel):
    """Defines the structure and rules for a single base segment (e.g., NM1, CLM)."""
    name: str
    description: str
    usage: str # Default usage (e.g., 'S' for Situational)
    elements: List[BaseElement]
    syntax: Optional[List[str]] = None

class ContextualElementOverride(BaseModel):
    """Defines the properties of an element that can be overridden in a specific context."""
    valid_codes: Optional[ValidCodes] = None
    description: Optional[str] = None
    usage: Optional[str] = None # e.g., 'R' to make a situational element required

class ContextualDefinition(BaseModel):
    """Defines a set of overrides for a segment within a specific loop context."""
    name: str
    description: Optional[str] = None
    # Dictionary of overrides, keyed by element xid (e.g., "CLM01")
    elements: Dict[str, ContextualElementOverride]

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
    The top-level model for our standardized v2 EDI implementation guide schema.
    """
    transactionName: str
    version: str
    description: str
    rules: List[Dict[str, Any]] = Field(default_factory=list)
    contextualDefinitions: Dict[str, ContextualDefinition] = Field(default_factory=dict)
    segmentDefinitions: Dict[str, SegmentDefinition] = Field(default_factory=dict)
    structure: List[StructureLoop]

    def get_version_key(self) -> str:
        """Helper to get the primary key for the schema manager."""
        return self.version
    
    def get_all_structured_segments(self) -> List[Dict[str, str]]:
        """
        Traverses the structure and returns a list of all unique segment/context pairs.
        """
        found = []
        unique_check = set()

        def _traverse(nodes: List['StructureChild']):
            for node in nodes:
                if isinstance(node, StructureSegment):
                    context_id = node.contextId or f"loop_{node.xid}"
                    if (node.xid, context_id) not in unique_check:
                        found.append({"segment_id": node.xid, "context_id": context_id})
                        unique_check.add((node.xid, context_id))
                elif isinstance(node, StructureLoop) and node.children:
                    _traverse(node.children)
        
        _traverse(self.structure)
        return found    

# Rebuild models to resolve forward references in BaseElement and StructureLoop.
BaseElement.model_rebuild()
StructureLoop.model_rebuild()