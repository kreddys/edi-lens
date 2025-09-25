"""Integration coverage for the workflow orchestrator using live services."""

from __future__ import annotations

import uuid

import pytest


def _build_sample_flow_definition(unique_suffix: str) -> dict:
    """Create a minimal but valid NiFi flow definition for deployment tests."""

    generate_id = f"generate-{unique_suffix}"
    log_id = f"log-{unique_suffix}"

    return {
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
                    "Custom Text": "integration-test",
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


@pytest.mark.asyncio
async def test_deployment_first_workflow(orchestrator, nifi_client, registry_client) -> None:
    """Exercise the full deployment-first orchestration workflow."""

    unique_suffix = uuid.uuid4().hex[:8]
    flow_definition = _build_sample_flow_definition(unique_suffix)
    flow_name = f"integration-flow-{unique_suffix}"
    bucket_name = f"integration-bucket-{unique_suffix}"
    deployment_parameters = {"greeting": "hello-world", "batch_size": "5"}

    cleanup = {
        "process_groups": [],
        "parameter_contexts": set(),
        "bucket_id": None,
        "bucket_revision": None,
        "flow_id": None,
    }

    try:
        deploy_result = await orchestrator.deploy_and_register_flow(
            flow_definition=flow_definition,
            flow_name=flow_name,
            bucket_name=bucket_name,
            parameters=deployment_parameters,
            comments="Integration test - deployment-first workflow",
        )

        assert deploy_result["success"] is True, f"Deployment failed: {deploy_result}"
        assert deploy_result["workflow"] == "deploy_and_register"
        assert deploy_result["stage"] == "completed"
        assert deploy_result["flow_name"] == flow_name

        process_group_id = deploy_result["process_group_id"]
        bucket_id = deploy_result["bucket_info"]["bucket_id"]
        flow_id = deploy_result["registry_upload"]["flow_id"]

        cleanup["process_groups"].append(process_group_id)
        cleanup["bucket_id"] = bucket_id
        cleanup["bucket_revision"] = deploy_result["bucket_info"].get("revision")
        cleanup["flow_id"] = flow_id

        nifi_deployment = deploy_result["nifi_deployment"]
        assert nifi_deployment["success"] is True
        assert nifi_deployment["process_group_id"] == process_group_id

        parameter_context_id = nifi_deployment.get("parameter_context_id")
        if parameter_context_id:
            cleanup["parameter_contexts"].add(parameter_context_id)

        registry_upload = deploy_result["registry_upload"]
        assert registry_upload["success"] is True
        assert registry_upload["flow_id"] == flow_id
        assert registry_upload.get("version") >= 1

        bucket_info = deploy_result["bucket_info"]
        assert bucket_info["bucket_id"] == bucket_id
        assert bucket_info["bucket_name"] == bucket_name

        overview = await orchestrator.get_flow_overview(process_group_id)
        assert overview["process_group_id"] == process_group_id
        assert overview["is_under_version_control"] is True
        assert overview["has_parameters"] is True
        if parameter_context_id:
            assert overview["parameter_context"]["parameter_context_id"] == parameter_context_id

        start_result = await orchestrator.start_flow_workflow(process_group_id)
        assert start_result["success"] is True
        assert start_result["workflow"] == "start_flow"
        assert start_result["process_group_id"] == process_group_id

        stop_result = await orchestrator.stop_flow_workflow(process_group_id)
        assert stop_result["success"] is True
        assert stop_result["workflow"] == "stop_flow"
        assert stop_result["process_group_id"] == process_group_id

        delete_result = await orchestrator.delete_flow_workflow(
            process_group_id,
            remove_from_registry=True,
        )
        assert delete_result["success"] is True
        assert delete_result["process_group_id"] == process_group_id

        cleanup["process_groups"].remove(process_group_id)
        cleanup["bucket_id"] = None
        cleanup["flow_id"] = None

    finally:
        for process_group_id in cleanup["process_groups"]:
            await orchestrator.nifi_flow_mgmt.delete_flow(process_group_id, force=True)

        for parameter_context_id in cleanup["parameter_contexts"]:
            try:
                await nifi_client.parameter_contexts.delete_parameter_context(parameter_context_id)
            except Exception:
                pass

        if cleanup["flow_id"] and cleanup["bucket_id"]:
            try:
                await registry_client.flows.delete_flow(
                    cleanup["bucket_id"],
                    cleanup["flow_id"],
                )
            except Exception:
                pass

        if cleanup["bucket_id"]:
            try:
                await registry_client.buckets.delete_bucket(
                    cleanup["bucket_id"], cleanup["bucket_revision"]
                )
            except Exception:
                pass
