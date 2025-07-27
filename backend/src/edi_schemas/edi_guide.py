# FILE: backend/src/edi_schemas/edi_guide.py
from pydantic import BaseModel, Field, AliasChoices
from typing import List, Optional, Union, Dict, Any, Literal, Annotated

# --- Models for Structured Syntax Rules ---
class ConditionClause(BaseModel):
    element: str
    operator: Literal["IS", "IS_NOT", "IS_PRESENT", "IS_NOT_PRESENT"]
    value: Optional[Any] = None

class Conditions(BaseModel):
    ALL_OF: Optional[List[ConditionClause]] = Field(None, description="All conditions must be true (AND).")
    ANY_OF: Optional[List[ConditionClause]] = Field(None, description="Any condition can be true (OR).")

class AssertionClause(BaseModel):
    # --- FIX #2a: Add 'elements' field and make 'element'/'value' optional ---
    element: Optional[str] = None 
    elements: Optional[List[str]] = None
    # --- FIX #2b: Add the new assertion type ---
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
    sub_elements: Optional[List['BaseElement']] = Field(default=None, alias="elements")

class SegmentDefinition(BaseModel):
    id: str
    name: str
    description: str
    usage: Literal['R', 'S', 'N']
    max_use: int = Field(validation_alias=AliasChoices("max_use", "maxUse"), default=1)
    elements: List[BaseElement]
    rules: Optional[List[SyntaxRule]] = None

# --- Models for Contextual Overrides ---
class NestedElementOverride(BaseModel):
    usage: Optional[Literal['R', 'S', 'N']] = None
    valid_codes: Optional[List[CodeDefinition]] = None
    name: Optional[str] = None
    description: Optional[str] = None

class ContextualElementOverride(BaseModel):
    usage: Optional[Literal['R', 'S', 'N']] = None
    name: Optional[str] = None
    description: Optional[str] = None
    dataType: Optional[Literal['ID', 'AN', 'DT', 'TM', 'N0', 'N1', 'N2', 'R', 'Composite']] = None
    minLength: Optional[int] = None
    maxLength: Optional[int] = None
    format: Optional[Union[str, List[str]]] = None
    valid_codes: Optional[List[CodeDefinition]] = None
    sub_elements: Optional[Dict[str, NestedElementOverride]] = None

class ContextualDefinition(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    # --- FIX #1: Make elements optional to handle simple naming contexts ---
    elements: Optional[Dict[str, ContextualElementOverride]] = None

# --- Models for Hierarchical Structure ---
class StructureSegment(BaseModel):
    type: Literal['segment']
    xid: str
    name: str # Add name to the structure model for completeness
    usage: str
    max_use: int
    # --- FIX #3: Rename to match the JSON file ---
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
        # ... (this function is no longer needed by the review script but can be kept) ...
        pass

# Rebuild models to resolve forward references.
BaseElement.model_rebuild()
StructureLoop.model_rebuild()