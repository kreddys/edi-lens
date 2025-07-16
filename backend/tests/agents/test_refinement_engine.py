# FILE: backend/tests/agents/test_refinement_engine.py
import pytest
import json
from unittest.mock import MagicMock, patch
from jsonpatch import JsonPatchException

from src.agents.refinement_engine.engine import SchemaRefinementEngine
from src.agents.refinement_engine.models import KnowledgeSource, RefinementStatus
from src.agents.refinement_engine.rag_tool import RAGTool, RAGToolInput

# Mark this entire file as a 'unit' test
pytestmark = pytest.mark.unit

# --- MOCK DATA ---

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
        "BHT": { "name": "Beginning of Hierarchical Transaction" },
        "HL": { "name": "Hierarchical Level" },
        "NM1": { "name": "Name (Base)" }
    },
    "contextualDefinitions": {
        "2010AA.NM1": { "name": "Billing Provider Name" }
    },
    "rules": []
}

# Mock outputs from the agent crews
MOCK_ENRICHMENT_PATCH = json.dumps(
    [{ "op": "add", "path": "/description", "value": "Enriched by AI" }]
)
MOCK_COMPLEX_RULES = json.dumps({
    "rules": [{
        "ruleId": "TEST_RULE",
        "description": "A test rule.",
        "citation": "Test guide.",
        "appliesTo": { "loop": "2300" },
        "conditions": { "logicalOperator": "AND", "expressions": [] },
        "action": { "type": "REQUIRE_SEGMENT", "target": {} }
    }]
})

# --- Fixture for the Engine ---

@pytest.fixture
def mock_crews(mocker):
    """Mocks the entire SchemaEnrichmentCrews class and its methods."""
    mock_enrichment_crew = MagicMock()
    mock_enrichment_result = MagicMock()
    mock_enrichment_result.raw = MOCK_ENRICHMENT_PATCH
    mock_enrichment_crew.kickoff.return_value = mock_enrichment_result

    mock_rule_crew = MagicMock()
    mock_rule_result = MagicMock()
    mock_rule_result.raw = MOCK_COMPLEX_RULES
    mock_rule_crew.kickoff.return_value = mock_rule_result

    crews_instance = MagicMock()
    crews_instance.element_enrichment_crew.return_value = mock_enrichment_crew
    crews_instance.complex_rule_extraction_crew.return_value = mock_rule_crew
    
    mocker.patch('src.agents.refinement_engine.engine.SchemaEnrichmentCrews', return_value=crews_instance)
    return crews_instance

@pytest.fixture
def refinement_engine(mocker, mock_crews):
    """
    Provides a SchemaRefinementEngine instance with its crew-related dependencies fully mocked.
    The mock_crews fixture handles the patching of the SchemaEnrichmentCrews class.
    """
    # Patch dependencies that are initialized directly within SchemaRefinementEngine's __init__
    # before the crews are ever used. This prevents real calls to external services.
    mocker.patch('src.agents.refinement_engine.embedding_models.PineconeEmbeddingModel')
    mocker.patch('src.agents.refinement_engine.rag_tool.RAGTool')

    knowledge = KnowledgeSource(source_type="text", content="dummy")
    # Create a deep copy to prevent modifications in one test from affecting others
    schema_copy = json.loads(json.dumps(MOCK_BASE_SCHEMA))
    
    engine = SchemaRefinementEngine(
        base_schema=schema_copy,
        knowledge_source=knowledge,
        guide_toc="dummy toc"
    )
    # The engine is created with a mock `crews` object thanks to the `mock_crews` fixture.
    return engine

# --- Unit Test Cases ---

def test_engine_initialization(refinement_engine: SchemaRefinementEngine, mock_crews):
    """Tests that the engine initializes correctly and sets up its components."""
    assert refinement_engine.schema is not None
    assert refinement_engine.crews is not None
    mock_crews.element_enrichment_crew.assert_not_called()

def test_engine_run_workflow_and_status_updates(refinement_engine: SchemaRefinementEngine, mock_crews):
    """
    Tests the overall orchestration flow and verifies that status updates are yielded correctly.
    """
    # Act
    status_updates = list(refinement_engine.run())

    # Assert
    assert len(status_updates) >= 4
    
    phases = [s.phase for s in status_updates]
    assert "Element Enrichment" in phases
    assert "Rule Extraction" in phases
    assert "Complete" in phases
    
    enrichment_crew = mock_crews.element_enrichment_crew()
    assert enrichment_crew.kickoff.call_count == 4

    rule_crew = mock_crews.complex_rule_extraction_crew()
    assert rule_crew.kickoff.call_count == 1

    final_status = status_updates[-1]
    assert final_status.phase == "Complete"
    assert final_status.progress == 1.0

