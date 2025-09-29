"""Integration tests for orchestrating NiFi and Registry interactions."""

import uuid

import pytest

from src.services.workflow_orchestrator import WorkflowOrchestrator
from tests.test_config import (
    get_test_nifi_client,
    get_test_registry_client,
)


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
@pytest.mark.integration
async def test_deployment_first_workflow():
    """Test the deployment-first workflow architecture."""

    unique_suffix = uuid.uuid4().hex[:8]
    flow_definition = _build_sample_flow_definition(unique_suffix)
    flow_name = f"integration-flow-{unique_suffix}"
    bucket_name = f"integration-bucket-{unique_suffix}"

    deployment_parameters = {"greeting": "hello-world", "batch_size": "5"}

    nifi_client = get_test_nifi_client()
    registry_client = get_test_registry_client()

    async with nifi_client:
        async with registry_client:
            orchestrator = WorkflowOrchestrator(nifi_client, registry_client)

            cleanup = {
                "process_groups": [],
                "parameter_contexts": set(),
                "bucket_id": None,
                "flow_id": None,
            }

            try:
                # Test 1: Deploy and Register Flow (main deployment-first workflow)
                deploy_result = await orchestrator.deploy_and_register_flow(
                    flow_definition=flow_definition,
                    flow_name=flow_name,
                    bucket_name=bucket_name,
                    parameters=deployment_parameters,
                    comments="Integration test - deployment-first workflow",
                )

                # Validate deployment success
                assert deploy_result["success"] is True, f"Deployment failed: {deploy_result}"
                assert deploy_result["workflow"] == "deploy_and_register"
                assert deploy_result["stage"] == "completed"
                assert deploy_result["flow_name"] == flow_name

                # Extract key IDs for further testing
                process_group_id = deploy_result["process_group_id"]
                bucket_id = deploy_result["bucket_info"]["bucket_id"]
                flow_id = deploy_result["registry_upload"]["flow_id"]
                
                cleanup["process_groups"].append(process_group_id)
                cleanup["bucket_id"] = bucket_id
                cleanup["flow_id"] = flow_id

                # Validate NiFi deployment details
                nifi_deployment = deploy_result["nifi_deployment"]
                assert nifi_deployment["success"] is True
                assert nifi_deployment["process_group_id"] == process_group_id
                
                parameter_context_id = nifi_deployment.get("parameter_context_id")
                if parameter_context_id:
                    cleanup["parameter_contexts"].add(parameter_context_id)

                # Validate Registry upload details
                registry_upload = deploy_result["registry_upload"]
                assert registry_upload["success"] is True
                assert registry_upload["flow_id"] == flow_id
                assert registry_upload.get("version") >= 1

                # Validate bucket creation
                bucket_info = deploy_result["bucket_info"]
                assert bucket_info["bucket_id"] == bucket_id
                assert bucket_info["bucket_name"] == bucket_name

                # Test 2: Get Flow Overview
                overview = await orchestrator.get_flow_overview(process_group_id)
                assert overview["process_group_id"] == process_group_id
                assert overview["is_under_version_control"] is True
                assert overview["has_parameters"] is True
                
                if parameter_context_id:
                    assert overview["parameter_context"]["parameter_context_id"] == parameter_context_id

                # Test 3: Flow Operations (Start/Stop)
                start_result = await orchestrator.start_flow_workflow(process_group_id)
                assert start_result["success"] is True
                assert start_result["workflow"] == "start_flow"
                assert start_result["process_group_id"] == process_group_id

                stop_result = await orchestrator.stop_flow_workflow(process_group_id)
                assert stop_result["success"] is True
                assert stop_result["workflow"] == "stop_flow"

                # Test 4: Version Control Operations
                comparison = await orchestrator.integration_bridge.compare_with_registry(
                    process_group_id
                )
                assert comparison["bucket_id"] == bucket_id
                assert comparison["flow_id"] == flow_id

                # Test 5: List All Flows
                listings = await orchestrator.list_all_flows()
                assert any(
                    flow["process_group_id"] == process_group_id
                    for flow in listings["nifi_flows"]
                )
                assert any(
                    flow["flow_id"] == flow_id for flow in listings["registry_flows"]
                )
                assert any(
                    bucket["bucket_id"] == bucket_id
                    for bucket in listings["registry_buckets"]
                )

                # Test 6: Delete Flow
                delete_result = await orchestrator.delete_flow_workflow(
                    process_group_id,
                    remove_from_registry=True,  # Test full cleanup
                )
                assert delete_result["success"] is True
                assert delete_result["workflow"] == "delete_flow"
                cleanup["process_groups"].remove(process_group_id)

                # Clean up bucket (it should be empty now)
                latest_bucket = await registry_client.buckets.get_bucket(bucket_id)
                await registry_client.buckets.delete_bucket(
                    bucket_id, latest_bucket["revision"]
                )
                cleanup["bucket_id"] = None
                cleanup["flow_id"] = None

                # Clean up parameter contexts
                for context_id in list(cleanup["parameter_contexts"]):
                    await orchestrator.nifi_param_mgmt.delete_parameter_context(context_id)
                    cleanup["parameter_contexts"].remove(context_id)

            finally:
                # Cleanup any remaining resources
                for pg_id in list(cleanup["process_groups"]):
                    try:
                        await orchestrator.delete_flow_workflow(
                            pg_id,
                            remove_from_registry=True,
                        )
                    except Exception:
                        pass

                for context_id in list(cleanup["parameter_contexts"]):
                    try:
                        await orchestrator.nifi_param_mgmt.delete_parameter_context(
                            context_id
                        )
                    except Exception:
                        pass

                if cleanup["flow_id"] and cleanup["bucket_id"]:
                    try:
                        await orchestrator.registry_flow_mgmt.delete_flow(
                            cleanup["bucket_id"],
                            cleanup["flow_id"],
                        )
                    except Exception:
                        pass

                if cleanup["bucket_id"]:
                    try:
                        latest_bucket = await registry_client.buckets.get_bucket(
                            cleanup["bucket_id"]
                        )
                        await registry_client.buckets.delete_bucket(
                            cleanup["bucket_id"],
                            latest_bucket["revision"],
                        )
                    except Exception:
                        pass


