# FILE: backend/tests/api/test_enrichment_api.py
import pytest
import asyncio
from httpx import AsyncClient

from src.main import app
from src.core.auth import User, RealmAccess, get_current_user

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]

@pytest.fixture
def superuser_user():
    """A superuser with permission to run enrichment."""
    return User(
        sub="mock-superuser-id-789",
        preferred_username="test-superuser",
        groups=["tenant-a"],
        realm_access=RealmAccess(roles=["superuser"])
    )

@pytest.fixture
def mock_get_current_user(superuser_user):
    """Mocks the get_current_user dependency."""
    app.dependency_overrides[get_current_user] = lambda: superuser_user
    yield
    del app.dependency_overrides[get_current_user]

async def test_enrichment_analysis_workflow(async_client: AsyncClient, mock_get_current_user):
    """
    Tests the full asynchronous workflow:
    1. Start an analysis job.
    2. Poll for its status until it completes.
    3. Verify the final result.
    """
    headers = {"X-Tenant-ID": "tenant-a"}
    request_data = {
        "schema_name": "837.5010.X222.A1.json",
        "segment_id": "CLM",
        "context_id": "2300.CLM"
    }

    # 1. Start the job
    response = await async_client.post("/api/v1/enrichment/analyze", json=request_data, headers=headers)
    assert response.status_code == 202
    data = response.json()
    assert "job_id" in data
    job_id = data["job_id"]

    # 2. Poll for completion
    final_status = None
    for _ in range(60): # Poll for up to 60 seconds
        await asyncio.sleep(1)
        status_response = await async_client.get(f"/api/v1/enrichment/status/{job_id}", headers=headers)
        assert status_response.status_code == 200
        status_data = status_response.json()
        
        if status_data["status"] in ["complete", "failed"]:
            final_status = status_data
            break
    
    assert final_status is not None, "Job did not complete within timeout."
    
    # 3. Verify the result
    assert final_status["status"] == "complete"
    assert final_status["error"] is None
    assert final_status["result"] is not None
    
    result = final_status["result"]
    assert "reasoning" in result
    assert "patches" in result
    # We expect the agent to find a missing definition and propose a patch
    assert len(result["patches"]) > 0
    assert result["patches"][0]["op"] == "add"
    assert result["patches"][0]["path"] == "/segmentDefinitions/CLM"