def test_engine_applies_patches_correctly(refinement_engine: SchemaRefinementEngine, mock_crews):
    """
    Verifies that the JSON patches returned by the agents are correctly applied
    to the in-memory schema.
    """
    # Act
    list(refinement_engine.run())
    final_schema = refinement_engine.get_final_schema()

    # Assert
    assert final_schema["segmentDefinitions"]["BHT"]["description"] == "Enriched by AI"
    assert final_schema["contextualDefinitions"]["2010AA.NM1"]["description"] == "Enriched by AI"
    assert len(final_schema["rules"]) == 1
    assert final_schema["rules"][0]["ruleId"] == "TEST_RULE"

def test_engine_handles_patching_error_gracefully(refinement_engine: SchemaRefinementEngine, mock_crews, mocker):
    """
    Tests that if a patch is invalid, the engine fails gracefully and yields a 'Failed' status.
    """
    mocker.patch('jsonpatch.JsonPatch.apply', side_effect=JsonPatchException("mock patch error"))

    # Act
    status_updates = list(refinement_engine.run())

    # Assert
    final_status = status_updates[-1]
    assert final_status.phase == "Failed"
    assert "mock patch error" in final_status.message

# --- More Complex Test Cases ---

MOCK_COMPLEX_SCHEMA = {
    "structure": [
        {
            "type": "loop", "xid": "2000A", "children": [
                { "type": "segment", "xid": "HL", "baseDefinitionId": "HL" },
                { 
                    "type": "loop", "xid": "2010AA", "children": [
                        { "type": "segment", "xid": "NM1", "baseDefinitionId": "NM1", "contextId": "2010AA.NM1" }
                    ]
                },
                {
                    "type": "loop", "xid": "2300", "children": [
                        { "type": "segment", "xid": "CLM", "baseDefinitionId": "CLM" },
                        { "type": "segment", "xid": "DTP", "baseDefinitionId": "DTP", "contextId": "2300.DTP" },
                        { 
                            "type": "loop", "xid": "2400", "children": [
                                { "type": "segment", "xid": "LX", "baseDefinitionId": "LX" },
                                { "type": "segment", "xid": "SV1", "baseDefinitionId": "SV1", "contextId": "2400.SV1" }
                            ]
                        }
                    ]
                }
            ]
        }
    ],
    "segmentDefinitions": {
        "HL": { "name": "Hierarchical Level" },
        "NM1": { "name": "Name (Base)" },
        "CLM": { "name": "Claim" },
        "DTP": { "name": "Date Time Period" },
        "LX": { "name": "Line Number" },
        "SV1": { "name": "Service Line" }
    },
    "contextualDefinitions": {
        "2010AA.NM1": { "name": "Billing Provider Name" },
        "2300.DTP": { "name": "Claim Date" },
        "2400.SV1": { "name": "Service Line Detail" }
    },
    "rules": []
}

MOCK_MULTIPLE_PATCHES = json.dumps([
    { "op": "add", "path": "/description", "value": "Enriched by AI" },
    { "op": "add", "path": "/elements/0/maxLength", "value": 10 }
])

def test_engine_handles_deeply_nested_schema(mock_crews, mocker):
    """
    Tests that the engine correctly traverses a more complex, deeply nested schema
    and applies patches at all levels.
    """
    # Arrange
    mocker.patch('src.agents.refinement_engine.embedding_models.PineconeEmbeddingModel')
    mocker.patch('src.agents.refinement_engine.rag_tool.RAGTool')
    
    knowledge = KnowledgeSource(source_type="text", content="dummy")
    schema_copy = json.loads(json.dumps(MOCK_COMPLEX_SCHEMA))
    
    engine = SchemaRefinementEngine(
        base_schema=schema_copy,
        knowledge_source=knowledge,
        guide_toc="dummy toc"
    )
    
    # Act
    list(engine.run())
    final_schema = engine.get_final_schema()

    # Assert
    enrichment_crew = mock_crews.element_enrichment_crew()
    # 6 base definitions + 3 contextual definitions
    assert enrichment_crew.kickoff.call_count == 9
    
    # Check a base definition
    assert final_schema["segmentDefinitions"]["SV1"]["description"] == "Enriched by AI"
    # Check a contextual definition
    assert final_schema["contextualDefinitions"]["2400.SV1"]["description"] == "Enriched by AI"

