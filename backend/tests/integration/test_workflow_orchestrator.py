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
async def test_workflow_orchestrator_end_to_end():
    """Validate orchestrator workflows against live NiFi and Registry services."""

    unique_suffix = uuid.uuid4().hex[:8]
    flow_definition = _build_sample_flow_definition(unique_suffix)
    flow_name = f"integration-flow-{unique_suffix}"
    imported_flow_name = f"{flow_name}-imported"
    bucket_name = f"integration-bucket-{unique_suffix}"
    registry_client_name = f"integration-registry-{unique_suffix}"

    deployment_parameters = {"greeting": "hello-world"}
    import_parameters = {"threshold": "5"}

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
                "registry_client_id": None,
            }

            try:
                deploy_result = await orchestrator.deploy_and_register_flow(
                    flow_definition=flow_definition,
                    flow_name=flow_name,
                    bucket_name=bucket_name,
                    parameters=deployment_parameters,
                    comments="Integration test deployment",
                )

                assert deploy_result["success"] is True
                process_group_id = deploy_result["process_group_id"]
                cleanup["process_groups"].append(process_group_id)

                bucket_id = deploy_result["bucket_info"]["bucket_id"]
                flow_id = deploy_result["registry_upload"]["flow_id"]
                cleanup["bucket_id"] = bucket_id
                cleanup["flow_id"] = flow_id

                parameter_context_id = deploy_result["nifi_deployment"].get(
                    "parameter_context_id"
                )
                if parameter_context_id:
                    cleanup["parameter_contexts"].add(parameter_context_id)

                registry_entity = await nifi_client.version_control.create_registry_client(
                    name=registry_client_name,
                    url=registry_client.base.registry_url,
                    description="Integration test registry client",
                )
                registry_client_id = registry_entity["id"]
                cleanup["registry_client_id"] = registry_client_id

                await nifi_client.version_control.start_version_control(
                    process_group_id=process_group_id,
                    registry_id=registry_client_id,
                    bucket_id=bucket_id,
                    flow_name=flow_name,
                    flow_description="Integration test flow deployment",
                    comments="Initial version",
                    flow_id=flow_id,
                    flow_version=deploy_result["registry_upload"].get("version") or 1,
                )

                version_info = await nifi_client.version_control.get_version_control_info(
                    process_group_id
                )
                assert version_info.get("bucketId") == bucket_id
                assert version_info.get("flowId") == flow_id

                overview = await orchestrator.get_flow_overview(process_group_id)
                assert overview["is_under_version_control"] is True
                assert overview["parameter_context"]["parameter_context_id"] == parameter_context_id

                push_result = await orchestrator.integration_bridge.sync_flow_with_registry(
                    process_group_id=process_group_id,
                    action="push",
                )
                assert push_result["success"] is True
                assert push_result["action"] == "push"

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

                import_result = await orchestrator.import_and_deploy_flow(
                    bucket_id=bucket_id,
                    flow_id=flow_id,
                    parameters=import_parameters,
                    flow_name=imported_flow_name,
                )
                assert import_result["success"] is True
                imported_pg_id = import_result["process_group_id"]
                cleanup["process_groups"].append(imported_pg_id)

                imported_context = (
                    await orchestrator.nifi_param_mgmt.get_process_group_parameter_context(
                        imported_pg_id
                    )
                )
                if imported_context:
                    cleanup["parameter_contexts"].add(
                        imported_context["parameter_context_id"]
                    )

                start_result = await orchestrator.start_flow_workflow(imported_pg_id)
                assert start_result["success"] is True

                stop_result = await orchestrator.stop_flow_workflow(imported_pg_id)
                assert stop_result["success"] is True

                comparison = await orchestrator.integration_bridge.compare_with_registry(
                    process_group_id
                )
                assert comparison["bucket_id"] == bucket_id
                assert comparison["flow_id"] == flow_id

                disconnect_imported = await orchestrator.integration_bridge.disconnect_from_registry(
                    imported_pg_id
                )
                assert disconnect_imported["success"] is True

                delete_imported = await orchestrator.delete_flow_workflow(
                    imported_pg_id,
                    remove_from_registry=False,
                )
                assert delete_imported["success"] is True
                cleanup["process_groups"].remove(imported_pg_id)

                disconnect_primary = await orchestrator.integration_bridge.disconnect_from_registry(
                    process_group_id
                )
                assert disconnect_primary["success"] is True

                delete_primary = await orchestrator.delete_flow_workflow(
                    process_group_id,
                    remove_from_registry=False,
                )
                assert delete_primary["success"] is True
                cleanup["process_groups"].remove(process_group_id)

                await orchestrator.registry_flow_mgmt.delete_flow(
                    bucket_id=bucket_id,
                    flow_id=flow_id,
                )

                latest_bucket = await registry_client.buckets.get_bucket(bucket_id)
                await registry_client.buckets.delete_bucket(
                    bucket_id, latest_bucket["revision"]
                )
                cleanup["bucket_id"] = None
                cleanup["flow_id"] = None

                latest_registry_client = await nifi_client.version_control.get_registry_client(
                    registry_client_id
                )
                registry_revision = latest_registry_client.get("revision", {}).get(
                    "version", 0
                )
                await nifi_client.version_control.delete_registry_client(
                    registry_client_id,
                    revision=registry_revision,
                )
                cleanup["registry_client_id"] = None

                for context_id in list(cleanup["parameter_contexts"]):
                    await orchestrator.nifi_param_mgmt.delete_parameter_context(context_id)
                    cleanup["parameter_contexts"].remove(context_id)

            finally:
                for pg_id in list(cleanup["process_groups"]):
                    try:
                        await orchestrator.integration_bridge.disconnect_from_registry(pg_id)
                    except Exception:
                        pass
                    try:
                        await orchestrator.delete_flow_workflow(
                            pg_id,
                            remove_from_registry=False,
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

                if cleanup["registry_client_id"]:
                    try:
                        latest_registry_client = (
                            await nifi_client.version_control.get_registry_client(
                                cleanup["registry_client_id"]
                            )
                        )
                        registry_revision = latest_registry_client.get("revision", {}).get(
                            "version", 0
                        )
                        await nifi_client.version_control.delete_registry_client(
                            cleanup["registry_client_id"],
                            revision=registry_revision,
                        )
                    except Exception:
                        pass
