# FILE: backend/src/agents/models.py
from pydantic import BaseModel, Field
from typing import Literal, Optional, Any, List, Dict

# --- Model for Element Enrichment Agent ---
class ElementEnrichment(BaseModel):
    """A JSON Patch operation to enrich a segment definition."""
    op: Literal["add", "replace", "remove"]
    path: str
    value: Optional[Any] = None

class ElementEnrichmentProposal(BaseModel):
    """The final output of the Element Enrichment Agent."""
    patches: List[ElementEnrichment] = Field(default_factory=list)

# --- Models for Complex Rule Extraction Agent ---
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