def test_engine_handles_multiple_patches_for_one_definition(mock_crews, mocker):
    """
    Tests that the engine can apply multiple, non-conflicting patches to a single definition.
    """
    # Arrange
    enrichment_crew = mock_crews.element_enrichment_crew()
    mock_enrichment_result = MagicMock()
    mock_enrichment_result.raw = MOCK_MULTIPLE_PATCHES
    enrichment_crew.kickoff.return_value = mock_enrichment_result
    
    mocker.patch('src.agents.refinement_engine.embedding_models.PineconeEmbeddingModel')
    mocker.patch('src.agents.refinement_engine.rag_tool.RAGTool')
    
    knowledge = KnowledgeSource(source_type="text", content="dummy")
    schema_copy = json.loads(json.dumps(MOCK_BASE_SCHEMA))
    # Add an 'elements' array to test the second patch
    schema_copy["segmentDefinitions"]["BHT"]["elements"] = [{"name": "Element 1"}]

    engine = SchemaRefinementEngine(
        base_schema=schema_copy,
        knowledge_source=knowledge,
        guide_toc="dummy toc"
    )

    # Act
    list(engine.run())
    final_schema = engine.get_final_schema()

    # Assert
    bht_def = final_schema["segmentDefinitions"]["BHT"]
    assert bht_def["description"] == "Enriched by AI"
    assert bht_def["elements"][0]["maxLength"] == 10

def test_engine_skips_enrichment_on_empty_llm_output(mock_crews, mocker):
    """
    Tests that the engine continues gracefully if the LLM returns an empty or invalid JSON response.
    """
    # Arrange
    enrichment_crew = mock_crews.element_enrichment_crew()
    mock_empty_result = MagicMock()
    mock_empty_result.raw = "" # Simulate empty response
    enrichment_crew.kickoff.return_value = mock_empty_result
    
    mocker.patch('src.agents.refinement_engine.embedding_models.PineconeEmbeddingModel')
    mocker.patch('src.agents.refinement_engine.rag_tool.RAGTool')
    
    knowledge = KnowledgeSource(source_type="text", content="dummy")
    schema_copy = json.loads(json.dumps(MOCK_BASE_SCHEMA))
    
    engine = SchemaRefinementEngine(
        base_schema=schema_copy,
        knowledge_source=knowledge,
        guide_toc="dummy toc"
    )

    # Act
    list(engine.run())
    final_schema = engine.get_final_schema()

    # Assert
    # The schema should be unchanged as no valid patches were applied
    assert "description" not in final_schema["segmentDefinitions"]["BHT"]
    # Ensure all definitions were still processed
    assert enrichment_crew.kickoff.call_count == 4

def test_engine_handles_malformed_rule_json(mock_crews, mocker):
    """
    Tests that the engine handles malformed JSON from the rule extraction crew.
    """
    # Arrange
    rule_crew = mock_crews.complex_rule_extraction_crew()
    mock_malformed_result = MagicMock()
    mock_malformed_result.raw = '{"rules": [{"ruleId": "BAD_RULE", "descript' # Malformed JSON
    rule_crew.kickoff.return_value = mock_malformed_result
    
    mocker.patch('src.agents.refinement_engine.embedding_models.PineconeEmbeddingModel')
    mocker.patch('src.agents.refinement_engine.rag_tool.RAGTool')
    
    knowledge = KnowledgeSource(source_type="text", content="dummy")
    schema_copy = json.loads(json.dumps(MOCK_BASE_SCHEMA))
    
    engine = SchemaRefinementEngine(
        base_schema=schema_copy,
        knowledge_source=knowledge,
        guide_toc="dummy toc"
    )

    # Act
    list(engine.run())
    final_schema = engine.get_final_schema()

    # Assert
    # The rules list should remain empty
    assert len(final_schema["rules"]) == 0

# --- Edge Case Scenarios ---

