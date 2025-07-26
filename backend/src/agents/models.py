# FILE: backend/src/agents/models.py
from pydantic import BaseModel, Field, ConfigDict
from typing import Literal, Optional, Any, List, Dict

class AuditResponse(BaseModel):
    """The structured response from the Auditor Agent."""
    approved: bool = Field(..., description="Whether the proposal is approved or rejected.")
    # Renaming 'justification' to 'reasoning' for consistency with other models
    reasoning: str = Field(..., description="A clear explanation for the approval or rejection decision.")

class ElementEnrichment(BaseModel):
    """A JSON Patch operation to enrich a segment definition."""
    op: Literal["add", "replace", "remove"]
    path: str
    value: Optional[Any] = None
    model_config = ConfigDict(extra="ignore")

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
    type: Literal["REQUIRE_ELEMENT", "PROHIBIT_SEGMENT"] = Field(..., description="The type of validation action to perform.")
    details: Dict[str, Any] = Field(..., description="A dictionary containing details for the action, e.g., {'element': 'REF02'}.")

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
    """The final list of extracted complex rules."""
    rules: List[ComplexRule] = Field(default_factory=list, description="A list of all complex rules extracted from the text.")

class UniversalAgentResponse(BaseModel):
    """
    A standardized response schema for agents that propose changes.
    """
    reasoning: str = Field(..., description="A step-by-step explanation of the agent's thought process, outlining how it reached its conclusion and generated the final data.")
    patches: List[ElementEnrichment] = Field(default_factory=list, description="A list of JSON Patch operations. This can be an empty list if no changes are needed.")
    complex_rules: Optional[ComplexRuleProposal] = Field(None, description="The final list of extracted complex rules.")