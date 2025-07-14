# FILE: backend/tests/agents/test_refinement_engine.py
import pytest
import json
from unittest.mock import MagicMock

from src.agents.refinement_engine.engine import SchemaRefinementEngine
from src.agents.refinement_engine.models import KnowledgeSource

# Mark this entire file as a 'unit' test
pytestmark = pytest.mark.unit

# --- MOCK DATA ---

MOCK_PLAN_JSON = json.dumps([
    {
        "task_type": "update_segment_definition",
        "entity_id": "CLM",
        "task_description": "Make CLM02 required."
    }
])

MOCK_PATCH_FOR_CLM = json.dumps([
    {"op": "replace", "path": "/segmentDefinitions/CLM/elements/1/usage", "value": "R"}
])


# --- The Unit Test Case ---

def test_engine_orchestrates_plan_and_execute_workflow(mocker):
    """
    Unit test for the SchemaRefinementEngine's orchestration logic.
    Mocks the crew outputs AND the embedding model to isolate the engine.
    """
    # --- THIS IS THE FIX ---
    # 1. Mock the PineconeEmbeddingModel to prevent any real API calls
    mock_embedding_model = MagicMock()
    mocker.patch(
        'src.agents.refinement_engine.engine.PineconeEmbeddingModel',
        return_value=mock_embedding_model
    )

    # 2. Mock the RAGTool's initialization, as it depends on the embedding model
    #    We don't need to test the RAGTool's internals here, just the engine.
    mocker.patch('src.agents.refinement_engine.engine.RAGTool')
    # --- END OF FIX ---

    # Arrange: Mock the crews that the engine depends on
    mock_crew_factory_instance = MagicMock()

    mock_planning_crew = MagicMock()
    mock_plan_output = MagicMock()
    mock_plan_output.raw = MOCK_PLAN_JSON
    mock_planning_crew.kickoff.return_value = mock_plan_output
    mock_crew_factory_instance.planning_crew.return_value = mock_planning_crew

    mock_worker_crew = MagicMock()
    mock_patch_output = MagicMock()
    mock_patch_output.raw = MOCK_PATCH_FOR_CLM
    mock_worker_crew.kickoff.return_value = mock_patch_output
    mock_crew_factory_instance.worker_crew.return_value = mock_worker_crew
    
    mocker.patch('src.agents.refinement_engine.engine.SchemaRefinementCrews', return_value=mock_crew_factory_instance)

    base_schema = {
        "segmentDefinitions": {
            "CLM": {
                "name": "Claim Info",
                "elements": [
                    {"xid": "CLM01", "usage": "R"},
                    {"xid": "CLM02", "usage": "S"}
                ]
            }
        }
    }
    knowledge = KnowledgeSource(source_type="text", content="Dummy knowledge source.")

    # Act: Run the engine and collect all status updates
    engine = SchemaRefinementEngine(base_schema=base_schema, knowledge_source=knowledge)
    status_updates = list(engine.run())

    # Assert: Verify the engine behaved as expected
    assert len(status_updates) == 5, "The number of status updates was not as expected."
    final_status = status_updates[-1]
    assert final_status.phase == "Complete"

    final_schema = engine.get_final_schema()
    clm_def = final_schema["segmentDefinitions"]["CLM"]
    assert clm_def["elements"][1]["usage"] == "R"

    mock_planning_crew.kickoff.assert_called_once()
    mock_worker_crew.kickoff.assert_called_once()