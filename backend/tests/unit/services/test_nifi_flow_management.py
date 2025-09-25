"""Unit coverage for :mod:`src.services.nifi_flow_management`."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.services.nifi_flow_management import NiFiFlowManagement


@pytest.fixture
def flow_management_service(mock_nifi_client) -> NiFiFlowManagement:
    """Return the flow management service with a mocked NiFi client."""

    return NiFiFlowManagement(mock_nifi_client)


@pytest.mark.asyncio
async def test_start_flow_success(flow_management_service: NiFiFlowManagement) -> None:
    """Starting all processors should yield a running status."""

    flow_management_service._get_processors_in_group = AsyncMock(
        return_value=[
            {"id": "proc-1", "component": {"name": "Processor1"}},
            {"id": "proc-2", "component": {"name": "Processor2"}},
        ]
    )
    flow_management_service.nifi.processors.start_processor = AsyncMock()

    result = await flow_management_service.start_flow("pg-123")

    assert result["success"] is True
    assert result["status"] == "running"
    assert result["total_processors"] == 2
    assert result["started_processors"] == 2
    assert not result["failed_processors"]


@pytest.mark.asyncio
async def test_start_flow_partial_failure(flow_management_service: NiFiFlowManagement) -> None:
    """A processor error should be reported while continuing with others."""

    flow_management_service._get_processors_in_group = AsyncMock(
        return_value=[
            {"id": "proc-1", "component": {"name": "Processor1"}},
            {"id": "proc-2", "component": {"name": "Processor2"}},
        ]
    )
    flow_management_service.nifi.processors.start_processor = AsyncMock(
        side_effect=[None, Exception("Processor configuration invalid")]
    )

    result = await flow_management_service.start_flow("pg-123")

    assert result["success"] is False
    assert result["status"] == "partially_running"
    assert result["started_processors"] == 1
    assert len(result["failed_processors"]) == 1
    assert result["failed_processors"][0]["processor_name"] == "Processor2"


@pytest.mark.asyncio
async def test_get_flow_status(flow_management_service: NiFiFlowManagement) -> None:
    """Gathered processor state should be summarised for operators."""

    flow_management_service.nifi.process_groups.get_process_group = AsyncMock(
        return_value={"component": {"name": "TestFlow"}}
    )
    flow_management_service._get_processors_in_group = AsyncMock(
        return_value=[
            {
                "id": "proc-1",
                "component": {"name": "Processor1", "state": "RUNNING", "validationStatus": "VALID"},
            },
            {
                "id": "proc-2",
                "component": {"name": "Processor2", "state": "STOPPED", "validationStatus": "VALID"},
            },
        ]
    )

    result = await flow_management_service.get_flow_status("pg-123")

    assert result["process_group_id"] == "pg-123"
    assert result["process_group_name"] == "TestFlow"
    assert result["overall_status"] == "partially_running"
    assert result["running_processors"] == 1
    assert result["stopped_processors"] == 1
    assert result["invalid_processors"] == 0
