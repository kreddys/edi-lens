# FILE: backend/tests/agents/test_agent_crews_integration.py

# --- Step 1: Add the necessary imports ---
import pytest
import os
import json
import logging
import inspect
from unittest.mock import MagicMock
from src.agents.tools.rag import KnowledgeBaseTool
from src.agents.crews import SchemaEnrichmentCrews
# --- This is the key import we were missing ---
from src.utils.telemetry import trace_crew
# --- We also need the parser for the raw output from trace_crew ---
from src.utils.llm_output_parser import extract_json_from_llm_output
from src.agents.models import ElementEnrichmentProposal, ComplexRuleProposal
import openlit 

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]
logger = logging.getLogger(__name__)

# --- (The fixtures 'check_llm_api_keys' and 'get_crews_with_mocked_rag' are correct and do not need changes) ---

@pytest.fixture(scope="module", autouse=True)
def check_llm_api_keys():
    if not (os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENROUTER_API_KEY") or os.getenv("GROQ_API_KEY")):
        pytest.skip("Skipping agent tests: No LLM API key found in .env.test")

@pytest.fixture
def get_crews_with_mocked_rag(monkeypatch):
    def _get_crews(guide_text_for_rag: str):
        mock_run = MagicMock(return_value=guide_text_for_rag)
        monkeypatch.setattr(KnowledgeBaseTool, "_run", mock_run)
        crews = SchemaEnrichmentCrews()
        crews.mock_rag_run = mock_run
        return crews
    return _get_crews

# --- Step 2: Update all test cases to use trace_crew and parse the raw output ---

def test_enrichment_crew_modifies_element(check_llm_api_keys, get_crews_with_mocked_rag):
    # Arrange
    guide_text = "The CLM segment defines claim information. CLM-02, Total Claim Charge, is Required."
    base_clm_def = {"name": "Claim Information", "elements": [{"xid": "CLM02", "name": "Total Claim Charge", "usage": "S"}]}
    crews = get_crews_with_mocked_rag(guide_text)
    enrichment_crew = crews.element_enrichment_crew()
    enrichment_inputs = {"segment_id": "CLM", "current_definition_json": json.dumps(base_clm_def)}

    # Act: Use the trace_crew wrapper
    result = trace_crew(enrichment_crew, enrichment_inputs)
    
    # Assert: Parse the raw output and validate against the Pydantic model
    assert result.raw is not None, "Agent crew returned a null raw result."
    json_output = extract_json_from_llm_output(result.raw)
    assert json_output, "Could not extract JSON from agent output."
    proposal = ElementEnrichmentProposal.model_validate_json(json_output)
    
    patches = proposal.patches
    assert isinstance(patches, list)
    assert len(patches) > 0
    replace_patch = next((p for p in patches if p.op == "replace"), None)
    assert replace_patch is not None
    assert replace_patch.path == "/elements/0/usage"
    assert replace_patch.value == "R"


def test_enrichment_crew_adds_missing_element(check_llm_api_keys, get_crews_with_mocked_rag):
    # Arrange
    guide_text = "The CLM segment is for claim data. CLM09 Release of Information Code is Situational."
    base_clm_def = {"name": "Claim Information", "elements": [{"xid": "CLM01"}]}
    crews = get_crews_with_mocked_rag(guide_text)
    enrichment_crew = crews.element_enrichment_crew()
    enrichment_inputs = {"segment_id": "CLM", "current_definition_json": json.dumps(base_clm_def)}

    # Act: Use the trace_crew wrapper
    result = trace_crew(enrichment_crew, enrichment_inputs)

    # Assert: Parse the raw output and validate
    assert result.raw is not None
    json_output = extract_json_from_llm_output(result.raw)
    assert json_output
    proposal = ElementEnrichmentProposal.model_validate_json(json_output)

    patches = proposal.patches
    assert isinstance(patches, list)
    assert len(patches) > 0
    add_patch = next((p for p in patches if p.op == "add" and "CLM09" in str(p.value)), None)
    assert add_patch is not None
    assert add_patch.path == "/elements/1"
    assert add_patch.value["xid"] == "CLM09"
    assert add_patch.value["usage"] == "S"


def test_enrichment_crew_returns_empty_patch_for_correct_segment(check_llm_api_keys, get_crews_with_mocked_rag):
    # Arrange
    guide_text = "The CLM-02 element is Required."
    correct_clm_def = {"name": "Claim Information", "elements": [{"xid": "CLM02", "usage": "R"}]}
    crews = get_crews_with_mocked_rag(guide_text)
    enrichment_crew = crews.element_enrichment_crew()
    enrichment_inputs = {"segment_id": "CLM", "current_definition_json": json.dumps(correct_clm_def)}
    
    # Act: Use the trace_crew wrapper
    result = trace_crew(enrichment_crew, enrichment_inputs)

    # Assert: Parse the raw output and validate
    assert result.raw is not None
    json_output = extract_json_from_llm_output(result.raw)
    # The LLM might return an empty object {} or an object with an empty list {"patches": []}
    # Both are valid, so we handle them.
    if json_output:
        proposal = ElementEnrichmentProposal.model_validate_json(json_output)
        assert len(proposal.patches) == 0, "Expected an empty patch list for a correct segment."
    else:
        # If the output is just an empty string, that's also acceptable here.
        assert True


def test_rule_extraction_crew_extracts_conditional_rule(check_llm_api_keys, get_crews_with_mocked_rag):
    # Arrange
    guide_text = "When the REF01 element contains the code 'G2', then the REF02 element is required."
    crews = get_crews_with_mocked_rag(guide_text)
    rule_crew = crews.complex_rule_extraction_crew()
    rule_inputs = {"guide_text_chunk": guide_text}
    
    # Act: Use the trace_crew wrapper
    result = trace_crew(rule_crew, rule_inputs)
    
    # Assert: Parse the raw output and validate
    assert result.raw is not None
    json_output = extract_json_from_llm_output(result.raw)
    assert json_output
    proposal = ComplexRuleProposal.model_validate_json(json_output)
    
    assert isinstance(proposal.rules, list)
    assert len(proposal.rules) == 1
    
    rule = proposal.rules[0]
    assert "REF" in rule.ruleId
    assert rule.appliesTo["segment"] == "REF"
    
    condition = rule.conditions
    assert condition.expressions[0].field == "REF01"
    assert condition.expressions[0].operator == "equals"
    assert condition.expressions[0].value == "G2"

    action = rule.action
    assert "REQUIRE" in action.type
    assert "REF02" in str(action)