@pytest.mark.asyncio
@pytest.mark.integration
async def test_update_flow_metadata_and_parameters_roundtrip():
    """Ensure metadata and parameter updates propagate across NiFi and Registry."""

    unique_suffix = uuid.uuid4().hex[:8]

    original_definition = _build_sample_flow_definition(unique_suffix)

    flow_name = f"integration-update-flow-{unique_suffix}"
    updated_name = f"integration-update-flow-{unique_suffix}-edited"
    updated_description = f"Updated description {unique_suffix}"
    bucket_name = f"integration-update-bucket-{unique_suffix}"

    initial_parameters = {"greeting": "hello-world", "batch_size": "5"}
    updated_parameters = {"greeting": "hello-updated", "batch_size": "7"}

    nifi_client = get_test_nifi_client()
    registry_client = get_test_registry_client()

    async with nifi_client:
        async with registry_client:
            orchestrator = WorkflowOrchestrator(nifi_client, registry_client)

            cleanup = {
                "process_group": None,
                "parameter_context": None,
                "bucket_id": None,
                "flow_id": None,
            }

            try:
                deploy_result = await orchestrator.deploy_and_register_flow(
                    flow_definition=original_definition,
                    flow_name=flow_name,
                    bucket_name=bucket_name,
                    parameters=initial_parameters,
                    comments="Integration test - flow update",
                )

                assert deploy_result["success"] is True

                process_group_id = deploy_result["process_group_id"]
                cleanup["process_group"] = process_group_id

                parameter_context_id = deploy_result.get("parameter_context_id")
                if parameter_context_id:
                    cleanup["parameter_context"] = parameter_context_id

                bucket_id = deploy_result["bucket_info"]["bucket_id"]
                cleanup["bucket_id"] = bucket_id

                flow_id = deploy_result["registry_upload"]["flow_id"]
                cleanup["flow_id"] = flow_id

                update_result = await orchestrator.update_flow(
                    process_group_id,
                    name=updated_name,
                    description=updated_description,
                    parameters=updated_parameters,
                )

                assert update_result["metadata"]["success"] is True
                assert update_result["parameters"]["success"] is True

                latest_process_group = await nifi_client.process_groups.get_process_group(
                    process_group_id
                )
                component = latest_process_group.get("component", {})
                assert component.get("name") == updated_name
                assert component.get("comments") == updated_description

                metadata_registry = update_result["metadata"].get("registry_update")
                if metadata_registry:
                    assert metadata_registry["success"] is True
                    assert metadata_registry["name"] == updated_name
                    assert metadata_registry["description"] == updated_description

                if update_result["parameters"]:
                    parameter_context_id = update_result["parameters"]["parameter_context_id"]
                    cleanup["parameter_context"] = parameter_context_id

                    context = await orchestrator.nifi_param_mgmt.get_parameter_context(
                        parameter_context_id
                    )
                    parameters = context.get("parameters", {})
                    assert parameters["greeting"]["value"] == "hello-updated"
                    assert parameters["batch_size"]["value"] == "7"

                registry_flow = await orchestrator.registry_flow_mgmt.get_flow(
                    bucket_id,
                    flow_id,
                )
                assert registry_flow["name"] == updated_name
                assert registry_flow["description"] == updated_description

            finally:
                if cleanup["process_group"]:
                    try:
                        await orchestrator.delete_flow_workflow(
                            cleanup["process_group"],
                            remove_from_registry=True,
                        )
                    except Exception:
                        pass

                if cleanup["parameter_context"]:
                    try:
                        await nifi_client.parameter_contexts.delete_parameter_context(
                            cleanup["parameter_context"]
                        )
                    except Exception:
                        pass

                if cleanup["bucket_id"]:
                    try:
                        latest_bucket = await registry_client.buckets.get_bucket(
                            cleanup["bucket_id"]
                        )
                        await registry_client.buckets.delete_bucket(
                            cleanup["bucket_id"], latest_bucket["revision"]
                        )
                    except Exception:
                        pass
