# FILE: backend/tests/agents/test_knowledge_ingestion_and_rag_integration.py
import pytest
import logging
import asyncio
from httpx import AsyncClient

# The agent tool we will use for querying
from src.agents.tools.rag import KnowledgeBaseTool

# Auth dependencies for mocking the superuser
from src.core.auth import User, RealmAccess, get_current_user
from src.main import app

# Mark the whole file as integration tests
pytestmark = pytest.mark.integration
logger = logging.getLogger(__name__)


@pytest.fixture
def rag_tool() -> KnowledgeBaseTool:
    """Provides an instance of the RAG tool for querying."""
    return KnowledgeBaseTool()

@pytest.fixture
def superuser():
    """Provides a mock superuser object, required for the ingestion endpoint."""
    return User(
        sub="mock-superuser-id",
        preferred_username="super-tester",
        groups=["tenant-a"],
        realm_access=RealmAccess(roles=["superuser"])
    )

@pytest.fixture
def mock_get_superuser(superuser: User):
    """Mocks the get_current_user dependency to return our superuser."""
    app.dependency_overrides[get_current_user] = lambda: superuser
    yield
    # Clean up the dependency override after the test
    del app.dependency_overrides[get_current_user]


async def test_ingest_and_query_workflow(
    async_client: AsyncClient, 
    rag_tool: KnowledgeBaseTool, 
    mock_get_superuser: None
):
    """
    Tests the full end-to-end workflow:
    1. Ingests a new document via the API.
    2. Waits for LightRAG to process it.
    3. Queries for the content of that specific document.
    """
    # --- 1. Arrange & Ingest ---
    # A unique piece of information that only exists in this test
    knowledge_content = "The secret codeword for the test is 'avocado'."
    
    # The file upload requires a specific format for httpx
    files_to_upload = {
        'file': ('test_knowledge.txt', knowledge_content.encode('utf-8'), 'text/plain')
    }
    
    ingest_url = "/api/v1/knowledge/ingest-guide"
    
    logger.info(f"Attempting to ingest test knowledge via POST to {ingest_url}")
    ingest_response = await async_client.post(ingest_url, files=files_to_upload)
    
    # Assert that the initial API call was successful
    assert ingest_response.status_code == 200, f"Ingestion API call failed: {ingest_response.text}"
    logger.info("Test knowledge successfully sent to the ingestion endpoint.")
    
    # --- 2. Wait for Processing ---
    # The LightRAG server processes files in the background. We must wait
    # for it to complete the embedding and indexing. For a small test file,
    # 15 seconds is a very safe amount of time.
    wait_time = 15
    logger.info(f"Waiting for {wait_time} seconds for LightRAG to process the document...")
    await asyncio.sleep(wait_time)
    logger.info("Wait complete. Proceeding to query.")

    # --- 3. Query ---
    query = "What is the secret codeword for the test?"
    logger.info(f"Querying RAG tool with: '{query}'")
    rag_response = rag_tool._run(query=query)
    logger.info(f"Received RAG response: '{rag_response}'")

    # --- 4. Assert ---
    assert "Error" not in rag_response, "The RAG response contained an error message."
    assert "No answer" not in rag_response, "The RAG tool could not find an answer."
    
    # The most important check: did it find our specific, unique content?
    assert "avocado" in rag_response.lower(), "The response did not contain the secret codeword."