# FILE: backend/tests/agents/test_graph_rag_system.py
import pytest
import os
from pathlib import Path
import asyncio
import sys

# This file is in /backend/tests/agents, so we need to go up three levels to reach the project root.
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from pinecone import Pinecone

from src.core.config import settings
from src.agents.ingestion.ingestor import GuideIngestor, PINECONE_INDEX_NAME
from src.models.knowledge_base import KnowledgeBaseGuide, KnowledgeBaseNode
from src.agents.rag_pipeline.graph_rag_tool import GraphRAGTool

# Mark all tests in this file as integration tests and tell pytest to run them in order.
pytestmark = [pytest.mark.integration, pytest.mark.run(order=-1)]

# A small, predictable guide with a clear hierarchy for testing
SAMPLE_GUIDE_TEXT = """
2010AA Billing Provider Name Loop
This loop contains the billing provider's name and address.

NM1 Billing Provider Name
This segment contains the provider's name and NPI.
NM1-01 Entity Identifier Code
Code identifying an organizational entity.
NM1-02 Entity Type Qualifier
Code qualifying the type of entity.

N3 Billing Provider Address
This segment contains the provider's street address.

N4 Billing Provider City, State, ZIP Code
This segment contains the provider's city, state, and ZIP code.

2300 Claim Information Loop
This loop contains claim-level information.
"""

@pytest.fixture(scope="module")
async def knowledge_base_setup(db_session, tmp_path_factory):
    """
    Module-scoped fixture to perform the entire ingestion process once.
    This populates the test DB and Pinecone index with our sample guide.
    """
    if not (settings.PINECONE_API_KEY and (os.getenv("OPENAI_API_KEY") or os.getenv("OPENROUTER_API_KEY"))):
        pytest.skip("Skipping GraphRAG tests: PINECONE_API_KEY and a valid LLM provider key are not set.")

    guide_version = "005010X999A1" # Use a unique version for testing
    
    # Use the GuideIngestor class directly from its new location
    ingestor = GuideIngestor(
        guide_version=guide_version,
        guide_name="Sample Test Guide",
        guide_content=SAMPLE_GUIDE_TEXT
    )
    # Consume the async generator to run the process
    async for status in ingestor.run():
        print(f"Ingestion status: {status}")

    yield guide_version

    # Teardown: Clean up Pinecone after all tests in this module are done
    pc = Pinecone(api_key=settings.PINECONE_API_KEY)
    if PINECONE_INDEX_NAME in pc.list_indexes().names():
        index = pc.Index(PINECONE_INDEX_NAME)
        index.delete(filter={"guide_version": guide_version})
        print(f"\nCleaned up Pinecone vectors for guide version {guide_version}")


# --- Test Cases ---

@pytest.mark.asyncio
async def test_ingestion_creates_correct_db_nodes(db_session, knowledge_base_setup):
    """
    Verifies that the ingestion script correctly populated the PostgreSQL database
    with a hierarchical structure.
    """
    guide_version = knowledge_base_setup
    
    # Fetch the guide and all its nodes with their children
    guide = (await db_session.execute(
        select(KnowledgeBaseGuide).options(selectinload(KnowledgeBaseGuide.nodes).selectinload(KnowledgeBaseNode.children)).filter_by(version=guide_version)
    )).scalars().first()

    assert guide is not None
    
    # Find the top-level loop nodes
    top_level_nodes = [n for n in guide.nodes if n.parent_id is None]
    assert len(top_level_nodes) == 2
    
    loop_2010aa = next(n for n in top_level_nodes if n.node_key == "2010AA")
    loop_2300 = next(n for n in top_level_nodes if n.node_key == "2300")
    
    assert loop_2010aa is not None
    assert "contains the billing provider's name" in loop_2010aa.raw_text
    
    # Verify the children of the 2010AA loop
    assert len(loop_2010aa.children) == 3
    nm1_node = next(n for n in loop_2010aa.children if n.node_key == "NM1")
    n3_node = next(n for n in loop_2010aa.children if n.node_key == "N3")
    
    assert nm1_node is not None
    assert "provider's name and NPI" in nm1_node.raw_text
    
    # Verify the grandchildren (elements of NM1)
    assert len(nm1_node.children) == 2
    nm101_node = next(n for n in nm1_node.children if n.node_key == "NM1-01")
    assert nm101_node is not None
    assert nm101_node.parent_id == nm1_node.id
    assert "Code identifying an organizational entity" in nm101_node.raw_text
    
    assert loop_2300 is not None
    assert "claim-level information" in loop_2300.raw_text
    assert len(loop_2300.children) == 0 # This loop has no children in our sample


@pytest.mark.asyncio
async def test_graph_rag_tool_retrieves_hierarchical_context(knowledge_base_setup):
    """
    Tests that the GraphRAGTool, when queried, returns a synthesized context
    that includes information from a node AND its parent.
    """
    guide_version = knowledge_base_setup # Ensures ingestion has run
    
    rag_tool = GraphRAGTool()
    
    # Query for a specific, nested element
    query = "What is the NM1-01 Entity Identifier Code?"
    
    # Run the tool
    # We need to run the async version as the sync wrapper won't work inside an async test
    result_context = await rag_tool._run_async(query=query)

    print(f"\n--- RAG Tool Output ---\n{result_context}\n---")

    # Assert that the output contains text from the element ITSELF
    assert "Code identifying an organizational entity" in result_context
    
    # Assert that the output ALSO contains text from its PARENT (the NM1 segment)
    assert "This segment contains the provider's name and NPI" in result_context
    
    # Assert that the output ALSO contains text from its GRANDPARENT (the 2010AA loop)
    assert "This loop contains the billing provider's name and address" in result_context

@pytest.mark.asyncio
async def test_graph_rag_tool_handles_no_results(knowledge_base_setup):
    """
    Tests that the tool returns a graceful message when no relevant context is found.
    """
    guide_version = knowledge_base_setup # Ensures ingestion has run
    
    rag_tool = GraphRAGTool()
    
    # Use a query that is completely unrelated to the sample guide
    query = "Information about rocket propulsion"
    
    result_context = await rag_tool._run_async(query=query)
    
    assert result_context == "No relevant information found for the query."