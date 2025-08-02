# FILE: backend/tests/api/test_knowledge_api.py
import pytest
import pytest_asyncio
import httpx
from httpx import AsyncClient
from typing import AsyncGenerator
from io import BytesIO
import asyncio

from src.main import app
from src.core.auth import User, RealmAccess, get_current_user

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.integration,
    pytest.mark.skip(reason="Skipping knowledge base API tests as the RAG service is not part of the core dev stack.")
]

LIGHTRAG_TEST_URL = "http://lightrag-server-test:9621"

# --- Fixtures ---

@pytest.fixture
def superuser_user():
    """A superuser with permission to manage knowledge sources."""
    return User(
        sub="mock-superuser-kb-123",
        preferred_username="kb-manager",
        groups=["tenant-a"],
        realm_access=RealmAccess(roles=["superuser"])
    )

@pytest.fixture
def mock_get_current_user(superuser_user):
    """Mocks the get_current_user dependency."""
    app.dependency_overrides[get_current_user] = lambda: superuser_user
    yield
    del app.dependency_overrides[get_current_user]

@pytest_asyncio.fixture(scope="function")
async def lightrag_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Provides a real HTTPX client for direct interaction with the LightRAG test server."""
    async with httpx.AsyncClient(base_url=LIGHTRAG_TEST_URL, timeout=60.0) as client:
        yield client

@pytest_asyncio.fixture(scope="function", autouse=True)
async def clean_rag_db(lightrag_client: httpx.AsyncClient):
    """Ensures the LightRAG database is clean before and after each test."""
    await lightrag_client.delete("/documents")
    await wait_for_pipeline_idle(lightrag_client)
    yield
    await lightrag_client.delete("/documents")
    await wait_for_pipeline_idle(lightrag_client)

async def wait_for_document_to_process(client: httpx.AsyncClient, file_name: str):
    """
    Polls the LightRAG documents endpoint until the specified file has a terminal
    status of 'processed' or 'failed'.
    """
    for _ in range(30):
        try:
            list_res = await client.get("/documents")
            list_res.raise_for_status()
            all_docs = []
            for status_group in list_res.json().get("statuses", {}).values():
                all_docs.extend(status_group)

            target_doc = next((doc for doc in all_docs if doc["file_path"].endswith(file_name)), None)

            if target_doc and target_doc["status"] in ["processed", "failed"]:
                if target_doc["status"] == "failed":
                    pytest.fail(f"Document '{file_name}' failed processing in LightRAG: {target_doc.get('error')}")
                return
        except (httpx.RequestError, KeyError):
            pass
        await asyncio.sleep(1)
    pytest.fail(f"Document '{file_name}' did not reach a terminal state in time.")

async def wait_for_pipeline_idle(client: httpx.AsyncClient):
    """Helper to wait for the LightRAG pipeline to become idle."""
    for _ in range(30):
        try:
            status_res = await client.get("/documents/pipeline_status")
            if not status_res.json().get("busy", True):
                return
        except httpx.RequestError:
            pass
        await asyncio.sleep(1)
    pytest.fail("LightRAG pipeline did not become idle in time.")

# --- Tests ---

async def test_list_sources_success(async_client: AsyncClient, lightrag_client: httpx.AsyncClient, mock_get_current_user):
    """Tests listing sources after ingesting a document directly into LightRAG."""
    file_name = "test.txt"
    files = {'file': (file_name, BytesIO(b"test content"), 'text/plain')}
    await lightrag_client.post("/documents/upload", files=files)
    await lightrag_client.post("/documents/scan")
    await wait_for_document_to_process(lightrag_client, file_name)

    headers = {"X-Tenant-ID": "tenant-a"}
    
    response = await async_client.get("/api/v1/knowledge/sources", headers=headers)
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["fileName"] == file_name
    assert data[0]["status"] == "processed"

async def test_delete_source_success(async_client: AsyncClient, lightrag_client: httpx.AsyncClient, mock_get_current_user):
    """Tests deleting a source via our API and confirms its deletion in LightRAG."""
    file_name = "to_delete.txt"
    files = {'file': (file_name, BytesIO(b"delete me"), 'text/plain')}
    await lightrag_client.post("/documents/upload", files=files)
    await lightrag_client.post("/documents/scan")
    await wait_for_document_to_process(lightrag_client, file_name)

    list_res = await lightrag_client.get("/documents")
    doc_id_to_delete = list_res.json()["statuses"]["processed"][0]["id"]

    headers = {"X-Tenant-ID": "tenant-a"}
    
    response = await async_client.delete(f"/api/v1/knowledge/sources/{doc_id_to_delete}", headers=headers)
    
    assert response.status_code == 204
    
    await wait_for_pipeline_idle(lightrag_client)
    final_list_res = await lightrag_client.get("/documents")
    
    # --- THIS IS THE FIX ---
    # Use .get() to safely access the 'processed' key, providing an empty list as a default.
    # This handles the case where the key is missing after the last document is deleted.
    processed_docs = final_list_res.json()["statuses"].get("processed", [])
    assert not processed_docs
    # --- END OF FIX ---

async def test_ingest_guides_success(async_client: AsyncClient, lightrag_client: httpx.AsyncClient, mock_get_current_user):
    """Tests uploading a file through our API and confirms its ingestion in LightRAG."""
    headers = {"X-Tenant-ID": "tenant-a"}
    file_name = "test_guide.txt"
    file_content = b"This is a test guide."
    files = {'files': (file_name, BytesIO(file_content), 'text/plain')}

    response = await async_client.post("/api/v1/knowledge/ingest-guides", files=files, headers=headers)
    
    assert response.status_code == 200
    data = response.json()
    assert data["uploads"][0]["status"] == "success"
    
    await wait_for_document_to_process(lightrag_client, file_name)
    list_res = await lightrag_client.get("/documents")
    assert len(list_res.json()["statuses"]["processed"]) == 1
    assert list_res.json()["statuses"]["processed"][0]["file_path"].endswith(file_name)