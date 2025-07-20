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

async def wait_for_pipeline_completion(client: httpx.AsyncClient):
    # ... (this helper function is correct and unchanged) ...
    print("Waiting for RAG pipeline to start processing...")
    job_started = False
    for _ in range(10): 
        try:
            status_response = await client.get("/documents/pipeline_status")
            if status_response.json().get("busy", False):
                print("Pipeline is now busy. Processing has begun.")
                job_started = True
                break
        except httpx.RequestError:
            pass 
        await asyncio.sleep(1)
    
    if not job_started:
        pytest.fail("Pipeline did not become busy after upload. Ingestion likely failed to start.")

    print("Waiting for RAG pipeline to finish processing...")
    for _ in range(60): 
        status_response = await client.get("/documents/pipeline_status")
        if not status_response.json().get("busy", True):
            print("Pipeline is now idle. Processing complete.")
            return
        await asyncio.sleep(1)

    pytest.fail("Pipeline did not become idle within the timeout period.")

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
    with open(sample_guide_path, "rb") as f:
        files = {"file": (sample_guide_path.name, f, "text/plain")}
        response = await lightrag_client.post("/documents/upload", files=files)
    assert response.status_code == 200, f"Upload failed: {response.text}"
    
    await wait_for_pipeline_completion(lightrag_client)

    rag_tool = KnowledgeBaseTool()
    rag_tool.LIGHTRAG_API_URL = LIGHTRAG_TEST_URL
    
    answer_nmi = rag_tool._run(query="What is the secret code for the NMI segment?")
    print(f"Received LightRAG response for NMI query: '{answer_nmi}'")
    # --- THIS IS THE FIX: Case-insensitive check ---
    assert "blue penguin" in answer_nmi.lower()

    answer_dmx = rag_tool._run(query="What is the purpose of the DMX segment?")
    print(f"Received LightRAG response for DMX query: '{answer_dmx}'")
    assert "date/time information" in answer_dmx.lower()
    assert "yellow giraffe" in answer_dmx.lower()
    # --- END OF FIX ---