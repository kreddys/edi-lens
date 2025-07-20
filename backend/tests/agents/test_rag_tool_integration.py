# FILE: backend/tests/agents/test_rag_tool_integration.py
import pytest
import pytest_asyncio
import httpx
import asyncio
from pathlib import Path
from typing import AsyncGenerator

from src.main import app
from src.agents.tools.rag import KnowledgeBaseTool

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]

LIGHTRAG_TEST_URL = "http://lightrag-server-test:9621"

@pytest.fixture(scope="module")
def sample_guide_path() -> Path:
    return Path(__file__).parent.parent / "data/test_guides/rag_test_guide.txt"

@pytest_asyncio.fixture(scope="function")
async def lightrag_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient(base_url=LIGHTRAG_TEST_URL) as client:
        yield client

@pytest_asyncio.fixture(scope="function", autouse=True)
async def clean_rag_db(lightrag_client: httpx.AsyncClient):
    yield
    print("\n[RAG Cleanup] Clearing all documents from LightRAG...")
    try:
        response = await lightrag_client.delete("/documents")
        response.raise_for_status()
        print("[RAG Cleanup] Successfully cleared documents.")
    except httpx.HTTPError as e:
        print(f"[RAG Cleanup] WARNING: Could not clear documents. Error: {e}")

async def test_lightrag_server_health(lightrag_client: httpx.AsyncClient):
    response = await lightrag_client.get("/health")
    assert response.status_code == 200
    health_data = response.json()
    assert health_data["status"] == "healthy"
    assert health_data["configuration"]["workspace"] == "edi_lens_kb_test"

async def test_ingestion_and_query_lifecycle(
    lightrag_client: httpx.AsyncClient,
    sample_guide_path: Path
):
    """
    Tests the full RAG lifecycle: ingestion, processing, and querying.
    """
    # 1. INGESTION - Restore the API-based upload logic
    with open(sample_guide_path, "rb") as f:
        files = {"file": (sample_guide_path.name, f, "text/plain")}
        response = await lightrag_client.post("/documents/upload", files=files)
    assert response.status_code == 200, f"Upload failed: {response.text}"
    
    # 2. POLLING - Wait for the pipeline to finish processing the uploaded file.
    max_wait_seconds = 60
    poll_interval_seconds = 5
    is_ready = False
    for i in range(max_wait_seconds // poll_interval_seconds):
        print(f"Polling LightRAG pipeline status (attempt {i+1})...")
        try:
            status_response = await lightrag_client.get("/documents/pipeline_status")
            status_data = status_response.json()
            
            if not status_data.get("busy", True):
                print("LightRAG pipeline is idle. Document processing should be complete.")
                is_ready = True
                break
            
            print(f"Pipeline is busy. Status: {status_data.get('latest_message', 'N/A')}")
        except httpx.RequestError as e:
            print(f"Could not connect to LightRAG to poll status: {e}")

        await asyncio.sleep(poll_interval_seconds)

    assert is_ready, "LightRAG pipeline did not become idle within the timeout period."

    # 3. QUERY with the agent tool
    rag_tool = KnowledgeBaseTool()
    rag_tool.LIGHTRAG_API_URL = LIGHTRAG_TEST_URL
    
    answer_nmi = rag_tool._run(query="What is the secret code for the NMI segment?")
    print(f"Received LightRAG response for NMI query: '{answer_nmi}'")
    assert "Blue Penguin" in answer_nmi

    answer_dmx = rag_tool._run(query="What is the purpose of the DMX segment?")
    print(f"Received LightRAG response for DMX query: '{answer_dmx}'")
    assert "Date/Time information" in answer_dmx
    assert "Yellow Giraffe" in answer_dmx