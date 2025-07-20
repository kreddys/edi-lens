# FILE: backend/tests/agents/test_agent_crews_integration.py
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
    if not (os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENROUTER_API_KEY") or os.getenv("GROQ_API_KEY")):
        pytest.skip("Skipping agent tests: No LLM API key found in .env.test")

@pytest.fixture
def get_crews_with_mocked_rag(monkeypatch):
    def _get_crews(guide_text_for_rag: str):
        mock_run = MagicMock(return_value=guide_text_for_rag)
        monkeypatch.setattr(KnowledgeBaseTool, "_run", mock_run)
        return SchemaEnrichmentCrews()
    return _get_crews

# --- Basic Test Cases (Updated with Correct Data) ---

def test_enrichment_crew_modifies_element(check_llm_api_keys, get_crews_with_mocked_rag):
    guide_text = "The CLM-02, Total Claim Charge, is Required."
    # --- THIS IS THE FIX ---
    # Provide a complete object, including the name. Now the ONLY error for the
    # agent to fix is the `usage` field, making the test unambiguous.
    base_clm_def = {"elements": [{"xid": "CLM02", "name": "Total Claim Charge", "usage": "S"}]}
    # --- END OF FIX ---
    crews = get_crews_with_mocked_rag(guide_text)
    enrichment_crew = crews.element_enrichment_crew()
    enrichment_inputs = {"segment_id": "CLM", "current_definition_json": json.dumps(base_clm_def)}

    result = trace_crew(enrichment_crew, enrichment_inputs)
    
    assert result.raw is not None
    json_output = extract_json_from_llm_output(result.raw)
    assert json_output, f"Could not extract JSON from agent output: {result.raw}"
    response = UniversalAgentResponse.model_validate_json(json_output)
    
    proposal = response.element_enrichment
    assert proposal is not None and len(proposal.patches) == 1
    assert proposal.patches[0].op == "replace"
    assert proposal.patches[0].path == "/elements/0/usage"
    assert proposal.patches[0].value == "R"


def test_enrichment_crew_adds_missing_element(check_llm_api_keys, get_crews_with_mocked_rag):
    guide_text = "The CLM segment includes CLM09 Release of Information, which is Situational."
    base_clm_def = {"elements": []}
    crews = get_crews_with_mocked_rag(guide_text)
    enrichment_crew = crews.element_enrichment_crew()
    enrichment_inputs = {
        "segment_id": "CLM",
        "current_definition_json": json.dumps(base_clm_def),
    }

    result = trace_crew(enrichment_crew, enrichment_inputs)
    
    assert result.raw is not None
    json_output = extract_json_from_llm_output(result.raw)
    assert json_output, f"Could not extract JSON from agent output: {result.raw}"
    response = UniversalAgentResponse.model_validate_json(json_output)
    
    proposal = response.element_enrichment
    assert proposal is not None

    add_patch = next((p for p in proposal.patches if p.op == "add"), None)
    assert add_patch is not None
    assert add_patch.path == "/elements/0"
    assert add_patch.value["xid"] == "CLM09"
    assert add_patch.value["usage"] == "S"
    assert "Release of Information" in add_patch.value["name"]


def test_enrichment_crew_returns_empty_patch_for_correct_segment(check_llm_api_keys, get_crews_with_mocked_rag):
    # --- THIS IS THE FIX ---
    # Make the guide text and the definition perfectly matched and complete.
    # This removes any ambiguity that might tempt the agent to hallucinate a `name`.
    guide_text = "The CLM-02, Total Claim Charge, is Required."
    correct_clm_def = {"elements": [{"xid": "CLM02", "name": "Total Claim Charge", "usage": "R"}]}
    # --- END OF FIX ---
    crews = get_crews_with_mocked_rag(guide_text)
    enrichment_crew = crews.element_enrichment_crew()
    enrichment_inputs = {
        "segment_id": "CLM",
        "current_definition_json": json.dumps(correct_clm_def),
    }
    
    result = trace_crew(enrichment_crew, enrichment_inputs)
    
    assert result.raw is not None
    json_output = extract_json_from_llm_output(result.raw)
    assert json_output, f"Could not extract JSON from agent output: {result.raw}"
    response = UniversalAgentResponse.model_validate_json(json_output)
    
    proposal = response.element_enrichment
    assert proposal is not None and len(proposal.patches) == 0


def test_rule_extraction_crew_extracts_conditional_rule(check_llm_api_keys, get_crews_with_mocked_rag):
    guide_text = "When the REF01 element is 'G2', then the REF02 element is required."
    crews = get_crews_with_mocked_rag(guide_text)
    rule_crew = crews.complex_rule_extraction_crew()
    rule_inputs = {
        "guide_text_chunk": guide_text
    }
    
    result = trace_crew(rule_crew, rule_inputs)
    
    assert result.raw is not None
    json_output = extract_json_from_llm_output(result.raw)
    assert json_output, f"Could not extract JSON from agent output: {result.raw}"
    response = UniversalAgentResponse.model_validate_json(json_output)
    
    proposal = response.complex_rules
    assert proposal is not None
    
    assert len(proposal.rules) == 1
    rule = proposal.rules[0]
    assert rule.conditions.expressions[0].field == "REF01"
    assert rule.action.type == "REQUIRE_ELEMENT"