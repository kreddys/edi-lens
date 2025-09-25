"""Unit coverage for :mod:`src.services.workflow_orchestrator`."""

from __future__ import annotations

from typing import Any, Dict
from unittest.mock import AsyncMock

import pytest

from src.services.workflow_orchestrator import WorkflowOrchestrator


@pytest.fixture
def orchestrator(mock_nifi_client, mock_registry_client) -> WorkflowOrchestrator:
    """Return the orchestrator with mocked NiFi and Registry clients."""

    return WorkflowOrchestrator(mock_nifi_client, mock_registry_client)


@pytest.mark.asyncio
async def test_deploy_and_register_flow_success(orchestrator: WorkflowOrchestrator) -> None:
    """Deploy and register workflow should succeed when dependencies succeed."""

    orchestrator.nifi_deployment.deploy_flow = AsyncMock(
        return_value={
            "success": True,
            "process_group_id": "pg-123",
            "parameter_context_id": "param-ctx-123",
            "summary": {"total_processors": 2, "created_processors": 2},
        }
    )
    orchestrator.registry_bucket_mgmt.get_or_create_bucket = AsyncMock(
        return_value={"bucket_id": "bucket-123", "bucket_name": "test-bucket"}
    )
    orchestrator.integration_bridge.upload_flow_to_registry = AsyncMock(
        return_value={
            "success": True,
            "flow_id": "flow-123",
            "version": 1,
            "created_timestamp": 1234567890,
        }
    )

    result = await orchestrator.deploy_and_register_flow(
        flow_definition={"processors": [], "connections": []},
        flow_name="test-flow",
        bucket_name="test-bucket",
    )

    assert result["success"] is True
    assert result["stage"] == "completed"
    assert result["process_group_id"] == "pg-123"
    assert "nifi_deployment" in result
    assert "registry_upload" in result


@pytest.mark.asyncio
async def test_deploy_and_register_flow_nifi_failure(orchestrator: WorkflowOrchestrator) -> None:
    """NiFi deployment failures should short circuit the workflow."""

    orchestrator.nifi_deployment.deploy_flow = AsyncMock(
        return_value={
            "success": False,
            "failures": [
                {"component_type": "processor", "message": "Invalid configuration"}
            ],
        }
    )

    result = await orchestrator.deploy_and_register_flow(
        flow_definition={"processors": [], "connections": []},
        flow_name="test-flow",
        bucket_name="test-bucket",
    )

    assert result["success"] is False
    assert result["stage"] == "nifi_deployment"
    assert "Flow deployment to NiFi failed" in result["message"]


@pytest.mark.asyncio
async def test_deploy_and_register_flow_registry_failure(orchestrator: WorkflowOrchestrator) -> None:
    """Registry upload errors should be reported while keeping NiFi identifiers."""

    orchestrator.nifi_deployment.deploy_flow = AsyncMock(
        return_value={
            "success": True,
            "process_group_id": "pg-123",
            "summary": {"total_processors": 1},
        }
    )
    orchestrator.registry_bucket_mgmt.get_or_create_bucket = AsyncMock(
        return_value={"bucket_id": "bucket-123", "bucket_name": "test-bucket"}
    )
    orchestrator.integration_bridge.upload_flow_to_registry = AsyncMock(
        side_effect=Exception("Registry connection failed")
    )

    result = await orchestrator.deploy_and_register_flow(
        flow_definition={"processors": [], "connections": []},
        flow_name="test-flow",
        bucket_name="test-bucket",
    )

    assert result["success"] is False
    assert result["stage"] == "registry_upload"
    assert "Registry upload failed" in result["message"]
    assert result["process_group_id"] == "pg-123"
