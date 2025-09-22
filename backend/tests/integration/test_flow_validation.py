import time
import uuid
from typing import Any, Dict

import pytest

from src.core.config import settings
from src.clients.nifi_client import NiFiClient
from src.services.validators.flow_definition_validator import FlowDefinitionValidator


pytestmark = pytest.mark.integration


async def _validate(flow_definition):
    async with NiFiClient(
        settings.NIFI_URL,
        username=settings.NIFI_USERNAME,
        password=settings.NIFI_PASSWORD,
        verify_ssl=settings.VERIFY_SSL,
    ) as client:
        validator = FlowDefinitionValidator(client)
        return await validator.validate(flow_definition, parameters=_test_parameters())


def _build_flow_definition() -> Dict[str, Any]:
    timestamp = int(time.time())
    getfile_id = str(uuid.uuid4())
    update_attr_id = str(uuid.uuid4())
    putfile_id = str(uuid.uuid4())
    conn1_id = str(uuid.uuid4())
    conn2_id = str(uuid.uuid4())

    return {
        "identifier": str(uuid.uuid4()),
        "name": f"Validation Flow {timestamp}",
        "comments": "Flow used for validation tests",
        "position": {"x": 0.0, "y": 0.0},
        "processors": [
            {
                "identifier": getfile_id,
                "name": "Get Input Files",
                "type": "org.apache.nifi.processors.standard.GetFile",
                "bundle": {
                    "group": "org.apache.nifi",
                    "artifact": "nifi-standard-nar",
                    "version": "1.23.2",
                },
                "position": {"x": 100.0, "y": 100.0},
                "properties": {
                    "Input Directory": "#{input_directory}",
                    "File Filter": "#{input_pattern}",
                    "Keep Source File": "false",
                },
                "schedulingPeriod": "1 sec",
                "schedulingStrategy": "TIMER_DRIVEN",
                "concurrentlySchedulableTaskCount": 1,
                "autoTerminatedRelationships": ["failure"],
            },
            {
                "identifier": update_attr_id,
                "name": "Add Processing Metadata",
                "type": "org.apache.nifi.processors.attributes.UpdateAttribute",
                "bundle": {
                    "group": "org.apache.nifi",
                    "artifact": "nifi-update-attribute-nar",
                    "version": "1.23.2",
                },
                "position": {"x": 400.0, "y": 100.0},
                "properties": {
                    "filename": "processed_${filename}",
                    "processing.timestamp": "${now():format('yyyy-MM-dd HH:mm:ss')}",
                    "processing.test_run": f"validation-{timestamp}",
                },
                "schedulingPeriod": "1 sec",
                "schedulingStrategy": "TIMER_DRIVEN",
                "concurrentlySchedulableTaskCount": 1,
                "autoTerminatedRelationships": [],
            },
            {
                "identifier": putfile_id,
                "name": "Write Output Files",
                "type": "org.apache.nifi.processors.standard.PutFile",
                "bundle": {
                    "group": "org.apache.nifi",
                    "artifact": "nifi-standard-nar",
                    "version": "1.23.2",
                },
                "position": {"x": 700.0, "y": 100.0},
                "properties": {
                    "Directory": "#{output_directory}",
                    "Create Missing Directories": "true",
                },
                "schedulingPeriod": "1 sec",
                "schedulingStrategy": "TIMER_DRIVEN",
                "concurrentlySchedulableTaskCount": 1,
                "autoTerminatedRelationships": ["failure", "success"],
            },
        ],
        "connections": [
            {
                "identifier": conn1_id,
                "source": {"id": getfile_id, "type": "PROCESSOR"},
                "destination": {"id": update_attr_id, "type": "PROCESSOR"},
                "selectedRelationships": ["success"],
            },
            {
                "identifier": conn2_id,
                "source": {"id": update_attr_id, "type": "PROCESSOR"},
                "destination": {"id": putfile_id, "type": "PROCESSOR"},
                "selectedRelationships": ["success"],
            },
        ],
        "controllerServices": [],
        "labels": [],
        "funnels": [],
        "variables": {},
        "parameterContextName": f"Validation-Context-{timestamp}",
    }


def _test_parameters() -> Dict[str, str]:
    return {
        "input_directory": "/tmp",
        "output_directory": "/tmp",
        "input_pattern": ".*\\.txt$",
    }


@pytest.mark.asyncio
async def test_flow_validation_catches_invalid_schedule():
    flow_def = _build_flow_definition()
    flow_def["processors"][1]["schedulingStrategy"] = "EVENT_DRIVEN"
    report = await _validate(flow_def)
    assert report["has_errors"], "Validator should flag invalid scheduling"
    assert any(issue["component_type"] == "processor" for issue in report["issues"])


@pytest.mark.asyncio
async def test_flow_validation_passes_for_timer_driven_schedule():
    flow_def = _build_flow_definition()
    for processor in flow_def["processors"]:
        processor["schedulingStrategy"] = "TIMER_DRIVEN"
    report = await _validate(flow_def)
    assert not report["has_errors"], report
