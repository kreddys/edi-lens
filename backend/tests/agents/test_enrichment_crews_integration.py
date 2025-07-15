# FILE: backend/tests/agents/test_enrichment_crews_integration.py
import pytest
import os
import json
import logging
from pathlib import Path
import time

from src.agents.crews import SchemaEnrichmentCrews, ChangeProposal
from src.agents.refinement_engine.rag_tool import RAGTool
from src.agents.refinement_engine.models import KnowledgeSource
from src.agents.refinement_engine.embedding_models import PineconeEmbeddingModel
from src.core.config import settings
from scripts.preprocess_guide import preprocess_guide

# Mark all tests in this file as integration tests
pytestmark = pytest.mark.integration
logger = logging.getLogger(__name__)

# --- Test Data and Fixtures ---

@pytest.fixture(scope="module")
def setup_prerequisites():
    """A module-scoped fixture to check for API keys once per test run."""
    if not settings.PINECONE_API_KEY:
        pytest.skip("Skipping agent tests: PINECONE_API_KEY not found in environment.")
    if not (os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY") or os.getenv("OLLAMA_BASE_URL")):
        pytest.skip("Skipping agent tests: No LLM API key or OLLAMA_BASE_URL found.")

def get_crews_for_guide_text(guide_text: str, tmp_path_factory) -> SchemaEnrichmentCrews:
    """Helper function to create a crew setup for a given piece of guide text."""
    # Use a unique temp path for each test function to avoid conflicts
    tmp_path = tmp_path_factory.mktemp("guide_data")
    
    guide_path = tmp_path / "guide.txt"
    guide_path.write_text(guide_text)
    chunk_dir, _ = preprocess_guide(guide_path)
    
    embedding_model = PineconeEmbeddingModel(model_name=settings.PINECONE_EMBED_MODEL)
    knowledge = KnowledgeSource(source_type="directory", content=str(chunk_dir))
    rag_tool = RAGTool(knowledge_source=knowledge, embedding_model=embedding_model)
    
    return SchemaEnrichmentCrews(rag_tool=rag_tool)

# --- Test Cases ---

def test_analyst_crew_proposes_modify_and_add(setup_prerequisites, tmp_path_factory):
    """
    Tests that the analysis crew can correctly identify both a missing element
    and an element with an incorrect property in the same segment.
    """
    # Arrange
    guide_text = """
    CLM Claim Information
    To specify basic data about the claim.

    CLM-02 Total Claim Charge Amount
    Required
    Decimal number (R)

    CLM-09 Release of Information Code
    Required
    Identifier (ID)
    """
    base_clm_def = {
      "name": "Claim Information", "elements": [
        {"xid": "CLM01", "name": "Patient Control Number", "usage": "R"},
        {"xid": "CLM02", "name": "Total Claim Charge", "usage": "S"} # Incorrect
      ]
    }
    crews = get_crews_for_guide_text(guide_text, tmp_path_factory)
    analysis_crew = crews.analysis_crew()

    # Act
    result = analysis_crew.kickoff(inputs={
        "segment_id": "CLM", "current_definition_json": json.dumps(base_clm_def)
    })
    logger.info(f"Analyst Agent (Modify/Add Test) raw output:\n{result}")
    proposed_tasks = json.loads(result.raw)

    # Assert
    assert isinstance(proposed_tasks["proposals"], list)
    assert len(proposed_tasks["proposals"]) == 2
    
    modify_task = next((t for t in proposed_tasks["proposals"] if t["change_type"] == "MODIFY_ELEMENT"), None)
    assert modify_task and modify_task["element_id"] == "CLM02"
    assert modify_task["proposed_changes"]["usage"] == "R"
    
    add_task = next((t for t in proposed_tasks["proposals"] if t["change_type"] == "ADD_ELEMENT"), None)
    assert add_task and add_task["element_id"] == "CLM09"
    assert add_task["proposed_changes"]["xid"] == "CLM09"


def test_analyst_crew_proposes_multiple_adds(setup_prerequisites, tmp_path_factory):
    """
    Tests that the crew can identify and propose adding multiple missing elements
    to a sparse segment definition.
    """
    # Arrange
    guide_text = """
    SBR Subscriber Information
    To record information specific to the primary insured.

    SBR-01 Payer Responsibility Sequence Number Code
    Required
    Identifier (ID)

    SBR-02 Individual Relationship Code
    Optional
    Identifier (ID)

    SBR-09 Claim Filing Indicator Code
    Required
    Identifier (ID)
    """
    base_sbr_def = { "name": "Subscriber Information", "elements": [] } # Start with an empty segment
    crews = get_crews_for_guide_text(guide_text, tmp_path_factory)
    analysis_crew = crews.analysis_crew()

    # Act
    result = analysis_crew.kickoff(inputs={
        "segment_id": "SBR", "current_definition_json": json.dumps(base_sbr_def)
    })
    logger.info(f"Analyst Agent (Multiple Adds Test) raw output:\n{result}")
    proposed_tasks = json.loads(result.raw)

    # Assert
    assert isinstance(proposed_tasks["proposals"], list)
    assert len(proposed_tasks["proposals"]) == 3, "Expected proposals to add three missing elements."
    element_ids_to_add = {t["element_id"] for t in proposed_tasks["proposals"]}
    assert element_ids_to_add == {"SBR01", "SBR02", "SBR09"}
    
    sbr01_task = next(t for t in proposed_tasks["proposals"] if t["element_id"] == "SBR01")
    assert sbr01_task["proposed_changes"]["usage"] == "R"
    
    sbr02_task = next(t for t in proposed_tasks["proposals"] if t["element_id"] == "SBR02")
    assert sbr02_task["proposed_changes"]["usage"] == "S" # Checks if it correctly parsed "Optional"

def test_analyst_crew_proposes_no_changes_for_correct_segment(setup_prerequisites, tmp_path_factory):
    """
    Tests the critical case where the segment definition already matches the guide,
    ensuring the agent correctly returns an empty list.
    """
    # Arrange
    guide_text = """
    ST Transaction Set Header
    To indicate the start of a transaction set.

    ST-01 Transaction Set Identifier Code
    Required
    Identifier (ID)
    """
    # This definition perfectly matches the guide text above.
    correct_st_def = {
      "name": "Transaction Set Header",
      "elements": [{"xid": "ST01", "name": "Transaction Set Identifier Code", "usage": "R"}]
    }
    crews = get_crews_for_guide_text(guide_text, tmp_path_factory)
    analysis_crew = crews.analysis_crew()

    # Act
    result = analysis_crew.kickoff(inputs={
        "segment_id": "ST", "current_definition_json": json.dumps(correct_st_def)
    })
    logger.info(f"Analyst Agent (No Change Test) raw output:\n{result}")
    proposed_tasks = json.loads(result.raw)

    # Assert
    assert isinstance(proposed_tasks["proposals"], list)
    assert len(proposed_tasks["proposals"]) == 0, "Agent should have proposed zero changes for a correct segment."