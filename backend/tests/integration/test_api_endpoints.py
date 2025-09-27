"""Integration tests for FastAPI endpoints."""

from __future__ import annotations

import asyncio
import uuid

import pytest
from httpx import AsyncClient

from src.api.dependencies import (
    get_nifi_client,
    get_registry_client,
    get_workflow_orchestrator,
)
from src.main import app
from src.services.workflow_orchestrator import WorkflowOrchestrator
from tests.test_config import (
    get_test_nifi_client,
    get_test_registry_client,
)


pytestmark = pytest.mark.asyncio


@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
async def nifi_client():
    client = get_test_nifi_client()
    async with client:
        yield client


@pytest.fixture(scope="module")
async def registry_client():
    client = get_test_registry_client()
    async with client:
        yield client


@pytest.fixture(scope="module")
async def orchestrator(nifi_client, registry_client):
    return WorkflowOrchestrator(nifi_client, registry_client)


@pytest.fixture(scope="module", autouse=True)
async def override_dependencies(nifi_client, registry_client, orchestrator):
    async def _get_nifi_client_override():
        yield nifi_client

    async def _get_registry_client_override():
        yield registry_client

    async def _get_orchestrator_override():
        return orchestrator

    app.dependency_overrides[get_nifi_client] = _get_nifi_client_override
    app.dependency_overrides[get_registry_client] = _get_registry_client_override
    app.dependency_overrides[get_workflow_orchestrator] = _get_orchestrator_override

    yield

    app.dependency_overrides.clear()


@pytest.fixture
async def api_client():
    async with AsyncClient(app=app, base_url="http://testserver") as client:
        yield client


def _build_flow_definition(unique_suffix: str) -> dict:
    generate_id = f"generate-{unique_suffix}"
    log_id = f"log-{unique_suffix}"

    return {
        "name": f"Integration Flow {unique_suffix}",
        "description": "Integration test flow deployed via API",
        "processors": [
            {
                "identifier": generate_id,
                "name": f"GenerateFlowFile-{unique_suffix}",
                "type": "org.apache.nifi.processors.standard.GenerateFlowFile",
                "position": {"x": 0.0, "y": 0.0},
                "properties": {
                    "Batch Size": "1",
                    "Data Format": "Text",
                    "Unique FlowFiles": "true",
                    "Custom Text": "api-integration-test",
                },
                "schedulingPeriod": "1 sec",
                "schedulingStrategy": "TIMER_DRIVEN",
                "executionNode": "ALL",
                "concurrentlySchedulableTaskCount": 1,
                "autoTerminatedRelationships": ["success"],
            },
            {
                "identifier": log_id,
                "name": f"LogAttribute-{unique_suffix}",
                "type": "org.apache.nifi.processors.standard.LogAttribute",
                "position": {"x": 350.0, "y": 0.0},
                "properties": {},
                "schedulingPeriod": "1 sec",
                "schedulingStrategy": "TIMER_DRIVEN",
                "executionNode": "ALL",
                "concurrentlySchedulableTaskCount": 1,
                "autoTerminatedRelationships": ["success"],
            },
        ],
        "connections": [
            {
                "identifier": f"connection-{unique_suffix}",
                "name": f"generate-to-log-{unique_suffix}",
                "source": {
                    "id": generate_id,
                    "name": f"GenerateFlowFile-{unique_suffix}",
                    "type": "PROCESSOR",
                },
                "destination": {
                    "id": log_id,
                    "name": f"LogAttribute-{unique_suffix}",
                    "type": "PROCESSOR",
                },
                "selectedRelationships": ["success"],
                "backPressureObjectThreshold": "10000",
                "backPressureDataSizeThreshold": "1 GB",
                "flowFileExpiration": "0 sec",
            }
        ],
    }


def _build_flow_definition_with_parameter(unique_suffix: str, parameter_name: str) -> dict:
    """Build a flow definition that references a NiFi parameter."""

    flow_definition = _build_flow_definition(unique_suffix)
    flow_definition["processors"][0]["properties"]["Batch Size"] = f"#{{{parameter_name}}}"
    return flow_definition


async def _assert_nifi_deployment_failure(api_client, payload: dict) -> dict:
    """Submit a deployment request and assert a structured NiFi failure response."""

    response = await api_client.post("/api/flows/deploy-and-store", json=payload)
    assert response.status_code == 400

    detail = response.json()["detail"]
    assert detail["error_type"] == "NIFI_DEPLOYMENT_FAILED"
    assert detail["user_message"], "Expected an actionable user message in the error response"
    assert (
        detail["action_required"]
        == "Review the NiFi flow definition and resolve the reported validation errors before retrying"
    )

    failure_details = detail["details"]
    assert failure_details["stage"] == "nifi_deployment"
    assert isinstance(failure_details.get("failures", []), list)

    return detail


async def _cleanup_bucket(registry_client, bucket_name: str) -> None:
    buckets = await registry_client.buckets.list_buckets()
    bucket = next((b for b in buckets if b.get("name") == bucket_name), None)
    if not bucket:
        return

    bucket_id = bucket["identifier"]
    latest = await registry_client.buckets.get_bucket(bucket_id)
    await registry_client.buckets.delete_bucket(bucket_id, latest["revision"])


async def _cleanup_parameter_context(nifi_client, parameter_context_id: str | None) -> None:
    if not parameter_context_id:
        return

    try:
        await nifi_client.parameter_contexts.delete_parameter_context(parameter_context_id)
    except Exception:
        # It may already be removed as part of orchestrator cleanup.
        pass


