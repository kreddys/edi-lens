# FILE: backend/tests/agents/test_end_to_end_rag_agent_integration.py
import pytest
import pytest_asyncio
import httpx
import asyncio
import logging
import os
from pathlib import Path
from typing import AsyncGenerator

from src.agents.crews import SchemaEnrichmentCrews
from tests.agents.agent_test_utils import run_iterative_validation_process

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]
logger = logging.getLogger(__name__)

LIGHTRAG_TEST_URL = "http://lightrag-server-test:9621"

# --- Helper functions to manage the RAG service ---

async def wait_for_pipeline_completion(client: httpx.AsyncClient):
    """
    Waits for the LightRAG pipeline to finish processing documents.
    This is now more robust to handle startup delays.
    """
    logger.info("Waiting for RAG pipeline to start processing...")
    job_started = False
    # Poll for up to 10 seconds for the job to start
    for i in range(10):
        try:
            status_response = await client.get("/documents/pipeline_status")
            status_data = status_response.json()
            if status_data.get("busy", False):
                logger.info(f"Pipeline is now busy. (Attempt {i+1}/10)")
                job_started = True
                break
        except httpx.RequestError as e:
            logger.warning(f"Request to pipeline_status failed: {e}")
        await asyncio.sleep(1)

    # If the job never started, it could be that it finished incredibly quickly.
    # We'll proceed to the next stage, which will catch if it's truly stuck.
    if not job_started:
        logger.warning("Pipeline did not appear to start. It may have finished too quickly to detect. Continuing...")

    logger.info("Waiting for RAG pipeline to become idle (finish processing)...")
    # Poll for up to 60 seconds for the job to complete.
    for i in range(60):
        try:
            status_response = await client.get("/documents/pipeline_status")
            status_data = status_response.json()
            if not status_data.get("busy", True):
                logger.info(f"Pipeline is now idle. Processing complete. (Attempt {i+1}/60)")
                return # Success
        except httpx.RequestError as e:
            logger.warning(f"Request to pipeline_status failed: {e}")
        await asyncio.sleep(1)

    pytest.fail("Pipeline did not become idle within the timeout period.")


async def upload_file(client: httpx.AsyncClient, file_path: Path):
    """Uploads a single file to LightRAG's input directory."""
    logger.info(f"Uploading file: {file_path.name}...")
    with open(file_path, "rb") as f:
        files = {"file": (file_path.name, f, "text/plain")}
        upload_response = await client.post("/documents/upload", files=files)
        assert upload_response.status_code == 200, f"Upload failed: {upload_response.text}"

# --- Pytest Fixtures ---

@pytest.fixture(scope="module", autouse=True)
def check_llm_api_keys():
    """Skips this entire test module if no LLM API key is configured."""
    api_keys_present = any([
        os.getenv("OPENAI_API_KEY"),
        os.getenv("ANTHROPIC_API_KEY"),
        os.getenv("OPENROUTER_API_KEY"),
        os.getenv("GROQ_API_KEY")
    ])
    if not api_keys_present:
        pytest.skip("Skipping agent tests: No LLM API key found in .env.test")

@pytest_asyncio.fixture(scope="module")
async def lightrag_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Provides an HTTPX client for interacting with the LightRAG test server."""
    async with httpx.AsyncClient(base_url=LIGHTRAG_TEST_URL, timeout=120.0) as client:
        yield client

@pytest_asyncio.fixture(scope="module", autouse=True)
async def setup_rag_knowledge_base(lightrag_client: httpx.AsyncClient):
    """
    A module-level fixture that cleans, uploads, and scans documents ONCE.
    This is much more efficient.
    """
    logger.info("\n--- [RAG E2E Setup] Preparing LightRAG for agent tests ---")
    
    # 1. Clean up any previous data
    delete_response = await lightrag_client.delete("/documents")
    delete_response.raise_for_status()
    await wait_for_pipeline_completion(lightrag_client)

    # 2. Upload ALL knowledge files
    complex_guide_path = Path(__file__).parent.parent.parent / "data/knowledge/complex_guide.txt"
    super_complex_guide_path = Path(__file__).parent.parent.parent / "data/knowledge/super_complex_guide.txt"
    
    await upload_file(lightrag_client, complex_guide_path)
    await upload_file(lightrag_client, super_complex_guide_path)
    
    # 3. Trigger ONE scan for all uploaded files
    logger.info(f"Triggering a single scan for all uploaded documents...")
    scan_response = await lightrag_client.post("/documents/scan")
    assert scan_response.status_code == 200, f"Scan trigger failed: {scan_response.text}"
    
    # 4. Wait for the single scan job to finish
    await wait_for_pipeline_completion(lightrag_client)
    
    logger.info("--- [RAG E2E Setup] Knowledge base is ready ---")
    yield
    # No cleanup needed here as it's done at the start of the next run

# --- Test Cases ---

@pytest.mark.asyncio
async def test_agent_proposes_base_schema_addition_from_rag(async_client, setup_rag_knowledge_base):
    """
    Tests if the agent can read from the RAG that an element is missing from a
    base segment definition and propose a patch to add it.
    
    Instruction from RAG: "the base definition of the CLM segment is missing the
    crucial 'Release of Information' element, CLM09."
    """
    crews = SchemaEnrichmentCrews()
    # Point the agent's RAG tool to the test server
    crews.rag_tool.LIGHTRAG_API_URL = LIGHTRAG_TEST_URL
    
    inputs = {"segment_id": "CLM", "context_id": "2300.CLM"}
    response = run_iterative_validation_process(crews, inputs)
    
    assert response.approved is True, f"Auditor rejected the proposal: {response.justification}"

@pytest.mark.asyncio
async def test_agent_proposes_contextual_override_from_rag(async_client, setup_rag_knowledge_base):
    """
    Tests if the agent can read a contextual rule from the RAG and
    propose a patch to enforce it.
    
    Instruction from RAG: "...the NM1 segment's NM102 element (Entity Type Qualifier)
    is situational but it is a business requirement that it must be required."
    """
    crews = SchemaEnrichmentCrews()
    crews.rag_tool.LIGHTRAG_API_URL = LIGHTRAG_TEST_URL
    
    # Target the NM1 segment within the Billing Provider loop (2010AA)
    inputs = {"segment_id": "NM1", "context_id": "2010AA.NM1"} 
    response = run_iterative_validation_process(crews, inputs)
    
    assert response.approved is True, f"Auditor rejected the proposal: {response.justification}"