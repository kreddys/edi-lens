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


async def test_flow_lifecycle_via_api(api_client, nifi_client, registry_client):
    unique_suffix = uuid.uuid4().hex[:8]
    flow_name = f"api-integration-flow-{unique_suffix}"
    bucket_name = f"api-integration-bucket-{unique_suffix}"

    flow_definition = _build_flow_definition(unique_suffix)

    # Create bucket first to get bucket ID
    bucket_payload = {
        "bucket_name": bucket_name,
        "description": "Integration test bucket"
    }
    bucket_response = await api_client.post("/api/flows/registry/buckets", json=bucket_payload)
    assert bucket_response.status_code == 200
    bucket_id = bucket_response.json()["bucket_id"]

    deploy_payload = {
        "bucket_id": bucket_id,
        "flow_definition": flow_definition,
        "parameters": {"greeting": "hello", "batch_size": "10"},
        "parent_group_id": "root",
        "flow_name": flow_name,
        "flow_description": "Integration test flow deployed via API",
    }

    process_group_id = None
    parameter_context_id = None
    try:
        deploy_response = await api_client.post("/api/flows/deploy-and-store", json=deploy_payload)
        assert deploy_response.status_code == 201
        deploy = deploy_response.json()
        assert deploy["success"] is True

        process_group_id = deploy["process_group_id"]
        parameter_context_id = deploy.get("parameter_context_id")

        status_response = await api_client.get(f"/api/flows/{process_group_id}/status")
        assert status_response.status_code == 200
        status = status_response.json()
        assert status["process_group_id"] == process_group_id
        assert status["processor_count"] == 2

        start_response = await api_client.post(f"/api/flows/{process_group_id}/start")
        assert start_response.status_code == 200
        assert start_response.json()["message"] == "Flow started successfully"

        stop_response = await api_client.post(f"/api/flows/{process_group_id}/stop")
        assert stop_response.status_code == 200
        assert stop_response.json()["message"] == "Flow stopped successfully"

        delete_response = await api_client.delete(
            f"/api/flows/{process_group_id}", params={"remove_from_registry": "true"}
        )
        assert delete_response.status_code == 200
        assert delete_response.json()["message"] == "Flow deleted successfully"
        process_group_id = None
    finally:
        if process_group_id:
            try:
                await nifi_client.process_groups.delete_process_group(process_group_id)
            except Exception:
                pass

        await _cleanup_parameter_context(nifi_client, parameter_context_id)
        await _cleanup_bucket(registry_client, bucket_name)


async def test_deploy_flow_with_invalid_connection_returns_actionable_error(
    api_client, nifi_client, registry_client
):
    unique_suffix = uuid.uuid4().hex[:8]
    flow_name = f"api-invalid-connection-flow-{unique_suffix}"
    bucket_name = f"api-invalid-connection-bucket-{unique_suffix}"

    # Create bucket first to get bucket ID
    bucket_payload = {
        "bucket_name": bucket_name,
        "description": "Integration test bucket for invalid connection"
    }
    bucket_response = await api_client.post("/api/flows/registry/buckets", json=bucket_payload)
    assert bucket_response.status_code == 200
    bucket_id = bucket_response.json()["bucket_id"]

    flow_definition = _build_flow_definition(unique_suffix)
    # Introduce an invalid destination that cannot be resolved to verify error details.
    flow_definition["connections"][0]["destination"]["name"] = "missing-destination"
    flow_definition["connections"][0]["destination"]["id"] = "missing-destination"

    payload = {
        "bucket_id": bucket_id,
        "flow_definition": flow_definition,
        "parameters": {},
        "parent_group_id": "root",
        "flow_name": flow_name,
        "flow_description": "Invalid connection integration test",
    }

    detail = await _assert_nifi_deployment_failure(api_client, payload)

    failures = detail["details"]["failures"]
    assert failures, "Expected failures in NiFi deployment error details"

    connection_failure = next(
        (
            failure
            for failure in failures
            if failure["component_type"] == "connection"
            and failure["error_type"] == "resolution"
        ),
        None,
    )
    assert connection_failure is not None
    assert "Unable to resolve connection endpoints" in connection_failure["message"]

    await _cleanup_parameter_context(
        nifi_client, detail["details"].get("parameter_context_id")
    )
    await _cleanup_bucket(registry_client, bucket_name)


