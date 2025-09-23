"""Flow service implementing the deployment-first workflow."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from ..clients.nifi_unified import NiFiUnifiedClient
from ..clients.registry_unified import RegistryUnifiedClient
from ..core.logging import get_logger, LoggerMixin, audit_logger
from .nifi_deployment_service import NiFiDeploymentService
from .nifi_version_control_service import NiFiVersionControlService
from .registry_flow_service import RegistryFlowService

log = get_logger(__name__)


class FlowServiceError(RuntimeError):
    """Raised when flow operations fail."""


class FlowService(LoggerMixin):
    """
    Flow service implementing deployment-first workflow:
    1. Deploy and validate in NiFi
    2. Upload to Registry with version control if successful
    """

    def __init__(self, nifi_client: NiFiUnifiedClient, registry_client: RegistryUnifiedClient):
        self.nifi_deployment = NiFiDeploymentService(nifi_client)
        self.nifi_version_control = NiFiVersionControlService(nifi_client, registry_client)
        self.registry_flows = RegistryFlowService(registry_client)

        self.logger.info("Initialized Flow Service")

    async def deploy_and_store_flow(
        self,
        bucket_id: str,
        flow_definition: Dict[str, Any],
        parameters: Dict[str, Any] = None,
        parent_group_id: str = "root",
        flow_name: Optional[str] = None,
        flow_description: str = "",
    ) -> Dict[str, Any]:
        """
        Deploy flow to NiFi and store in Registry with version control.
        This is the main method implementing the improved workflow.
        """
        flow_name = flow_name or flow_definition.get("name", f"flow-{int(time.time())}")
        parameters = parameters or {}

        self.logger.info("Starting deploy-and-store workflow for flow: %s", flow_name)

        # Step 1: Deploy and validate in NiFi
        deployment_result = await self.nifi_deployment.deploy_and_validate_flow(
            flow_definition=flow_definition,
            parameters=parameters,
            parent_group_id=parent_group_id,
            flow_name=flow_name,
        )

        if not deployment_result.get("success"):
            self.logger.warning("Flow deployment failed, stopping workflow")
            return {
                "success": False,
                "stage": "deployment",
                "error": {
                    "error_type": "DEPLOYMENT_FAILED",
                    "user_message": "Flow failed to deploy and validate in NiFi",
                    "action_required": "Fix deployment issues and try again",
                    "deployment_details": deployment_result,
                },
            }

        process_group_id = deployment_result.get("process_group_id")
        parameter_context_id = deployment_result.get("parameter_context_id")

        self.logger.info("Flow deployed successfully, proceeding to Registry upload")

        # Step 2: Upload to Registry with version control
        registry_result = await self.nifi_version_control.upload_to_registry_with_version_control(
            process_group_id=process_group_id,
            bucket_id=bucket_id,
            flow_name=flow_name,
            description=flow_description,
            comments="Initial version from deployment-first workflow",
        )

        if not registry_result.get("success"):
            self.logger.warning("Registry upload failed, but flow remains deployed")
            return {
                "success": True,  # Deployment succeeded, Registry upload failed
                "stage": "registry_upload",
                "deployment_result": deployment_result,
                "registry_warning": {
                    "error_type": "REGISTRY_UPLOAD_FAILED",
                    "user_message": "Flow deployed successfully but failed to upload to Registry",
                    "action_required": "Flow is ready to use, Registry upload can be retried later",
                    "registry_details": registry_result.get("error", {}),
                },
            }

        self.logger.info("Flow successfully deployed and stored with version control")

        # Audit log
        audit_logger.log_flow_operation(
            operation="deploy_and_store_flow",
            bucket_id=bucket_id,
            flow_id=registry_result.get("flow_id"),
            details={
                "flow_name": flow_name,
                "process_group_id": process_group_id,
                "parameter_context_id": parameter_context_id,
                "has_parameters": bool(parameters),
                "processors_count": deployment_result.get("summary", {}).get("total_processors", 0),
                "connections_count": deployment_result.get("summary", {}).get("total_connections", 0),
            },
        )

        return {
            "success": True,
            "stage": "completed",
            "flow_id": registry_result.get("flow_id"),
            "version": registry_result.get("version"),
            "process_group_id": process_group_id,
            "parameter_context_id": parameter_context_id,
            "deployment_result": deployment_result,
            "registry_result": registry_result,
        }

    async def update_deployed_flow(
        self,
        process_group_id: str,
        flow_definition: Optional[Dict[str, Any]] = None,
        parameters: Optional[Dict[str, Any]] = None,
        commit_changes: bool = True,
        comments: str = "Updated flow",
    ) -> Dict[str, Any]:
        """
        Update a deployed flow by modifying NiFi and optionally committing to Registry.
        """
        self.logger.info("Updating deployed flow: %s", process_group_id)

        try:
            # For now, this is a placeholder for more complex update logic
            # In a full implementation, this would:
            # 1. Stop the flow
            # 2. Update processors/connections
            # 3. Restart the flow
            # 4. Commit changes to Registry if requested

            if commit_changes:
                commit_result = await self.nifi_version_control.commit_local_changes(
                    process_group_id=process_group_id,
                    comments=comments,
                )

                if not commit_result.get("success"):
                    return {
                        "success": False,
                        "error": {
                            "error_type": "COMMIT_FAILED",
                            "user_message": "Flow updated but failed to commit to Registry",
                            "action_required": "Commit can be retried later",
                            "details": commit_result.get("error", {}),
                        },
                    }

            return {
                "success": True,
                "process_group_id": process_group_id,
                "committed": commit_changes,
            }

        except Exception as exc:
            self.logger.error("Failed to update deployed flow %s: %s", process_group_id, exc)
            return {
                "success": False,
                "error": {
                    "error_type": "UPDATE_FAILED",
                    "user_message": f"Failed to update flow: {exc}",
                    "action_required": "Check flow status and try again",
                    "details": {"message": str(exc)},
                },
            }

    # Flow Management Operations
    async def start_flow(self, process_group_id: str) -> Dict[str, Any]:
        """Start a deployed flow."""
        try:
            result = await self.nifi_deployment.start_flow(process_group_id)
            self.logger.info("Started flow: %s", process_group_id)
            return {"success": True, **result}
        except Exception as exc:
            self.logger.error("Failed to start flow %s: %s", process_group_id, exc)
            return {
                "success": False,
                "error": {
                    "error_type": "START_FAILED",
                    "user_message": f"Failed to start flow: {exc}",
                    "action_required": "Check flow status and NiFi connectivity",
                },
            }

    async def stop_flow(self, process_group_id: str) -> Dict[str, Any]:
        """Stop a deployed flow."""
        try:
            result = await self.nifi_deployment.stop_flow(process_group_id)
            self.logger.info("Stopped flow: %s", process_group_id)
            return {"success": True, **result}
        except Exception as exc:
            self.logger.error("Failed to stop flow %s: %s", process_group_id, exc)
            return {
                "success": False,
                "error": {
                    "error_type": "STOP_FAILED",
                    "user_message": f"Failed to stop flow: {exc}",
                    "action_required": "Check flow status and NiFi connectivity",
                },
            }

    async def delete_flow(self, process_group_id: str, remove_from_registry: bool = False) -> Dict[str, Any]:
        """Delete a deployed flow and optionally remove from Registry."""
        try:
            # Get version control info before deletion
            vc_info = None
            if remove_from_registry:
                vc_result = await self.nifi_version_control.get_version_control_info(process_group_id)
                if vc_result.get("success"):
                    vc_info = vc_result.get("version_control_info", {}).get("versionControlInformation", {})

            # Delete from NiFi
            nifi_result = await self.nifi_deployment.delete_flow(process_group_id)

            # Delete from Registry if requested and we have version control info
            if remove_from_registry and vc_info:
                bucket_id = vc_info.get("bucketId")
                flow_id = vc_info.get("flowId")
                if bucket_id and flow_id:
                    try:
                        await self.registry_flows.delete_flow(bucket_id, flow_id)
                        self.logger.info("Deleted flow from Registry: %s", flow_id)
                    except Exception as exc:
                        self.logger.warning("Failed to delete flow from Registry: %s", exc)

            self.logger.info("Deleted flow: %s", process_group_id)
            return {"success": True, **nifi_result}

        except Exception as exc:
            self.logger.error("Failed to delete flow %s: %s", process_group_id, exc)
            return {
                "success": False,
                "error": {
                    "error_type": "DELETE_FAILED",
                    "user_message": f"Failed to delete flow: {exc}",
                    "action_required": "Check flow status and try again",
                },
            }

    async def get_flow_status(self, process_group_id: str) -> Dict[str, Any]:
        """Get status of a deployed flow."""
        try:
            status = await self.nifi_deployment.get_flow_status(process_group_id)

            # Also get version control info if available
            vc_result = await self.nifi_version_control.get_version_control_info(process_group_id)
            if vc_result.get("success"):
                status["version_control"] = vc_result.get("version_control_info", {})

            return {"success": True, **status}

        except Exception as exc:
            self.logger.error("Failed to get flow status %s: %s", process_group_id, exc)
            return {
                "success": False,
                "error": {
                    "error_type": "STATUS_FAILED",
                    "user_message": f"Failed to get flow status: {exc}",
                    "action_required": "Check process group ID and NiFi connectivity",
                },
            }

    # Version Control Operations
    async def commit_changes(self, process_group_id: str, comments: str = "Updated flow") -> Dict[str, Any]:
        """Commit local changes to Registry."""
        return await self.nifi_version_control.commit_local_changes(process_group_id, comments)

    async def update_from_registry(self, process_group_id: str) -> Dict[str, Any]:
        """Update flow from Registry."""
        return await self.nifi_version_control.update_from_registry(process_group_id)

    async def revert_changes(self, process_group_id: str) -> Dict[str, Any]:
        """Revert local changes to Registry version."""
        return await self.nifi_version_control.revert_local_changes(process_group_id)

    async def get_local_modifications(self, process_group_id: str) -> Dict[str, Any]:
        """Get local modifications."""
        return await self.nifi_version_control.get_local_modifications(process_group_id)

    # Registry Operations (passthrough to registry service)
    async def list_buckets(self) -> List[Dict[str, Any]]:
        """List Registry buckets."""
        return await self.registry_flows.list_buckets()

    async def list_flows(self, bucket_id: str) -> List[Dict[str, Any]]:
        """List flows in a bucket."""
        return await self.registry_flows.list_flows(bucket_id)

    async def get_flow_from_registry(self, bucket_id: str, flow_id: str, version: Optional[int] = None) -> Dict[str, Any]:
        """Get flow from Registry."""
        if version is None:
            return await self.registry_flows.get_latest_flow_version(bucket_id, flow_id)
        else:
            return await self.registry_flows.get_flow_version(bucket_id, flow_id, version)