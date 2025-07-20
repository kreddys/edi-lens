# FILE: backend/tests/agents/test_agent_crews_complex_integration.py
import pytest
import os
import json
import logging
from unittest.mock import MagicMock

from src.utils.telemetry import trace_crew
from src.utils.llm_output_parser import extract_json_from_llm_output
from src.agents.tools.rag import KnowledgeBaseTool
from src.agents.crews import SchemaEnrichmentCrews
from src.agents.models import UniversalAgentResponse

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]
logger = logging.getLogger(__name__)

# --- Reusable Fixtures ---

@pytest.fixture(scope="module", autouse=True)
def check_llm_api_keys():
    """Skips this entire test module if no LLM API key is configured."""
    if not (os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENROUTER_API_KEY") or os.getenv("GROQ_API_KEY")):
        pytest.skip("Skipping agent tests: No LLM API key found in .env.test")


@pytest.fixture
def get_crews_with_mocked_rag(monkeypatch):
    """Mocks the KnowledgeBaseTool to return a predefined string."""
    def _get_crews(guide_text_for_rag: str):
        mock_run = MagicMock(return_value=guide_text_for_rag)
        monkeypatch.setattr(KnowledgeBaseTool, "_run", mock_run)
        return SchemaEnrichmentCrews()
    return _get_crews


# --- New, More Complex Test Cases ---

def test_enrichment_crew_handles_multiple_operations(check_llm_api_keys, get_crews_with_mocked_rag):
    """
    Tests that the agent can generate both a 'replace' and an 'add' patch
    from a single, more complex piece of guide text.
    """
    # Arrange
    guide_text = """
    For the CLM segment, the Total Claim Charge (CLM02) is a mandatory field.
    Additionally, the segment includes an optional element for Patient Signature Source (CLM08).
    """
    # Provide a complete and unambiguous starting definition.
    base_clm_def = {
        "elements": [
            {"xid": "CLM01", "name": "Patient Control Number", "usage": "R"},
            {"xid": "CLM02", "name": "Total Claim Charge", "usage": "S"}
        ]
    }
    
    crews = get_crews_with_mocked_rag(guide_text)
    enrichment_crew = crews.element_enrichment_crew()
    enrichment_inputs = {"segment_id": "CLM", "current_definition_json": json.dumps(base_clm_def)}

    # Act
    result = trace_crew(enrichment_crew, enrichment_inputs)
    
    # Assert
    assert result.raw is not None, "Agent crew returned a null raw result."
    json_output = extract_json_from_llm_output(result.raw)
    assert json_output, f"Could not extract JSON from agent output: {result.raw}"
    response = UniversalAgentResponse.model_validate_json(json_output)
    
    proposal = response.element_enrichment
    assert proposal is not None
    patches = proposal.patches
    
    assert isinstance(patches, list) and len(patches) == 2, "Expected exactly two patch operations."

    # Verify the 'replace' operation for CLM02
    replace_patch = next((p for p in patches if p.op == "replace" and p.path == "/elements/1/usage"), None)
    assert replace_patch is not None, "A 'replace' operation for CLM02 usage was expected."
    assert replace_patch.value == "R"

    # Verify the 'add' operation for CLM08
    add_patch = next((p for p in patches if p.op == "add"), None)
    assert add_patch is not None, "An 'add' operation for CLM08 was expected."
    assert add_patch.path == "/elements/2"
    assert add_patch.value["xid"] == "CLM08"
    assert add_patch.value["usage"] == "S"


def test_rule_extraction_crew_handles_multi_condition_rule(check_llm_api_keys, get_crews_with_mocked_rag):
    """
    Tests that the agent can correctly parse a rule that has multiple 'AND' conditions.
    """
    # Arrange
    guide_text = """
    A situational rule for the DTP segment: If DTP01 is '472' for Service Date
    AND DTP02 is 'D8' for date format, then DTP03 must contain a valid date.
    """
    
    crews = get_crews_with_mocked_rag(guide_text)
    rule_crew = crews.complex_rule_extraction_crew()
    rule_inputs = {"guide_text_chunk": guide_text}
    
    # Act
    result = trace_crew(rule_crew, rule_inputs)
    
    # Assert
    assert result.raw is not None, "Agent crew returned a null raw result."
    json_output = extract_json_from_llm_output(result.raw)
    assert json_output, f"Could not extract JSON from agent output: {result.raw}"
    response = UniversalAgentResponse.model_validate_json(json_output)
    
    proposal = response.complex_rules
    assert proposal is not None
    assert isinstance(proposal.rules, list) and len(proposal.rules) == 1
    
    rule = proposal.rules[0]
    assert rule.appliesTo["segment"] == "DTP"
    
    conditions = rule.conditions
    assert conditions.logicalOperator == "AND" and len(conditions.expressions) == 2
    
    exp1 = next((e for e in conditions.expressions if e.field == "DTP01"), None)
    assert exp1 is not None and exp1.value == "472"
    
    exp2 = next((e for e in conditions.expressions if e.field == "DTP02"), None)
    assert exp2 is not None and exp2.value == "D8"
    
    action = rule.action
    assert action.type == "REQUIRE_ELEMENT" and action.details == {"element": "DTP03"}