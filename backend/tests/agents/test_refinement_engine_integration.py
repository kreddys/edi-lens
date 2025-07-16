
import pytest
import json
from unittest.mock import MagicMock, patch

from src.agents.refinement_engine.engine import SchemaRefinementEngine
from src.agents.refinement_engine.models import KnowledgeSource, RefinementStatus
from src.agents.refinement_engine.rag_tool import RAGTool, RAGToolInput

# Mark this entire file as an 'integration' test
pytestmark = pytest.mark.integration

# A minimal schema to test the traversal logic
MOCK_BASE_SCHEMA = {
    "structure": [
        {
            "type": "loop", "xid": "HEADER", "children": [
                { "type": "segment", "xid": "BHT", "baseDefinitionId": "BHT" }
            ]
        },
        {
            "type": "loop", "xid": "2000A", "children": [
                { "type": "segment", "xid": "HL", "baseDefinitionId": "HL" },
                { "type": "loop", "xid": "2010AA", "children": [
                    { "type": "segment", "xid": "NM1", "baseDefinitionId": "NM1", "contextId": "2010AA.NM1" }
                ]}
            ]
        }
    ],
    "segmentDefinitions": {
        "BHT": { "name": "Beginning of Hierarchical Transaction", "elements": [{"description": ""}] },
        "HL": { "name": "Hierarchical Level", "elements": [{"description": ""}] },
        "NM1": { "name": "Name (Base)", "elements": [{"description": ""}] }
    },
    "contextualDefinitions": {
        "2010AA.NM1": { "name": "Billing Provider Name", "elements": [{"description": ""}] }
    },
    "rules": []
}

def test_refinement_engine_integration_with_real_crews(mocker):
    """
    Tests the full refinement engine workflow with real agent crews and a mocked RAGTool.
    """
    # Arrange
    # We will mock the embedding model to avoid actual Pinecone calls
    mocker.patch('src.agents.refinement_engine.embedding_models.PineconeEmbeddingModel')
    
    knowledge = KnowledgeSource(source_type="text", content="This is a test guide.")
    schema_copy = json.loads(json.dumps(MOCK_BASE_SCHEMA))
    
    engine = SchemaRefinementEngine(
        base_schema=schema_copy,
        knowledge_source=knowledge,
        guide_toc="Test TOC"
    )

    # Act
    status_updates = list(engine.run())

    # Assert
    final_status = status_updates[-1]
    assert final_status.phase == "Complete"
    assert final_status.progress == 1.0

    final_schema = engine.get_final_schema()
    assert "description" in final_schema["segmentDefinitions"]["BHT"]
    assert "description" in final_schema["contextualDefinitions"]["2010AA.NM1"]
    assert len(final_schema["rules"]) > 0
    assert "elements" in final_schema["segmentDefinitions"]["BHT"]
    assert len(final_schema["segmentDefinitions"]["BHT"]["elements"]) > 0
    assert "elements" in final_schema["segmentDefinitions"]["BHT"]
    assert len(final_schema["segmentDefinitions"]["BHT"]["elements"]) > 0
