"""Unit coverage for :mod:`src.services.nifi_flow_deployment`."""

from __future__ import annotations

from typing import Any, Dict
from unittest.mock import AsyncMock

import pytest

from src.services.nifi_flow_deployment import (
    NiFiFlowDeployment,
)


@pytest.fixture
def deployment_service(mock_nifi_client) -> NiFiFlowDeployment:
    """Return the deployment service under test with a mocked NiFi client."""

    return NiFiFlowDeployment(mock_nifi_client)


@pytest.mark.asyncio
async def test_deploy_flow_success(deployment_service: NiFiFlowDeployment, mock_nifi_client) -> None:
    """A happy-path deployment should report success and include created IDs."""

    mock_nifi_client.parameter_contexts.create_parameter_context = AsyncMock(
        return_value={"id": "param-ctx-123"}
    )
    mock_nifi_client.process_groups.create_process_group = AsyncMock(
        return_value={"id": "pg-123", "revision": {"version": 1, "clientId": "abc"}}
    )
    mock_nifi_client.process_groups.set_parameter_context = AsyncMock()

    deployment_service._deploy_processors = AsyncMock(
        return_value=({"proc-1": "proc-id-1"}, [])
    )
    deployment_service._deploy_connections = AsyncMock(return_value=[])
    deployment_service._validate_components = AsyncMock(return_value=[])

    flow_definition: Dict[str, Any] = {
        "processors": [
            {"name": "TestProcessor", "type": "org.apache.nifi.processor.TestProcessor"}
        ],
        "connections": [],
    }

    result = await deployment_service.deploy_flow(
        flow_definition=flow_definition,
        flow_name="test-flow",
        parameters={"param1": "value1"},
    )

    assert result["success"] is True
    assert result["process_group_id"] == "pg-123"
    assert result["parameter_context_id"] == "param-ctx-123"
    assert not result["failures"], "Expected no deployment failures"


@pytest.mark.asyncio
async def test_deploy_flow_with_component_failures(
    deployment_service: NiFiFlowDeployment, mock_nifi_client
) -> None:
    """Component creation errors should surface and trigger cleanup."""

    mock_nifi_client.parameter_contexts.create_parameter_context = AsyncMock(
        return_value={"id": "param-ctx-123"}
    )
    mock_nifi_client.process_groups.create_process_group = AsyncMock(
        return_value={"id": "pg-123", "revision": {"version": 1, "clientId": "abc"}}
    )
    mock_nifi_client.process_groups.set_parameter_context = AsyncMock()

    deployment_service._deploy_processors = AsyncMock(
        return_value=(
            {},
            [
                {
                    "component_type": "processor",
                    "component_name": "FailedProcessor",
                    "error_type": "creation",
                    "message": "Invalid configuration",
                }
            ],
        )
    )
    deployment_service._deploy_connections = AsyncMock(return_value=[])
    deployment_service._validate_components = AsyncMock(return_value=[])
    deployment_service.cleanup_failed_deployment = AsyncMock()

    result = await deployment_service.deploy_flow(
        flow_definition={"processors": [], "connections": []},
        flow_name="test-flow",
    )

    assert result["success"] is False
    assert len(result["failures"]) == 1
    assert result["failures"][0]["component_name"] == "FailedProcessor"
    deployment_service.cleanup_failed_deployment.assert_called_once()


@pytest.mark.asyncio
async def test_deploy_flow_exception_handling(
    deployment_service: NiFiFlowDeployment, mock_nifi_client
) -> None:
    """Unexpected exceptions should be captured as deployment-level failures."""

    mock_nifi_client.process_groups.create_process_group = AsyncMock(
        side_effect=Exception("NiFi connection failed")
    )

    result = await deployment_service.deploy_flow(
        flow_definition={"processors": [], "connections": []},
        flow_name="test-flow",
    )

    assert result["success"] is False
    assert len(result["failures"]) == 1
    failure = result["failures"][0]
    assert failure["component_type"] == "deployment"
    assert "NiFi connection failed" in failure["message"]
