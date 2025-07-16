# FILE: backend/tests/agents/test_agent_crews_integration.py
import pytest
import os
import json
import logging
from pathlib import Path
from unittest.mock import MagicMock

from src.agents.crews import SchemaRefinementCrews
from src.agents.rag_pipeline.rag_tool import RAGTool
from src.agents.rag_pipeline.models import KnowledgeSource
from src.agents.rag_pipeline.embedding_models import PineconeEmbeddingModel
from src.agents.rag_pipeline.engine import SchemaRefinementEngine
from src.core.config import settings

# Mark all tests in this file as integration tests
pytestmark = pytest.mark.integration
logger = logging.getLogger(__name__)

# --- Test Data and Fixtures ---

@pytest.fixture
def complex_knowledge_source() -> KnowledgeSource:
    """Provides the KnowledgeSource for our new complex guide."""
    if not settings.PINECONE_API_KEY:
        pytest.skip("Skipping agent tests: PINECONE_API_KEY not found in environment.")
        
    knowledge_file_path = Path(__file__).parent.parent.parent / "data" / "knowledge" / "super_complex_guide.txt"
    assert knowledge_file_path.exists(), "super_complex_guide.txt is missing."
    
    # Use the new 'file_sections' source type to ensure the document is split correctly.
    return KnowledgeSource(source_type="file_sections", content=str(knowledge_file_path))

@pytest.fixture
def base_schema_for_tests() -> dict:
    """Provides a consistent starting schema for all tests."""
    return {
        "segmentDefinitions": {
            "NM1": {
                "name": "Provider Name",
                "elements": [
                    {"xid": "NM101", "name": "Entity ID Code", "usage": "R", "valid_codes": {"code": ["IL"]}},
                    {"xid": "NM102", "name": "Entity Type Qualifier", "usage": "S"}
                ]
            },
            "CLM": {
                "name": "Claim Information",
                "elements": [
                    {"xid": "CLM01", "name": "Patient Control Number", "usage": "R"},
                    {"xid": "CLM02", "name": "Total Claim Charge", "usage": "S"}
                ]
            }
        }
    }

# --- Agent-Level Tests ---

def test_planner_agent_generates_correct_plan(complex_knowledge_source: KnowledgeSource):
    """
    Tests the planner agent in isolation to ensure it correctly interprets
    the complex guide and creates a structured, multi-step plan.
    """
    # Arrange
    embedding_model = PineconeEmbeddingModel(model_name=settings.PINECONE_EMBED_MODEL)
    rag_tool = RAGTool(knowledge_source=complex_knowledge_source, embedding_model=embedding_model)
    crew_factory = SchemaRefinementCrews(rag_tool=rag_tool)
    planning_crew = crew_factory.planning_crew()

    # Act
    result = planning_crew.kickoff()
    
    logger.info(f"Planner Agent raw output:\n{result.raw}")
    plan = json.loads(result.raw)

    # Assert
    assert isinstance(plan, list)
    # The document contains 4 distinct requirements
    assert len(plan) == 4, "The planner should have identified exactly four tasks from the document."

    # --- THIS IS THE FIX: Align assertions with the agent's more intelligent output ---
    # Task 1: Make NM102 required
    assert any(
        t['entity_id'] == '2010AA:NM1.NM102' and
        'required' in t['task_description']
        for t in plan
    ), "Task to make NM102 required was not found in the plan."

    # Task 2: Add 'QC' valid code
    assert any(
        t['entity_id'] == '2010BA:NM1.NM101' and
        "'QC'" in t['task_description']
        for t in plan
    ), "Task to add 'QC' valid code was not found in the plan."

    # Task 3: Make CLM02 required
    assert any(
        t['entity_id'] == '2300:CLM.CLM02' and
        'required' in t['task_description']
        for t in plan
    ), "Task to make CLM02 required was not found in the plan."
    
    # Task 4: Add CLM09
    assert any(
        t['entity_id'] == '2300:CLM.CLM09' and
        'add' in t['task_description'].lower() and  # Use .lower() for robustness
        'situational' in t['task_description']
        for t in plan
    ), "Task to add CLM09 was not found in the plan."
    # --- END OF FIX ---

def test_architect_agent_generates_replace_patch(mocker, base_schema_for_tests: dict):
    """
    Tests the architect agent in isolation to ensure it can correctly generate
    a 'replace' operation JSON Patch for a given task.
    """
    # Create a mock for the structured tool that `to_structured_tool()` returns.
    # This mock needs to have a `.name` attribute that is a string.
    mock_structured_tool = MagicMock()
    mock_structured_tool.name = "Mocked RAG Tool"

    # Create the main mock for the RAGTool instance.
    mock_rag_tool_for_factory = MagicMock(spec=RAGTool)
    # Configure its `to_structured_tool` method to return our prepared structured tool mock.
    mock_rag_tool_for_factory.to_structured_tool.return_value = mock_structured_tool
    
    # Arrange
    task_description = "The NM102 element in the NM1 segment must be required."
    task = {"task_type": "update_segment_definition", "entity_id": "NM1", "task_description": task_description}
    crew_input = {
        "current_schema_json": json.dumps(base_schema_for_tests),
        "task": json.dumps(task)
    }

    # Pass the validly configured mock to the factory.
    crew_factory = SchemaRefinementCrews(rag_tool=mock_rag_tool_for_factory)
    worker_crew = crew_factory.worker_crew()

    # Act
    result = worker_crew.kickoff(inputs=crew_input)
    logger.info(f"Architect Agent raw output for 'replace' test:\n{result.raw}")
    # The architect might still wrap its output in markdown, so we clean it.
    raw_json = result.raw.strip().replace("```json", "").replace("```", "")
    patch = json.loads(raw_json)

    # Assert
    assert len(patch) == 1
    assert patch[0]['op'] == 'replace'
    assert patch[0]['path'] == '/segmentDefinitions/NM1/elements/1/usage'
    assert patch[0]['value'] == 'R'

# --- Full Engine End-to-End Test ---

def test_full_engine_with_complex_guide(complex_knowledge_source: KnowledgeSource, base_schema_for_tests: dict):
    """
    An end-to-end test that runs the entire SchemaRefinementEngine with the
    complex guide and asserts that the final schema is correctly modified.
    """
    # Arrange
    engine = SchemaRefinementEngine(base_schema=base_schema_for_tests, knowledge_source=complex_knowledge_source)

    # Act
    status_updates = list(engine.run())

    # Assert preliminary success
    assert status_updates[-1].phase == "Complete", f"The refinement engine failed to complete. Final message: {status_updates[-1].message}"
    
    # Assert the final schema state
    final_schema = engine.get_final_schema()
    
    # 1. Check NM1 segment changes
    nm1_def = final_schema['segmentDefinitions']['NM1']
    assert nm1_def['elements'][1]['usage'] == 'R', "NM102 usage was not changed to 'R'"
    # The base schema has ["IL"], the guide adds ["QC"]. Check for both.
    assert 'QC' in nm1_def['elements'][0]['valid_codes']['code']
    assert 'IL' in nm1_def['elements'][0]['valid_codes']['code']

    # 2. Check CLM segment changes
    clm_def = final_schema['segmentDefinitions']['CLM']
    assert clm_def['elements'][1]['usage'] == 'R', "CLM02 usage was not changed to 'R'"
    assert len(clm_def['elements']) == 3, "An element was not added to the CLM segment."
    new_element = clm_def['elements'][2]
    assert new_element['xid'] == 'CLM09'
    assert 'Release of Information' in new_element['name']
    assert new_element['usage'] == 'S'