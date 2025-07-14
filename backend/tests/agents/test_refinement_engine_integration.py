# FILE: backend/tests/agents/test_refinement_engine_integration.py
import pytest
import json
import os
import logging
from pathlib import Path

from src.agents.refinement_engine.engine import SchemaRefinementEngine
from src.agents.refinement_engine.models import KnowledgeSource
# --- NEW IMPORT ---
from src.core.schema_manager import schema_manager

# Mark this entire file as an 'integration' test
pytestmark = pytest.mark.integration
logger = logging.getLogger(__name__)

def test_engine_e2e_with_live_llm():
    """
    Integration test for the SchemaRefinementEngine using a live LLM call.
    """
    # Arrange: Check for prerequisite API key
    llm_api_key_found = (
        os.getenv("OPENROUTER_API_KEY") or
        os.getenv("OPENAI_API_KEY") or
        os.getenv("ANTHROPIC_API_KEY") or
        os.getenv("OLLAMA_BASE_URL")
    )
    if not llm_api_key_found:
        pytest.skip("Skipping live LLM test: No LLM API key or OLLAMA_BASE_URL found in environment.")

    # --- THIS IS THE FIX ---
    # Manually load schemas into the singleton manager so the tools can find them.
    # This simulates the app's startup process for the test.
    test_schema_dir = Path(__file__).parent.parent / "data" / "test_schemas"
    schema_manager.load_schemas(test_schema_dir)
    assert schema_manager.get_schema("005010X222A1") is not None, "Test schema failed to load."
    # --- END OF FIX ---

    # Arrange: Define a simple schema and a clear instruction
    base_schema = {
        "segmentDefinitions": {
            "CLM": {
                "name": "Claim Info",
                "elements": [
                    {"xid": "CLM01", "name": "Patient Control Number", "usage": "R"},
                    {"xid": "CLM02", "name": "Total Claim Charge", "usage": "S"}
                ]
            }
        }
    }
    
    instruction = "The Total Claim Charge element, which is CLM02 in the CLM segment, must be required."
    knowledge = KnowledgeSource(source_type="text", content=instruction)

    # Act: Run the engine and collect status updates
    engine = SchemaRefinementEngine(base_schema=base_schema, knowledge_source=knowledge)
    
    logger.info("--- Starting Live LLM Refinement Engine Test ---")
    status_updates = []
    for status in engine.run():
        logger.info(f"[{status.phase.upper():<9}] {status.message}")
        status_updates.append(status)

    # Assert: Verify the engine completed successfully and applied the correct change
    final_status = status_updates[-1]
    assert final_status.phase == "Complete", f"Engine failed with message: {final_status.message}"

    final_schema = engine.get_final_schema()
    
    clm_def = final_schema["segmentDefinitions"]["CLM"]
    clm02_element = clm_def["elements"][1]
    
    assert clm02_element["xid"] == "CLM02"
    assert clm02_element["usage"] == "R", "The LLM failed to change the usage of CLM02 to 'R'."

    logger.info("--- Live LLM Refinement Engine Test Passed ---")