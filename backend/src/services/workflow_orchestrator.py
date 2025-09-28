"""Workflow orchestrator - coordinates domain services for complete workflow operations."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..clients.nifi_unified import NiFiUnifiedClient
from ..clients.registry_unified import RegistryUnifiedClient
from ..core.logging import get_logger, LoggerMixin
from .integration_bridge import IntegrationBridge
from .nifi_flow_deployment import NiFiFlowDeployment
from .nifi_flow_management import NiFiFlowManagement
from .nifi_parameter_management import NiFiParameterManagement
from .registry_bucket_management import RegistryBucketManagement
from .registry_flow_management import RegistryFlowManagement
from .registry_version_management import RegistryVersionManagement

log = get_logger(__name__)


class WorkflowOrchestratorError(RuntimeError):
    """Raised when workflow orchestration operations fail."""


class WorkflowOrchestrator(LoggerMixin):
    """Main orchestration service that coordinates all domain services for complete workflows."""

    def __init__(self, nifi_client: NiFiUnifiedClient, registry_client: RegistryUnifiedClient):
        self.nifi = nifi_client
        self.registry = registry_client

        # Initialize domain services
        self.nifi_deployment = NiFiFlowDeployment(nifi_client)
        self.nifi_flow_mgmt = NiFiFlowManagement(nifi_client)
        self.nifi_param_mgmt = NiFiParameterManagement(nifi_client)
        self.registry_bucket_mgmt = RegistryBucketManagement(registry_client)
        self.registry_flow_mgmt = RegistryFlowManagement(registry_client)
        self.registry_version_mgmt = RegistryVersionManagement(registry_client)
        self.integration_bridge = IntegrationBridge(nifi_client, registry_client)

        self.logger.info("Initialized Workflow Orchestrator with all domain services")

    async def deploy_and_register_flow(
        self,
        flow_definition: Dict[str, Any],
        flow_name: str,
        bucket_name: str,
        parameters: Dict[str, Any] = None,
        comments: str = "",
        parent_group_id: str = "root",
        bucket_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Complete deployment-first workflow:
        1. Deploy flow to NiFi with parameters
        2. If successful, upload to Registry for version control
        """
        parameters = parameters or {}

        try:
            self.logger.info("Starting deployment-first workflow for flow: %s", flow_name)

            # Step 1: Deploy flow to NiFi
            deployment_result = await self.nifi_deployment.deploy_flow(
                flow_definition=flow_definition,
                flow_name=flow_name,
                parameters=parameters,
                parent_group_id=parent_group_id
            )

            if not deployment_result.get("success"):
                # Return deployment failures without proceeding to Registry
                return {
                    "workflow": "deploy_and_register",
                    "flow_name": flow_name,
                    "success": False,
                    "stage": "nifi_deployment",
                    "nifi_deployment": deployment_result,
                    "message": "Flow deployment to NiFi failed"
                }

            process_group_id = deployment_result.get("process_group_id")

            # Step 2: Get bucket information
            if bucket_id:
                # Bucket ID provided, use it directly
                bucket_info = {"bucket_id": bucket_id, "bucket_name": bucket_name}
            else:
                # No bucket ID provided, ensure bucket exists by name
                bucket_info = await self.registry_bucket_mgmt.get_or_create_bucket(
                    bucket_name=bucket_name,
                    description=f"Bucket for {flow_name} and related flows"
                )
                bucket_id = bucket_info.get("bucket_id")

            # Step 3: Upload successful deployment to Registry
            try:
                upload_result = await self.integration_bridge.upload_flow_to_registry(
                    process_group_id=process_group_id,
                    bucket_id=bucket_id,
                    flow_name=flow_name,
                    comments=comments or f"Initial deployment of {flow_name}",
                    flow_description=f"Flow {flow_name} deployed via deployment-first workflow"
                )

                # Complete success
                result = {
                    "workflow": "deploy_and_register",
                    "flow_name": flow_name,
                    "success": True,
                    "stage": "completed",
                    "nifi_deployment": deployment_result,
                    "registry_upload": upload_result,
                    "bucket_info": bucket_info,
                    "process_group_id": process_group_id,
                    "parameter_context_id": deployment_result.get("parameter_context_id"),  # Include parameter context ID
                    "message": "Flow successfully deployed to NiFi and registered in Registry"
                }

                self.logger.info("Successfully completed deployment-first workflow for flow: %s", flow_name)
                return result

            except Exception as registry_exc:
                # NiFi deployment succeeded but Registry upload failed
                self.logger.warning("Registry upload failed for flow %s, but NiFi deployment succeeded: %s",
                                  flow_name, registry_exc)

                return {
                    "workflow": "deploy_and_register",
                    "flow_name": flow_name,
                    "success": False,
                    "stage": "registry_upload",
                    "nifi_deployment": deployment_result,
                    "registry_error": str(registry_exc),
                    "process_group_id": process_group_id,
                    "parameter_context_id": deployment_result.get("parameter_context_id"),  # Include parameter context ID
                    "message": "Flow deployed to NiFi successfully but Registry upload failed"
                }

        except Exception as exc:
            self.logger.error("Deployment-first workflow failed for flow %s: %s", flow_name, exc)
            raise WorkflowOrchestratorError(f"Deployment-first workflow failed: {exc}") from exc

    async def start_flow_workflow(
        self,
        process_group_id: str
    ) -> Dict[str, Any]:
        """Start a flow and return comprehensive status."""
        try:
            # Start the flow
            start_result = await self.nifi_flow_mgmt.start_flow(process_group_id)

            # Get detailed status
            flow_status = await self.nifi_flow_mgmt.get_flow_status(process_group_id)

            result = {
                "workflow": "start_flow",
                "process_group_id": process_group_id,
                "success": start_result.get("success"),
                "start_result": start_result,
                "flow_status": flow_status,
                "message": "Flow start operation completed" if start_result.get("success") else "Flow start partially failed"
            }

            return result

        except Exception as exc:
            self.logger.error("Start flow workflow failed for process group %s: %s", process_group_id, exc)
            raise WorkflowOrchestratorError(f"Start flow workflow failed: {exc}") from exc

    async def stop_flow_workflow(
        self,
        process_group_id: str
    ) -> Dict[str, Any]:
        """Stop a flow and return comprehensive status."""
        try:
            # Stop the flow
            stop_result = await self.nifi_flow_mgmt.stop_flow(process_group_id)

            # Get detailed status
            flow_status = await self.nifi_flow_mgmt.get_flow_status(process_group_id)

            result = {
                "workflow": "stop_flow",
                "process_group_id": process_group_id,
                "success": stop_result.get("success"),
                "stop_result": stop_result,
                "flow_status": flow_status,
                "message": "Flow stop operation completed" if stop_result.get("success") else "Flow stop partially failed"
            }

            return result

        except Exception as exc:
            self.logger.error("Stop flow workflow failed for process group %s: %s", process_group_id, exc)
            raise WorkflowOrchestratorError(f"Stop flow workflow failed: {exc}") from exc

    async def delete_flow_workflow(
        self,
        process_group_id: str,
        remove_from_registry: bool = False
    ) -> Dict[str, Any]:
        """Delete a flow from NiFi and optionally from Registry."""
        try:
            registry_info = None

            # If removing from Registry, get version control info first
            if remove_from_registry:
                try:
                    version_info = await self.nifi.version_control.get_version_control_info(process_group_id)
                    if version_info:
                        registry_info = {
                            "bucket_id": version_info.get("bucketId"),
                            "flow_id": version_info.get("flowId")
                        }
                except Exception:
                    # Process group might not be under version control
                    pass

            # Delete from NiFi
            delete_result = await self.nifi_flow_mgmt.delete_flow(process_group_id)

            # Delete from Registry if requested and we have the info
            registry_delete_result = None
            if remove_from_registry and registry_info:
                try:
                    registry_delete_result = await self.registry_flow_mgmt.delete_flow(
                        bucket_id=registry_info["bucket_id"],
                        flow_id=registry_info["flow_id"]
                    )
                except Exception as registry_exc:
                    registry_delete_result = {
                        "success": False,
                        "error": str(registry_exc)
                    }

            result = {
                "workflow": "delete_flow",
                "process_group_id": process_group_id,
                "success": delete_result.get("success"),
                "nifi_delete": delete_result,
                "registry_delete": registry_delete_result,
                "registry_info": registry_info,
                "message": "Flow deletion workflow completed"
            }

            return result

        except Exception as exc:
            self.logger.error("Delete flow workflow failed for process group %s: %s", process_group_id, exc)
            raise WorkflowOrchestratorError(f"Delete flow workflow failed: {exc}") from exc

    async def get_flow_overview(
        self,
        process_group_id: str
    ) -> Dict[str, Any]:
        """Get comprehensive overview of a flow including NiFi status and Registry info."""
        try:
            # Get NiFi status
            flow_status = await self.nifi_flow_mgmt.get_flow_status(process_group_id)

            # Get version control info if available
            version_control_info = None
            registry_comparison = None

            try:
                version_control_info = await self.nifi.version_control.get_version_control_info(process_group_id)
                if version_control_info:
                    # Validate version control info before attempting Registry comparison
                    vci = version_control_info.get("versionControlInformation", {})
                    bucket_id = vci.get("bucketId")
                    flow_id = vci.get("flowId")
                    version = vci.get("version")
                    
                    if all([bucket_id, flow_id, version]):
                        # Get comparison with Registry only if we have complete version control info
                        registry_comparison = await self.integration_bridge.compare_with_registry(process_group_id)
                    else:
                        self.logger.debug("Process group %s has incomplete version control info, skipping Registry comparison", process_group_id)
            except Exception as exc:
                # Process group might not be under version control or Registry might be unavailable
                self.logger.debug("Could not get version control info for process group %s: %s", process_group_id, exc)

            # Get parameter context info
            parameter_context = await self.nifi_param_mgmt.get_process_group_parameter_context(process_group_id)

            result = {
                "process_group_id": process_group_id,
                "flow_status": flow_status,
                "version_control_info": version_control_info,
                "registry_comparison": registry_comparison,
                "parameter_context": parameter_context,
                "is_under_version_control": version_control_info is not None,
                "has_parameters": parameter_context is not None
            }

            return result

        except Exception as exc:
            self.logger.error("Get flow overview failed for process group %s: %s", process_group_id, exc)
            raise WorkflowOrchestratorError(f"Get flow overview failed: {exc}") from exc

    async def list_all_flows(self) -> Dict[str, Any]:
        """Get a comprehensive list of all flows in NiFi and Registry."""
        try:
            # Get flows from NiFi
            nifi_flows = await self.nifi_flow_mgmt.list_flows()

            # Get flows from Registry
            registry_flows = await self.registry_flow_mgmt.list_all_flows()

            # Get buckets for context
            buckets = await self.registry_bucket_mgmt.list_buckets()

            result = {
                "nifi_flows": nifi_flows,
                "registry_flows": registry_flows,
                "registry_buckets": buckets,
                "summary": {
                    "nifi_flow_count": len(nifi_flows),
                    "registry_flow_count": len(registry_flows),
                    "registry_bucket_count": len(buckets)
                }
            }

            return result

        except Exception as exc:
            self.logger.error("List all flows failed: %s", exc)
            raise WorkflowOrchestratorError(f"List all flows failed: {exc}") from exc