def test_engine_handles_empty_base_schema(mock_crews, mocker):
    """
    Tests that the engine runs without errors when given a completely empty schema.
    """
    # Arrange
    mocker.patch('src.agents.refinement_engine.embedding_models.PineconeEmbeddingModel')
    mocker.patch('src.agents.refinement_engine.rag_tool.RAGTool')
    
    knowledge = KnowledgeSource(source_type="text", content="dummy")
    
    engine = SchemaRefinementEngine(
        base_schema={},
        knowledge_source=knowledge,
        guide_toc="dummy toc"
    )
    
    # Act
    status_updates = list(engine.run())
    final_schema = engine.get_final_schema()

    # Assert
    # No definitions to process, so kickoff should not be called
    mock_crews.element_enrichment_crew().kickoff.assert_not_called()
    # Rule crew should still run
    mock_crews.complex_rule_extraction_crew().kickoff.assert_called_once()
    # The final schema should just contain the extracted rules
    assert len(final_schema.get("rules", [])) == 1
    assert status_updates[-1].phase == "Complete"

def test_engine_handles_logically_invalid_patch(mock_crews, mocker):
    """
    Tests that the engine catches a JsonPatchException for a logically invalid patch
    (e.g., testing a value that doesn't exist) and fails gracefully.
    """
    # Arrange
    # This patch will fail because /description does not exist to be tested
    invalid_patch = json.dumps([
        { "op": "test", "path": "/description", "value": "some value" },
        { "op": "add", "path": "/description", "value": "A new description" }
    ])
    enrichment_crew = mock_crews.element_enrichment_crew()
    mock_invalid_result = MagicMock()
    mock_invalid_result.raw = invalid_patch
    enrichment_crew.kickoff.return_value = mock_invalid_result
    
    mocker.patch('src.agents.refinement_engine.embedding_models.PineconeEmbeddingModel')
    mocker.patch('src.agents.refinement_engine.rag_tool.RAGTool')
    
    knowledge = KnowledgeSource(source_type="text", content="dummy")
    schema_copy = json.loads(json.dumps(MOCK_BASE_SCHEMA))
    
    engine = SchemaRefinementEngine(
        base_schema=schema_copy,
        knowledge_source=knowledge,
        guide_toc="dummy toc"
    )

    # Act
    status_updates = list(engine.run())

    # Assert
    final_status = status_updates[-1]
    assert final_status.phase == "Failed"
    assert "member 'description' not found" in final_status.message

def test_engine_handles_malformed_rules_key(mock_crews, mocker):
    """
    Tests robustness against a malformed rule structure where 'rules' is not a list.
    """
    # Arrange
    rule_crew = mock_crews.complex_rule_extraction_crew()
    mock_bad_rules_result = MagicMock()
    # 'rules' should be a list, not a dict
    mock_bad_rules_result.raw = '{"rules": {"ruleId": "NOT_A_LIST"}}'
    rule_crew.kickoff.return_value = mock_bad_rules_result
    
    mocker.patch('src.agents.refinement_engine.embedding_models.PineconeEmbeddingModel')
    mocker.patch('src.agents.refinement_engine.rag_tool.RAGTool')
    
    knowledge = KnowledgeSource(source_type="text", content="dummy")
    schema_copy = json.loads(json.dumps(MOCK_BASE_SCHEMA))
    # Ensure there's a rules list to begin with
    schema_copy["rules"] = []
    
    engine = SchemaRefinementEngine(
        base_schema=schema_copy,
        knowledge_source=knowledge,
        guide_toc="dummy toc"
    )

    # Act
    status_updates = list(engine.run())

    # Assert
    final_status = status_updates[-1]
    assert final_status.phase == "Failed"
    # The error should be caught by the generic exception handler
    assert "'rules' key in agent output is not a list" in final_status.message

def test_engine_handles_non_patch_json_from_agent(mock_crews, mocker):
    """
    Tests that the engine fails gracefully if an agent returns valid JSON that is not a patch.
    """
    # Arrange
    enrichment_crew = mock_crews.element_enrichment_crew()
    mock_non_patch_result = MagicMock()
    mock_non_patch_result.raw = '{"error": "An unexpected error occurred."}'
    enrichment_crew.kickoff.return_value = mock_non_patch_result
    
    mocker.patch('src.agents.refinement_engine.embedding_models.PineconeEmbeddingModel')
    mocker.patch('src.agents.refinement_engine.rag_tool.RAGTool')
    
    knowledge = KnowledgeSource(source_type="text", content="dummy")
    schema_copy = json.loads(json.dumps(MOCK_BASE_SCHEMA))
    
    engine = SchemaRefinementEngine(
        base_schema=schema_copy,
        knowledge_source=knowledge,
        guide_toc="dummy toc"
    )

    # Act
    status_updates = list(engine.run())

    # Assert
    final_status = status_updates[-1]
    assert final_status.phase == "Failed"
    assert "Patch is not a list of operations." in final_status.message

