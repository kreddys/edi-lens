# FILE: backend/src/agents/models.py
from pydantic import BaseModel, Field, ConfigDict
from typing import Literal, Optional, Any, List, Dict

# --- Model for Element Enrichment Agent (Unchanged) ---
class ElementEnrichment(BaseModel):
    op: Literal["add", "replace", "remove"]
    path: str
    value: Optional[Any] = None

class ElementEnrichmentProposal(BaseModel):
    patches: List[ElementEnrichment] = Field(default_factory=list)

# --- Models for Complex Rule Extraction Agent (REVISED) ---
class RuleExpression(BaseModel):
    """A single condition, e.g., 'field CLM05-03 equals 7'."""
    field: str = Field(..., description="The element ID to check, e.g., 'REF01'.")
    operator: Literal["equals", "not_equals", "in", "not_in", "is_present", "is_not_present"]
    value: Any

class RuleCondition(BaseModel):
    """A block of conditions, combined with AND or OR."""
    logicalOperator: Literal["AND", "OR"]
    expressions: List[RuleExpression]

class RuleAction(BaseModel):
    """The action to take if the conditions are met."""
    # --- THIS IS THE FIX ---
    # We are simplifying the action types. This is easier for the LLM to choose from
    # and reduces ambiguity. We can map these to more complex logic in our engine later.
    type: Literal["REQUIRE_ELEMENT", "PROHIBIT_SEGMENT"] = Field(..., description="The type of validation action to perform.")
    details: Dict[str, Any] = Field(..., description="A dictionary containing details for the action, e.g., {'element': 'REF02'}.")
    # --- END OF FIX ---

class ComplexRule(BaseModel):
    """A single, structured complex validation rule found in the guide."""
    ruleId: str = Field(..., description="A unique identifier for the rule, e.g., 'REF_G2_Requirement'.")
    description: str = Field(..., description="A clear, human-readable description of the rule.")
    citation: str = Field(..., description="A reference to where this rule is found in the guide.")
    appliesTo: Dict[str, str] = Field(..., description="Defines the scope of the rule, e.g., {'segment': 'REF'}.")
    conditions: RuleCondition
    action: RuleAction
    model_config = ConfigDict(extra="ignore")

class ComplexRuleProposal(BaseModel):
    """The final, validated output from the Complex Rule Extraction Agent."""
    rules: List[ComplexRule] = Field(default_factory=list, description="A list of all complex rules extracted from the text.")