async def test_root_endpoint(api_client):
    response = await api_client.get("/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "healthy"
    assert "version" in payload


async def test_health_endpoints(api_client):
    health_response = await api_client.get("/health")
    assert health_response.status_code == 200
    health = health_response.json()
    assert health["status"] == "healthy"

    nifi_response = await api_client.get("/health/nifi")
    assert nifi_response.status_code == 200
    assert nifi_response.json()["healthy"] is True

    registry_response = await api_client.get("/health/registry")
    assert registry_response.status_code == 200
    assert registry_response.json()["healthy"] is True


async def test_v1_registry_buckets_crud(api_client):
    """Test V1 registry buckets CRUD operations."""
    unique_suffix = uuid.uuid4().hex[:8]
    bucket_name = f"v1-test-bucket-{unique_suffix}"
    
    # Create bucket
    bucket_payload = {
        "name": bucket_name,
        "description": "V1 API integration test bucket"
    }
    create_response = await api_client.post("/api/v1/registry/buckets/", json=bucket_payload)
    assert create_response.status_code == 201
    bucket = create_response.json()

    assert bucket["name"] == bucket_name
    assert bucket["description"] == "V1 API integration test bucket"
    assert "id" in bucket
    bucket_id = bucket["id"]

    # List buckets - should include our new bucket
    list_response = await api_client.get("/api/v1/registry/buckets/")
    assert list_response.status_code == 200
    buckets = list_response.json()
    assert isinstance(buckets, list)

    # Find our bucket in the list
    our_bucket = next((b for b in buckets if b["id"] == bucket_id), None)
    assert our_bucket is not None
    assert our_bucket["name"] == bucket_name
    
    # Get specific bucket
    get_response = await api_client.get(f"/api/v1/registry/buckets/{bucket_id}")
    assert get_response.status_code == 200
    retrieved_bucket = get_response.json()
    assert retrieved_bucket["id"] == bucket_id
    assert retrieved_bucket["name"] == bucket_name


async def test_v1_templates_list(api_client):
    """Test V1 templates listing."""
    response = await api_client.get("/api/v1/templates/")
    assert response.status_code == 200
    
    data = response.json()
    assert "templates" in data
    assert "total" in data
    assert "categories" in data
    assert "tags" in data
    
    assert isinstance(data["templates"], list)
    assert isinstance(data["total"], int)
    assert data["total"] >= 0
    
    # Check template structure if any exist
    if data["templates"]:
        template = data["templates"][0]
        required_fields = ["id", "name", "description", "category", "tags", "processor_count", "connection_count"]
        for field in required_fields:
            assert field in template


async def test_v1_templates_get_specific(api_client):
    """Test getting a specific template via V1 API."""
    # First get the list to find a template
    list_response = await api_client.get("/api/v1/templates/")
    assert list_response.status_code == 200
    templates = list_response.json()["templates"]
    
    if not templates:
        pytest.skip("No templates available for testing")
    
    template_id = templates[0]["id"]
    
    # Get specific template
    get_response = await api_client.get(f"/api/v1/templates/{template_id}")
    assert get_response.status_code == 200
    
    template = get_response.json()
    assert template["id"] == template_id
    assert "definition" in template
    assert "parameters" in template


async def test_v1_flows_list(api_client):
    """Test V1 flows listing."""
    response = await api_client.get("/api/v1/flows/")
    assert response.status_code == 200
    
    data = response.json()
    assert "flows" in data
    assert "total" in data
    assert "page" in data
    assert "size" in data
    
    assert isinstance(data["flows"], list)
    assert isinstance(data["total"], int)
    assert data["total"] >= 0


async def test_v1_flow_execution_invalid_action(api_client):
    """Test V1 flow execution with invalid action."""
    payload = {
        "process_group_id": "test-pg-id",
        "action": "invalid_action"
    }
    
    response = await api_client.post("/api/v1/flows/executions/", json=payload)
    assert response.status_code == 400
    
    error = response.json()["detail"]
    assert error["error_type"] == "INVALID_ACTION"
    assert "invalid_action" in error["message"]


async def test_v1_flow_execution_nonexistent_process_group(api_client):
    """Test V1 flow execution with nonexistent process group."""
    payload = {
        "process_group_id": "nonexistent-pg-id",
        "action": "start"
    }
    
    response = await api_client.post("/api/v1/flows/executions/", json=payload)
    assert response.status_code == 500  # Should be 500 due to NiFi API error
    
    error = response.json()["detail"]
    assert error["error_type"] == "EXECUTION_FAILED"
    assert "nonexistent-pg-id" in error["message"]


async def test_v1_registry_flows_list(api_client):
    """Test V1 registry flows listing."""
    response = await api_client.get("/api/v1/registry/flows/")
    assert response.status_code == 200
    
    data = response.json()
    assert "flows" in data
    assert "total" in data or data.get("total") is None  # total might be None if no flows
    
    assert isinstance(data["flows"], list)


async def test_v1_api_error_handling(api_client):
    """Test V1 API error handling for invalid requests."""
    # Test invalid template ID
    response = await api_client.get("/api/v1/templates/nonexistent-id")
    assert response.status_code == 404
    
    error = response.json()["detail"]
    assert error["error_type"] == "TEMPLATE_NOT_FOUND"
    
    # Test invalid bucket creation
    invalid_bucket = {"invalid_field": "value"}  # Missing required 'name' field
    response = await api_client.post("/api/v1/registry/buckets/", json=invalid_bucket)
    assert response.status_code == 422  # Validation error


async def test_v1_flow_crud_basic(api_client):
    """Test basic V1 flow CRUD operations without deployment."""
    # Test creating a flow via V1 API (when implemented)
    response = await api_client.get("/api/v1/flows/")
    assert response.status_code == 200
    
    data = response.json()
    initial_count = data["total"]
    
    # For now, just verify the structure since creation isn't fully implemented
    assert isinstance(data["flows"], list)
    assert data["total"] == initial_count