async def test_deploy_flow_with_invalid_processor_type_returns_actionable_error(
    api_client, nifi_client, registry_client
):
    unique_suffix = uuid.uuid4().hex[:8]
    flow_name = f"api-invalid-processor-flow-{unique_suffix}"
    bucket_name = f"api-invalid-processor-bucket-{unique_suffix}"

    # Create bucket first to get bucket ID
    bucket_payload = {
        "bucket_name": bucket_name,
        "description": "Integration test bucket for invalid processor"
    }
    bucket_response = await api_client.post("/api/flows/registry/buckets", json=bucket_payload)
    assert bucket_response.status_code == 200
    bucket_id = bucket_response.json()["bucket_id"]

    flow_definition = _build_flow_definition(unique_suffix)
    invalid_processor_type = "org.apache.nifi.processors.standard.DoesNotExist"
    flow_definition["processors"][0]["type"] = invalid_processor_type

    payload = {
        "bucket_id": bucket_id,
        "flow_definition": flow_definition,
        "parameters": {},
        "parent_group_id": "root",
        "flow_name": flow_name,
        "flow_description": "Invalid processor integration test",
    }

    detail = await _assert_nifi_deployment_failure(api_client, payload)

    failures = detail["details"]["failures"]
    assert failures, "Expected processor failures in NiFi deployment error details"

    processor_failure = next(
        (
            failure
            for failure in failures
            if failure["component_type"] == "processor"
            and failure["error_type"] == "creation"
        ),
        None,
    )
    assert processor_failure is not None
    assert processor_failure["details"].get("processor_type") == invalid_processor_type
    assert processor_failure["message"], "Expected processor failure message to be populated"

    await _cleanup_parameter_context(
        nifi_client, detail["details"].get("parameter_context_id")
    )
    await _cleanup_bucket(registry_client, bucket_name)


async def test_deploy_flow_with_invalid_parameter_value_returns_actionable_error(
    api_client, nifi_client, registry_client
):
    unique_suffix = uuid.uuid4().hex[:8]
    parameter_name = f"batch_size_{unique_suffix}"
    flow_name = f"api-invalid-parameter-flow-{unique_suffix}"
    bucket_name = f"api-invalid-parameter-bucket-{unique_suffix}"

    # Create bucket first to get bucket ID
    bucket_payload = {
        "bucket_name": bucket_name,
        "description": "Integration test bucket for invalid parameter"
    }
    bucket_response = await api_client.post("/api/flows/registry/buckets", json=bucket_payload)
    assert bucket_response.status_code == 200
    bucket_id = bucket_response.json()["bucket_id"]

    flow_definition = _build_flow_definition_with_parameter(unique_suffix, parameter_name)

    payload = {
        "bucket_id": bucket_id,
        "flow_definition": flow_definition,
        "parameters": {parameter_name: "not-a-number"},
        "parent_group_id": "root",
        "flow_name": flow_name,
        "flow_description": "Invalid parameter integration test",
    }

    detail = await _assert_nifi_deployment_failure(api_client, payload)

    failures = detail["details"].get("failures", [])
    assert failures, "Expected deployment failures when parameter value is invalid"

    validation_failure = next(
        (
            failure
            for failure in failures
            if failure["component_type"] == "processor"
            and failure["error_type"] == "validation"
        ),
        None,
    )
    assert validation_failure is not None

    validation_errors = validation_failure["details"].get("validation_errors", [])
    assert validation_errors, "Expected validation errors in failure details"
    assert any(parameter_name in error or "Batch Size" in error for error in validation_errors)

    # The deployment should also include a summary to help operators triage the issue.
    summary = detail["details"].get("summary", {})
    assert summary.get("failed_processors", 0) >= 1

    await _cleanup_parameter_context(
        nifi_client, detail["details"].get("parameter_context_id")
    )
    await _cleanup_bucket(registry_client, bucket_name)
