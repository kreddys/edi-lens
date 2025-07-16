# FILE: backend/tests/agents/test_enrichment_crews_integration.py
import pytest
import os
import json
import logging
import inspect
import asyncio
import litellm
from unittest.mock import MagicMock, AsyncMock

from src.utils.telemetry import trace_crew
from src.utils.llm_output_parser import extract_json_from_llm_output
from src.agents.crews import SchemaEnrichmentCrews
from src.agents.rag_pipeline.graph_rag_tool import GraphRAGTool
from src.core.config import settings

pytestmark = pytest.mark.integration
logger = logging.getLogger(__name__)

# --- Fixtures ---

@pytest.fixture(autouse=True)
def patch_litellm_completion(monkeypatch):
    """Patches litellm.completion to add a debug callback if AGENT_VERBOSE is set."""
    original_completion = litellm.completion
    is_verbose = os.getenv('AGENT_VERBOSE', 'false').lower() == 'true'

    if not is_verbose:
        yield
        return

    def llm_debug_callback(kwargs, completion_response, start_time, end_time):
        print("\n" + "="*20 + " LLM DEBUG " + "="*20)
        try:
            print("\n--- LLM Request ---")
            request_data = {"model": kwargs.get("model"), "messages": kwargs.get("messages")}
            print(json.dumps(request_data, indent=2))
            print("\n--- LLM Response ---")
            if hasattr(completion_response, 'model_dump_json'):
                print(completion_response.model_dump_json(indent=2))
            else:
                print(str(completion_response))
        except Exception as e:
            print(f"\nError in llm_debug_callback: {e}")
        finally:
            print("\n" + "="*51 + "\n")

    def wrapped_completion(*args, **kwargs):
        existing_callbacks = kwargs.get("success_callback", [])
        if not isinstance(existing_callbacks, list):
            existing_callbacks = [existing_callbacks]
        if llm_debug_callback not in existing_callbacks:
            existing_callbacks.append(llm_debug_callback)
        kwargs["success_callback"] = existing_callbacks
        return original_completion(*args, **kwargs)

    monkeypatch.setattr(litellm, "completion", wrapped_completion)
    logger.info("LLM debug logging enabled via monkeypatch.")
    yield
    logger.info("LLM debug logging disabled.")


