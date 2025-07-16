# FILE: backend/src/agents/refinement_engine/models.py
from pydantic import BaseModel, Field
from typing import Literal, Optional, Any, List, Dict

# --- Input/Output Models for Agents ---

class KnowledgeSource(BaseModel):
    """Defines the source of knowledge for the refinement."""
    source_type: Literal["file", "text", "directory"]
    content: str

# --- Agent 1: Structural Integrity ---
class StructuralChange(BaseModel):
    """A proposal to add a missing loop or segment to the schema's structure."""
    type: Literal["loop", "segment"]
    xid: str
    name: str
    parentLoopId: str
    # Could add 'insertBefore' or 'insertAfter' for precise positioning

class StructuralChangeProposal(BaseModel):
    """The final output of the Structural Integrity Agent."""
    changes: List[StructuralChange] = Field(default_factory=list)

# --- Agent 2: Contextualization ---
class ContextualLink(BaseModel):
    """A proposal to create a contextual link for a specific segment usage."""
    loopId: str
    segmentId: str
    contextId: str # e.g., "2010AA.NM1"

class ContextualLinkProposal(BaseModel):
    """The final output of the Contextualization Agent."""
    links: List[ContextualLink] = Field(default_factory=list)

# --- Agent 3: Element Enrichment ---
class ElementEnrichment(BaseModel):
    """A JSON Patch operation to enrich a segment definition."""
    op: Literal["add", "replace", "remove"]
    path: str
    value: Optional[Any] = None

class ElementEnrichmentProposal(BaseModel):
    """The final output of the Element Enrichment Agent."""
    patches: List[ElementEnrichment] = Field(default_factory=list)

# --- Agent 4: Complex Rule Extraction ---
class RuleExpression(BaseModel):
    """A single condition, e.g., 'field CLM05-03 equals 7'."""
    field: str
    operator: Literal["equals", "not_equals", "in", "not_in", "is_present", "is_not_present"]
    value: Any

class RuleCondition(BaseModel):
    """A block of conditions, combined with AND or OR."""
    logicalOperator: Literal["AND", "OR"]
    expressions: List[RuleExpression]

class RuleAction(BaseModel):
    """The action to take if the conditions are met."""
    type: Literal["REQUIRE_SEGMENT", "PROHIBIT_SEGMENT", "REQUIRE_PAIRED_ELEMENTS", "FIELD_EQUALS_FIELD"]
    target: Optional[Dict[str, Any]] = None
    elements: Optional[List[str]] = None
    source: Optional[Dict[str, Any]] = None

class ComplexRule(BaseModel):
    """A single, structured complex validation rule."""
    ruleId: str
    description: str
    citation: str
    appliesTo: Dict[str, str] # e.g., {"loop": "2300"} or {"segment": "PER"}
    conditions: RuleCondition
    action: RuleAction

class ComplexRuleProposal(BaseModel):
    """The final output of the Complex Rule Extraction Agent."""
    rules: List[ComplexRule] = Field(default_factory=list)

# --- Status Model for the Engine ---
class RefinementStatus(BaseModel):
    """A structured status update yielded by the engine during its run."""
    phase: Literal["Initializing", "Structural Integrity", "Contextualization", "Element Enrichment", "Rule Extraction", "Complete", "Failed"]
    message: str
    progress: float = 0.0
    details: Optional[Dict[str, Any]] = None