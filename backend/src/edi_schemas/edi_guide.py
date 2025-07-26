# FILE: backend/src/edi_schemas/edi_guide.py
from pydantic import BaseModel, Field, AliasChoices
from typing import List, Optional, Union, Dict, Any, Literal, Annotated

class CodeDefinition(BaseModel):
    """Represents a single valid code and its description."""
    code: str
    description: str

class BaseElement(BaseModel):
    """Defines a single data element, with strict data types."""
    xid: str
    data_ele: str
    name: str
    usage: Literal['R', 'S', 'N'] # <-- STRICTLY one of these three values
    seq: int
    dataType: Literal['ID', 'AN', 'DT', 'TM', 'N0', 'N1', 'N2', 'R'] # <-- Common EDI types
    description: Optional[str] = None
    minLength: Optional[int] = None
    maxLength: Optional[int] = None
    format: Optional[Union[str, List[str]]] = None
    valid_codes: Optional[List[CodeDefinition]] = None
    sub_elements: Optional[List['BaseElement']] = Field(default=None, alias="elements")

class SegmentDefinition(BaseModel):
    """Defines the structure for a segment, with strict data types."""
    id: str
    name: str
    description: str
    usage: Literal['R', 'S', 'N'] # <-- STRICTLY one of these three values
    max_use: int = Field(validation_alias=AliasChoices("max_use", "maxUse"), default=1)
    elements: List[BaseElement]
    syntax: Optional[List[str]] = None

# --- MODELS FOR CONTEXTUAL OVERRIDES ---
class ContextualElementOverride(BaseModel):
    """
    Defines a sparse set of overrides for a single element within a context.
    Only fields that are different from the base definition should be present.
    """
    # --- THIS IS THE FULL, UPDATED LIST OF OVERRIDABLE FIELDS ---
    usage: Optional[Literal['R', 'S', 'N']] = None
    name: Optional[str] = None
    description: Optional[str] = None
    dataType: Optional[Literal['ID', 'AN', 'DT', 'TM', 'N0', 'N1', 'N2', 'R']] = None
    minLength: Optional[int] = None
    maxLength: Optional[int] = None
    format: Optional[Union[str, List[str]]] = None
    valid_codes: Optional[List[CodeDefinition]] = None
    # --- END OF UPDATED LIST ---

class ContextualDefinition(BaseModel):
    """
    Defines a set of overrides for a segment within a specific loop context.
    The `id` should match the contextId from the schema structure (e.g., '1000A.NM1').
    """
    id: str
    name: str
    description: Optional[str] = None
    # The keys of this dictionary are the element XIDs (e.g., "NM101", "NM108")
    elements: Dict[str, ContextualElementOverride]

# --- MODELS FOR HIERARCHICAL STRUCTURE (Unchanged) ---
class StructureSegment(BaseModel):
    type: Literal['segment']
    xid: str
    usage: str
    max_use: int
    baseDefinitionId: str
    contextId: Optional[str] = None

class StructureLoop(BaseModel):
    type: Literal['loop']
    xid: str
    name: str
    usage: str
    repeat: Union[str, int] # Keep this flexible as it can be ">1" or an int
    children: List['StructureChild'] = Field(default_factory=list)

StructureChild = Annotated[Union[StructureLoop, StructureSegment], Field(discriminator='type')]

class ImplementationGuideSchema(BaseModel):
    transactionName: str
    version: str
    description: str
    rules: List[Dict[str, Any]] = Field(default_factory=list)
    contextualDefinitions: Dict[str, ContextualDefinition] = Field(default_factory=dict)
    segmentDefinitions: Dict[str, SegmentDefinition] = Field(default_factory=dict)
    structure: List[StructureLoop]

    def get_version_key(self) -> str:
        return self.version

    def get_all_structured_segments(self) -> List[Dict[str, str]]:
        found = []
        unique_check = set()
        def _traverse(nodes: List['StructureChild']):
            for node in nodes:
                if isinstance(node, StructureSegment):
                    context_id = node.contextId or f"loop:{node.xid}"
                    if (node.xid, context_id) not in unique_check:
                        found.append({"segment_id": node.xid, "context_id": context_id})
                        unique_check.add((node.xid, context_id))
                elif isinstance(node, StructureLoop) and node.children:
                    _traverse(node.children)
        _traverse(self.structure)
        return found

BaseElement.model_rebuild()
StructureLoop.model_rebuild()