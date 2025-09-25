"""Integration tests for FastAPI routes backed by real NiFi and Registry clients."""

from __future__ import annotations

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

pytestmark = pytest.mark.asyncio


@pytest.fixture(scope="module", autouse=True)
async def override_dependencies(nifi_client, registry_client, orchestrator: WorkflowOrchestrator):
    """Override FastAPI dependencies with the integration-grade fixtures."""

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
async def api_client() -> AsyncClient:
    """Return an HTTPX client bound to the FastAPI test application."""

    async with AsyncClient(app=app, base_url="http://testserver") as client:
        yield client


def _build_flow_definition(unique_suffix: str) -> dict:
    """Construct a minimal flow definition for deployment endpoints."""

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
    """Re-use the base definition while referencing a NiFi parameter."""

    flow_definition = _build_flow_definition(unique_suffix)
    flow_definition["processors"][0]["properties"]["Batch Size"] = f"#{{{parameter_name}}}"
    return flow_definition


async def _post_and_assert_validation_error(api_client: AsyncClient, payload: dict) -> dict:
    """Helper to assert the API returns FastAPI validation errors."""

    response = await api_client.post("/api/flows/deploy-and-store", json=payload)
    assert response.status_code == 422

    detail = response.json()["detail"]
    assert isinstance(detail, list)
    return detail


async def _delete_flow(api_client: AsyncClient, process_group_id: str, *, remove_from_registry: bool = True) -> None:
    """Delete a flow via the API and assert success."""

    response = await api_client.delete(
        f"/api/flows/{process_group_id}",
        params={"remove_from_registry": remove_from_registry},
    )
    assert response.status_code == 200
    assert response.json()["process_group_id"] == process_group_id


async def test_deploy_and_store_flow(api_client: AsyncClient) -> None:
    """Full deployment workflow should respond with NiFi and Registry metadata."""

    unique_suffix = uuid.uuid4().hex[:8]
    payload = {
        "flow_definition": _build_flow_definition(unique_suffix),
        "flow_name": f"api-integration-{unique_suffix}",
        "bucket_id": f"api-integration-{unique_suffix}",
        "comments": "Integration test deployment",
        "parameters": {"batch_size": "1"},
    }

    response = await api_client.post("/api/flows/deploy-and-store", json=payload)
    assert response.status_code == 201

    body = response.json()
    assert body["success"] is True
    assert body["stage"] == "completed"
    assert body["process_group_id"]
    assert body["flow_id"]

    await _delete_flow(api_client, body["process_group_id"], remove_from_registry=True)


async def test_deploy_flow_validation_error(api_client: AsyncClient) -> None:
    """Invalid processor types should generate a helpful error payload."""

    unique_suffix = uuid.uuid4().hex[:8]
    payload = {
        "flow_definition": {
            "processors": [
                {
                    "identifier": f"invalid-{unique_suffix}",
                    "name": f"InvalidProcessor-{unique_suffix}",
                    "type": "org.apache.nifi.processors.Invalid",
                    "position": {"x": 0.0, "y": 0.0},
                }
            ],
            "connections": [],
        },
        "flow_name": f"invalid-flow-{unique_suffix}",
        "bucket_id": f"invalid-bucket-{unique_suffix}",
    }

    detail = await _post_and_assert_validation_error(api_client, payload)
    assert any(item["loc"][-1] == "name" for item in detail)


async def test_deploy_flow_with_parameters(api_client: AsyncClient) -> None:
    """Parameters referenced in the definition should be persisted."""

    unique_suffix = uuid.uuid4().hex[:8]
    parameter_name = f"batch_size_{unique_suffix}"
    payload = {
        "flow_definition": _build_flow_definition_with_parameter(unique_suffix, parameter_name),
        "flow_name": f"parameter-flow-{unique_suffix}",
        "bucket_id": f"parameter-bucket-{unique_suffix}",
        "parameters": {parameter_name: "10"},
    }

    response = await api_client.post("/api/flows/deploy-and-store", json=payload)
    assert response.status_code == 201

    body = response.json()
    assert body["success"] is True
    assert body["parameter_context_id"], "Parameter context id should be returned"

    await _delete_flow(api_client, body["process_group_id"], remove_from_registry=True)


async def test_delete_flow(api_client: AsyncClient) -> None:
    """Deleting a process group should clean up NiFi resources."""

    unique_suffix = uuid.uuid4().hex[:8]
    deploy_payload = {
        "flow_definition": _build_flow_definition(unique_suffix),
        "flow_name": f"delete-flow-{unique_suffix}",
        "bucket_id": f"delete-bucket-{unique_suffix}",
    }

    deploy_response = await api_client.post("/api/flows/deploy-and-store", json=deploy_payload)
    assert deploy_response.status_code == 201

    deploy_body = deploy_response.json()
    process_group_id = deploy_body["process_group_id"]

    delete_response = await api_client.delete(f"/api/flows/{process_group_id}")
    assert delete_response.status_code == 200

    delete_body = delete_response.json()
    assert delete_body["message"] == "Flow deleted successfully"
    assert delete_body["process_group_id"] == process_group_id
