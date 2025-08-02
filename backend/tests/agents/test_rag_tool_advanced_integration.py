# FILE: backend/tests/agents/test_rag_tool_advanced_integration.py
import pytest
import pytest_asyncio
import httpx
import asyncio
from pathlib import Path
from typing import AsyncGenerator

from src.agents.tools.rag import KnowledgeBaseTool

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.integration,
    pytest.mark.skip(reason="Skipping advanced RAG tool tests as this feature is not currently active.")
]

LIGHTRAG_TEST_URL = "http://lightrag-server-test:9621"

# ... (wait_for_pipeline_completion helper and fixtures are unchanged) ...
async def wait_for_pipeline_completion(client: httpx.AsyncClient):
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
        pytest.fail("Pipeline did not become busy after upload/delete. Task likely failed to start.")

    print("Waiting for RAG pipeline to finish processing...")
    for _ in range(60):
        status_response = await client.get("/documents/pipeline_status")
        if not status_response.json().get("busy", True):
            print("Pipeline is now idle. Processing complete.")
            return
        await asyncio.sleep(1)

    pytest.fail("Pipeline did not become idle within the timeout period.")

@pytest_asyncio.fixture(scope="function")
async def lightrag_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient(base_url=LIGHTRAG_TEST_URL, timeout=60.0) as client:
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

async def ingest_file(client: httpx.AsyncClient, file_path: Path):
    print(f"Ingesting file: {file_path.name}...")
    with open(file_path, "rb") as f:
        files = {"file": (file_path.name, f, "text/plain")}
        response = await client.post("/documents/upload", files=files)
        assert response.status_code == 200, f"Upload failed: {response.text}"
    await wait_for_pipeline_completion(client)
    print(f"Finished ingesting {file_path.name}.")

# ... (test_multi_document_retrieval and test_query_with_no_relevant_context are unchanged) ...
async def test_multi_document_retrieval(lightrag_client: httpx.AsyncClient):
    guide_a_path = Path(__file__).parent.parent / "data/test_guides/guide_a.txt"
    guide_b_path = Path(__file__).parent.parent / "data/test_guides/guide_b.txt"
    await ingest_file(lightrag_client, guide_a_path)
    await ingest_file(lightrag_client, guide_b_path)
    rag_tool = KnowledgeBaseTool()
    rag_tool.LIGHTRAG_API_URL = LIGHTRAG_TEST_URL
    response_a = rag_tool._run(query="What is the primary secret code?")
    print(f"Response for Guide A query: '{response_a}'")
    assert "alpha" in response_a.lower()
    assert "bravo" not in response_a.lower()
    response_b = rag_tool._run(query="What color is the grass?")
    print(f"Response for Guide B query: '{response_b}'")
    assert "green" in response_b.lower()
    assert "blue" not in response_b.lower()

async def test_query_with_no_relevant_context(lightrag_client: httpx.AsyncClient):
    guide_a_path = Path(__file__).parent.parent / "data/test_guides/guide_a.txt"
    await ingest_file(lightrag_client, guide_a_path)
    rag_tool = KnowledgeBaseTool()
    rag_tool.LIGHTRAG_API_URL = LIGHTRAG_TEST_URL
    response = rag_tool._run(query="What is the capital of France?")
    print(f"Response for irrelevant query: '{response}'")
    lower_response = response.lower()
    assert "i do not have" in lower_response or "not able to provide" in lower_response or "information is not available" in lower_response
    assert "alpha" not in lower_response
    assert "sky" not in lower_response

async def test_document_deletion_lifecycle(lightrag_client: httpx.AsyncClient):
    # 1. Arrange: Ingest a document and verify its content is retrievable
    guide_b_path = Path(__file__).parent.parent / "data/test_guides/guide_b.txt"
    await ingest_file(lightrag_client, guide_b_path)
    
    rag_tool = KnowledgeBaseTool()
    rag_tool.LIGHTRAG_API_URL = LIGHTRAG_TEST_URL
    
    response_before_delete = rag_tool._run(query="What is the secondary secret code?")
    print(f"Response before delete: '{response_before_delete}'")
    assert "bravo" in response_before_delete.lower()

    # 2. Act: Find the document's ID and delete it
    docs_response = await lightrag_client.get("/documents")
    docs_data = docs_response.json()
    doc_id = None
    for status, doc_list in docs_data.get("statuses", {}).items():
        for doc in doc_list:
            if doc.get("file_path") and guide_b_path.name in doc["file_path"]:
                doc_id = doc["id"]
                break
    
    assert doc_id is not None, "Could not find the ingested document ID to delete it."
    print(f"Found document ID '{doc_id}' for deletion.")

    delete_payload = {"doc_ids": [doc_id], "delete_file": True}
    delete_response = await lightrag_client.request("DELETE", "/documents/delete_document", json=delete_payload)
    assert delete_response.status_code == 200
    
    await wait_for_pipeline_completion(lightrag_client) # Wait for deletion to finish

    # --- THIS IS THE FIX: Clear the cache after deletion ---
    print("Clearing RAG query cache...")
    clear_cache_response = await lightrag_client.post("/documents/clear_cache", json={})
    assert clear_cache_response.status_code == 200
    print("Cache cleared successfully.")
    # --- END OF FIX ---

    # 3. Assert: The information should now be gone
    response_after_delete = rag_tool._run(query="What is the secondary secret code?")
    print(f"Response after delete: '{response_after_delete}'")
    lower_response_after_delete = response_after_delete.lower()
    assert "bravo" not in lower_response_after_delete
    assert "i do not have" in lower_response_after_delete or "not able to provide" in lower_response_after_delete or "information is not available" in lower_response_after_delete