@pytest.fixture(scope="module")
def setup_prerequisites():
    """Checks for necessary API keys before running the test module."""
    if not settings.PINECONE_API_KEY:
        pytest.skip("Skipping agent tests: PINECONE_API_KEY not found in environment.")
    if not (os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY") or os.getenv("GROQ_API_KEY") or os.getenv("OLLAMA_BASE_URL")):
        pytest.skip("Skipping agent tests: No LLM API key or OLLAMA_BASE_URL found.")


# --- THIS IS THE CORRECTED HELPER FUNCTION ---
@pytest.fixture
def get_crews_for_guide_text(monkeypatch):
    """
    A factory fixture to create a SchemaEnrichmentCrews instance with a mocked GraphRAGTool.
    This prevents the tests from needing a live database connection for the knowledge base.
    """
    def _get_crews(guide_text_for_rag: str):
        # Create a mock for the async run method of the tool
        mock_run_async = AsyncMock(return_value=guide_text_for_rag)
        
        # Patch the _run_async method on the GraphRAGTool class
        monkeypatch.setattr(GraphRAGTool, "_run_async", mock_run_async)

        # Now, when SchemaEnrichmentCrews initializes its GraphRAGTool,
        # the tool's run method will be our mock, so it won't hit the DB.
        return SchemaEnrichmentCrews()

    return _get_crews
# --- END OF CORRECTION ---


# --- Test Cases ---

def test_enrichment_crew_modifies_element(setup_prerequisites, get_crews_for_guide_text):
    """
    Tests the agent's ability to generate a 'replace' patch for an existing,
    incorrect element property.
    """
    # Arrange
    guide_text = "The CLM segment defines claim information. CLM-02, Total Claim Charge, is Required."
    base_clm_def = {"name": "Claim Information", "elements": [{"xid": "CLM02", "name": "Total Claim Charge", "usage": "S"}]}
    
    # Use the factory to get a crew instance with the RAG tool mocked to return our guide_text
    crews = get_crews_for_guide_text(guide_text)
    
    enrichment_crew = crews.element_enrichment_crew()
    enrichment_inputs = {"segment_id": "CLM", "context_id": None, "current_definition_json": json.dumps(base_clm_def)}

    # Act
    result = trace_crew(enrichment_crew, enrichment_inputs)
    
    # Debug & Parse
    logger.info(f"--- DEBUG OUTPUT FOR: {inspect.currentframe().f_code.co_name} ---")
    logger.info(f"Agent's raw output:\n{result.raw}")
    json_string = extract_json_from_llm_output(result.raw)
    logger.info(f"Extracted JSON:\n{json_string}")
    logger.info("--- END DEBUG ---")
    
    # Assert
    assert json_string, "The LLM did not return a valid JSON block."
    patch_data = json.loads(json_string)
    patches = patch_data.get("patches", patch_data)

    assert isinstance(patches, list)
    assert len(patches) > 0, "Expected at least one patch operation, but got none."
    replace_patch = next((p for p in patches if p.get("op") == "replace"), None)
    assert replace_patch is not None, "A 'replace' operation was expected in the patch."
    assert replace_patch["path"] == "/elements/0/usage"
    assert replace_patch["value"] == "R"


def test_enrichment_crew_adds_missing_element(setup_prerequisites, get_crews_for_guide_text):
    """
    Tests the agent's ability to generate an 'add' patch for a missing element.
    """
    # Arrange
    guide_text = """
    The CLM segment is for claim data.
    - CLM01 Patient Control Number is Required.
    - CLM02 Total Claim Charge is Required.
    - CLM09 Release of Information Code is Situational. This indicates if the provider has authorization to release medical info.
    """
    base_clm_def = {
        "name": "Claim Information",
        "elements": [
            {"xid": "CLM01", "name": "Patient Control Number", "usage": "R"},
            {"xid": "CLM02", "name": "Total Claim Charge", "usage": "R"}
        ]
    }
    
    crews = get_crews_for_guide_text(guide_text)
    enrichment_crew = crews.element_enrichment_crew()
    enrichment_inputs = {"segment_id": "CLM", "context_id": None, "current_definition_json": json.dumps(base_clm_def)}

    # Act
    result = trace_crew(enrichment_crew, enrichment_inputs)

    # Debug & Parse
    logger.info(f"--- DEBUG OUTPUT FOR: {inspect.currentframe().f_code.co_name} ---")
    logger.info(f"Agent's raw output:\n{result.raw}")
    json_string = extract_json_from_llm_output(result.raw)
    logger.info(f"Extracted JSON:\n{json_string}")
    logger.info("--- END DEBUG ---")

    # Assert
    assert json_string, "The LLM did not return a valid JSON block."
    patch_data = json.loads(json_string)
    patches = patch_data.get("patches", patch_data)
    
    assert isinstance(patches, list)
    assert len(patches) > 0, "Expected at least one patch operation, but got none."
    add_patch = next((p for p in patches if p.get("op") == "add" and "CLM09" in str(p.get("value"))), None)
    assert add_patch is not None, "An 'add' operation for CLM09 was expected."
    assert add_patch["path"] == "/elements/2"
    assert add_patch["value"]["xid"] == "CLM09"
    assert add_patch["value"]["usage"] == "S"


def test_enrichment_crew_returns_empty_patch_for_correct_segment(setup_prerequisites, get_crews_for_guide_text):
    """
    Tests the critical case where the agent correctly identifies that no changes
    are needed and returns an empty patch list.
    """
    # Arrange
    guide_text = "The CLM-02 element is Required."
    correct_clm_def = {"name": "Claim Information", "elements": [{"xid": "CLM02", "name": "Total Claim Charge", "usage": "R"}]}
    
    crews = get_crews_for_guide_text(guide_text)
    enrichment_crew = crews.element_enrichment_crew()
    enrichment_inputs = {"segment_id": "CLM", "context_id": None, "current_definition_json": json.dumps(correct_clm_def)}
    
    # Act
    result = trace_crew(enrichment_crew, enrichment_inputs)

    # Debug & Parse
    logger.info(f"--- DEBUG OUTPUT FOR: {inspect.currentframe().f_code.co_name} ---")
    logger.info(f"Agent's raw output:\n{result.raw}")
    json_string = extract_json_from_llm_output(result.raw)
    logger.info(f"Extracted JSON:\n{json_string}")
    logger.info("--- END DEBUG ---")

    # Assert
    assert json_string, "The LLM did not return a valid JSON block."
    patch_data = json.loads(json_string)
    patches = patch_data.get("patches", [])
    
    assert isinstance(patches, list)
    assert len(patches) == 0, "Expected an empty patch list for a correct segment."


def test_rule_extraction_crew_extracts_conditional_rule(setup_prerequisites, get_crews_for_guide_text):
    """
    Tests that the rule extraction agent can correctly parse a conditional
    rule from text into the structured `ComplexRule` format.
    """
    # Arrange
    guide_text = "When the REF01 element contains the code 'G2', then the REF02 element is required."
    
    crews = get_crews_for_guide_text(guide_text)
    rule_crew = crews.complex_rule_extraction_crew()
    rule_inputs = {"guide_text_chunk": guide_text}
    
    # Act
    result = trace_crew(rule_crew, rule_inputs)
    
    # Debug & Parse
    logger.info(f"--- DEBUG OUTPUT FOR: {inspect.currentframe().f_code.co_name} ---")
    logger.info(f"Agent's raw output:\n{result.raw}")
    json_string = extract_json_from_llm_output(result.raw)
    logger.info(f"Extracted JSON:\n{json_string}")
    logger.info("--- END DEBUG ---")

    # Assert
    assert json_string, "The LLM did not return a valid JSON block."
    proposal = json.loads(json_string)
    
    assert "rules" in proposal
    assert isinstance(proposal["rules"], list)
    assert len(proposal["rules"]) == 1, "Expected exactly one rule to be extracted."
    
    rule = proposal["rules"][0]
    assert "REF" in rule["ruleId"]
    assert rule["appliesTo"]["segment"] == "REF"
    
    condition = rule["conditions"]
    assert condition["expressions"][0]["field"] == "REF01"
    assert condition["expressions"][0]["operator"] == "equals"
    assert condition["expressions"][0]["value"] == "G2"

    action = rule["action"]
    assert "REQUIRE" in action["type"]
    assert "REF02" in str(action)