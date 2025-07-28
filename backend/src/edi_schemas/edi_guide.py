# FILE: backend/src/edi_schemas/edi_guide.py
from pydantic import BaseModel, Field, AliasChoices
from typing import List, Optional, Union, Dict, Any, Literal, Annotated

# --- NEW: Models for Structured Syntax Rules ---
class ConditionClause(BaseModel):
    element: str
    operator: Literal["IS", "IS_NOT", "IS_PRESENT", "IS_NOT_PRESENT"]
    value: Optional[Any] = None

class Conditions(BaseModel):
    ALL_OF: Optional[List[ConditionClause]] = Field(None, description="All conditions must be true (AND).")
    ANY_OF: Optional[List[ConditionClause]] = Field(None, description="Any condition can be true (OR).")

class AssertionClause(BaseModel):
    element: Optional[str] = None 
    elements: Optional[List[str]] = None
    assertion: Literal[
        "MUST_BE_FORMAT", 
        "MUST_HAVE_LENGTH", 
        "MUST_BE_PRESENT", 
        "MUST_NOT_BE_PRESENT",
        "ANY_OF_MUST_BE_PRESENT"
    ]
    value: Optional[Any] = None

class SyntaxRule(BaseModel):
    ruleId: str
    description: str
    snipLevel: int
    severity: Literal["error", "warning", "info"] = "error"
    tags: Optional[List[str]] = None
    conditions: Conditions
    then: List[AssertionClause]

# --- Models for Element and Segment Definitions ---
class CodeDefinition(BaseModel):
    code: str
    description: str

class BaseElement(BaseModel):
    xid: str
    data_ele: str
    name: str
    usage: Literal['R', 'S', 'N']
    seq: int
    dataType: Literal['ID', 'AN', 'DT', 'TM', 'N0', 'N1', 'N2', 'R', 'Composite']
    description: Optional[str] = None
    minLength: Optional[int] = None
    maxLength: Optional[int] = None
    format: Optional[Union[str, List[str]]] = None
    valid_codes: Optional[List[CodeDefinition]] = None
    sub_elements: Optional[List['BaseElement']] = None

class SegmentDefinition(BaseModel):
    id: str
    name: str
    description: str
    usage: Literal['R', 'S', 'N']
    max_use: int = Field(validation_alias=AliasChoices("max_use", "maxUse"), default=1)
    elements: List[BaseElement]
    # --- UPDATE: Add the rules field to the segment definition ---
    rules: Optional[List[SyntaxRule]] = None

# --- The rest of the models are unchanged ---
# ... (ContextualDefinition, StructureSegment, StructureLoop, etc.)
class ContextualDefinition(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    elements: Optional[Dict[str, Any]] = None

class StructureSegment(BaseModel):
    type: Literal['segment']
    xid: str
    name: str 
    usage: str
    max_use: int
    segmentDefinitionId: str
    contextDefinitionId: Optional[str] = None

class StructureLoop(BaseModel):
    type: Literal['loop']
    xid: str
    name: str
    usage: str
    repeat: Union[str, int]
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
        pass

# Rebuild models to resolve forward references.
BaseElement.model_rebuild()
StructureLoop.model_rebuild()