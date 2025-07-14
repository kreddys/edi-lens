# FILE: backend/tests/agents/test_rag_tool_integration.py
import pytest
import os
import logging
from pathlib import Path
from unittest.mock import MagicMock

from src.agents.refinement_engine.rag_tool import RAGTool
from src.agents.refinement_engine.models import KnowledgeSource
from src.agents.refinement_engine.embedding_models import PineconeEmbeddingModel
from src.core.config import settings

pytestmark = pytest.mark.integration
logger = logging.getLogger(__name__)

# --- Fixture for a fully initialized RAG tool ---
@pytest.fixture
def initialized_rag_tool() -> RAGTool:
    if not settings.PINECONE_API_KEY:
        pytest.skip("Skipping RAG tool tests: PINECONE_API_KEY not found in environment.")
    
    knowledge_file_path = Path(__file__).parent.parent.parent / "data" / "knowledge" / "complex_guide.txt"
    assert knowledge_file_path.exists(), f"Test knowledge file is missing at: {knowledge_file_path}"
    
    knowledge = KnowledgeSource(source_type="file_sections", content=str(knowledge_file_path))
    embedding_model = PineconeEmbeddingModel(model_name=settings.PINECONE_EMBED_MODEL)
    
    return RAGTool(
        knowledge_source=knowledge,
        embedding_model=embedding_model
    )

# --- Test Cases ---

def test_rag_tool_retrieves_ref_rules_context(initialized_rag_tool: RAGTool):
    """
    Tests that the retriever can correctly find and isolate the context
    for the 'REF' segment rules.
    """
    assert initialized_rag_tool.query_engine is not None, "RAG query engine failed to initialize."
    
    query = "What are the requirements for the REF segment when its first element is 'G2'?"
    final_response = initialized_rag_tool._run(query)
    
    logger.info(f"Retrieved context for REF rules test:\n---\n{final_response}\n---")
    
    # Positive Assertions: The correct context is present
    assert "Referring Provider (REF) Rules" in final_response
    assert "REF01 element contains the code 'G2'" in final_response
    
    # Negative Assertions: Irrelevant context is absent
    assert "CLM02, Total Claim Charge" not in final_response
    assert "No relevant context found" not in final_response

def test_rag_tool_retrieves_dtp_rules_context(initialized_rag_tool: RAGTool):
    """
    Tests that the retriever can correctly find and isolate the context
    for the 'DTP' segment rules, proving it works for different sections.
    """
    assert initialized_rag_tool.query_engine is not None, "RAG query engine failed to initialize."

    query = "How many times can the DTP segment repeat?"
    final_response = initialized_rag_tool._run(query)

    logger.info(f"Retrieved context for DTP rules test:\n---\n{final_response}\n---")
    
    # Positive Assertions
    assert "Date Time Period (DTP) Rules" in final_response
    assert "repeat up to a maximum of 5 times" in final_response
    
    # Negative Assertions
    assert "Claim Information (CLM) Rules" not in final_response
    assert "No relevant context found" not in final_response

def test_rag_tool_handles_irrelevant_query(initialized_rag_tool: RAGTool):
    """
    Tests that the RAG tool's final output is a specific message when asked
    a completely irrelevant question.
    """
    assert initialized_rag_tool.query_engine is not None, "RAG query engine failed to initialize."
    
    query = "What is the currency of Japan?"
    final_response = initialized_rag_tool._run(query)

    logger.info(f"Final response for irrelevant query: '{final_response}'")

    # --- THIS IS THE FIX ---
    # We now assert that the tool itself correctly identified the context as irrelevant.
    assert final_response == "No relevant context found in the documentation for this query."
    # --- END OF FIX ---

def test_rag_tool_initialization_with_empty_source():
    """
    Tests that the RAGTool initializes gracefully and returns a specific
    error message when the knowledge source is empty.
    """
    knowledge = KnowledgeSource(source_type="text", content="")
    embedding_model = PineconeEmbeddingModel(model_name=settings.PINECONE_EMBED_MODEL)
    
    # This now executes without raising a ValueError
    rag_tool = RAGTool(
        knowledge_source=knowledge,
        embedding_model=embedding_model
    )
    
    # The engine should not have been created because the document list was empty
    assert rag_tool.query_engine is None
    
    # Running the tool should return the specific error message
    result = rag_tool._run("any query")
    assert "Error: RAG query engine is not initialized" in result

def test_rag_tool_properties(initialized_rag_tool: RAGTool):
    """
    Tests that the tool's name and description are set correctly.
    """
    assert initialized_rag_tool.name == "Documentation Query Tool"
    assert "Queries the implementation guide documentation" in initialized_rag_tool.description