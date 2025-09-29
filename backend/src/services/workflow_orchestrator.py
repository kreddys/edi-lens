"""Workflow orchestrator - coordinates domain services for complete workflow operations."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..clients.nifi_unified import NiFiUnifiedClient
from ..clients.registry_unified import RegistryUnifiedClient
from ..core.logging import get_logger, LoggerMixin
from .integration_bridge import IntegrationBridge
from .nifi_flow_deployment import NiFiFlowDeployment
from .nifi_flow_management import NiFiFlowManagement
from .nifi_parameter_management import (
    NiFiParameterManagement,
    NiFiParameterManagementError,
)
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

    async def update_flow_metadata(
        self,
        process_group_id: str,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update flow metadata in NiFi (and Registry when applicable)."""

        if name is None and description is None:
            raise WorkflowOrchestratorError("No metadata fields provided for update")

        try:
            self.logger.info(
                "Updating metadata for process group %s (name=%s, description_provided=%s)",
                process_group_id,
                name,
                description is not None,
            )

            nifi_update = await self.nifi_flow_mgmt.update_flow_metadata(
                process_group_id,
                name=name,
                description=description,
            )

            registry_update: Optional[Dict[str, Any]] = None
            version_control_info: Optional[Dict[str, Any]] = None

            try:
                version_control_info = await self.nifi.version_control.get_version_control_info(
                    process_group_id
                )
            except Exception as exc:
                self.logger.debug(
                    "Process group %s has no version control info or Registry unavailable: %s",
                    process_group_id,
                    exc,
                )

            if version_control_info:
                vci = version_control_info.get("versionControlInformation", {}) or {}
                bucket_id = vci.get("bucketId") or version_control_info.get("bucketId")
                flow_id = vci.get("flowId") or version_control_info.get("flowId")

                if bucket_id and flow_id:
                    try:
                        registry_update = await self.registry_flow_mgmt.update_flow(
                            bucket_id=bucket_id,
                            flow_id=flow_id,
                            name=name,
                            description=description,
                        )
                    except Exception as exc:
                        self.logger.warning(
                            "Failed to update Registry metadata for flow %s/%s: %s",
                            bucket_id,
                            flow_id,
                            exc,
                        )

            result = {
                "success": True,
                "process_group_id": process_group_id,
                "nifi_update": nifi_update,
                "registry_update": registry_update,
                "version_control_info": version_control_info,
            }

            self.logger.info(
                "Successfully updated metadata for process group %s",
                process_group_id,
            )

            return result

        except WorkflowOrchestratorError:
            raise
        except Exception as exc:
            self.logger.error(
                "Update flow metadata failed for process group %s: %s",
                process_group_id,
                exc,
            )
            raise WorkflowOrchestratorError(
                f"Update flow metadata failed: {exc}"
            ) from exc

    def _normalize_parameter_updates(
        self,
        parameter_updates: Optional[List[Dict[str, Any]]] = None,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Merge parameter update payloads from different shapes into a canonical list."""

        updates: Dict[str, Dict[str, Any]] = {}

        if parameter_updates:
            for update in parameter_updates:
                name = update.get("name") if isinstance(update, dict) else None
                if not name:
                    continue

                updates[name] = {
                    "name": name,
                    "value": update.get("value"),
                    "description": update.get("description") or f"Parameter {name}",
                    "sensitive": update.get("sensitive", False),
                }

        if parameters:
            for name, value in parameters.items():
                if isinstance(value, dict):
                    updates[name] = {
                        "name": name,
                        "value": value.get("value"),
                        "description": value.get("description") or f"Parameter {name}",
                        "sensitive": value.get("sensitive", False),
                    }
                else:
                    updates[name] = {
                        "name": name,
                        "value": value,
                        "description": f"Parameter {name}",
                        "sensitive": False,
                    }

        return list(updates.values())

    async def _update_parameter_context(
        self,
        process_group_id: str,
        parameter_updates: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Apply parameter updates to the flow's parameter context."""

        if not parameter_updates:
            raise WorkflowOrchestratorError("No parameter updates provided")

        self.logger.info("Starting parameter update for flow: %s", process_group_id)

        param_context = await self.nifi_param_mgmt.get_process_group_parameter_context(process_group_id)
        if not param_context:
            raise WorkflowOrchestratorError(f"No parameter context found for flow {process_group_id}")

        context_id = param_context["parameter_context_id"]
        self.logger.debug("Found parameter context: %s for flow: %s", context_id, process_group_id)

        parameter_dict = {}
        for update in parameter_updates:
            parameter_dict[update["name"]] = {
                "value": update.get("value"),
                "description": update.get("description", f"Parameter {update['name']}") or f"Parameter {update['name']}",
                "sensitive": update.get("sensitive", False),
            }

        try:
            update_result = await self.nifi_param_mgmt.update_parameter_context_parameters(
                context_id, parameter_dict
            )

            updated_context = await self.nifi_param_mgmt.get_parameter_context(context_id)

            result = {
                "success": True,
                "process_group_id": process_group_id,
                "parameter_context_id": context_id,
                "updated_parameters": list(parameter_dict.keys()),
                "parameter_count": updated_context["parameter_count"],
                "revision": updated_context["revision"],
                "update_details": update_result,
                "message": f"Successfully updated {len(parameter_dict)} parameters",
            }

            self.logger.info("Successfully updated parameters for flow: %s", process_group_id)
            return result

        except NiFiParameterManagementError as exc:
            message = str(exc)
            if "componentId must be specified" in message:
                self.logger.info(
                    "Parameter update for %s requires context recreation; creating new context",
                    process_group_id,
                )
                return await self._recreate_parameter_context(
                    process_group_id,
                    param_context,
                    parameter_updates,
                )
            raise WorkflowOrchestratorError(
                f"Update flow parameters failed: {exc}"
            ) from exc
        except Exception as exc:
            self.logger.error(
                "Update flow parameters failed for process group %s: %s",
                process_group_id,
                exc,
            )
            raise WorkflowOrchestratorError(
                f"Update flow parameters failed: {exc}"
            ) from exc

    async def update_flow(
        self,
        process_group_id: str,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        parameter_updates: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Coordinate flow metadata and parameter context updates."""

        normalized_parameter_updates = self._normalize_parameter_updates(parameter_updates, parameters)

        if name is None and description is None and not normalized_parameter_updates:
            raise WorkflowOrchestratorError("No update fields provided")

        result: Dict[str, Any] = {
            "process_group_id": process_group_id,
            "metadata": None,
            "parameters": None,
        }

        if name is not None or description is not None:
            result["metadata"] = await self.update_flow_metadata(
                process_group_id,
                name=name,
                description=description,
            )

        if normalized_parameter_updates:
            result["parameters"] = await self._update_parameter_context(
                process_group_id,
                normalized_parameter_updates,
            )

        return result

    async def _recreate_parameter_context(
        self,
        process_group_id: str,
        current_context: Dict[str, Any],
        parameter_updates: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Fallback path that recreates the parameter context when NiFi refuses in-place updates."""

        original_parameters = current_context.get("parameters", {}) or {}
        merged_parameters: Dict[str, Dict[str, Any]] = {}

        for name, details in original_parameters.items():
            merged_parameters[name] = {
                "value": details.get("value"),
                "sensitive": details.get("sensitive", False),
                "description": details.get("description", f"Parameter {name}"),
            }

        for update in parameter_updates:
            merged_parameters[update["name"]] = {
                "value": update.get("value"),
                "sensitive": update.get("sensitive", False),
                "description": update.get("description", f"Parameter {update['name']}") or f"Parameter {update['name']}",
            }

        base_name = current_context.get("name") or f"flow-{process_group_id}-context"
        description = current_context.get("description", "")

        parameters_payload = {
            name: details.get("value")
            for name, details in merged_parameters.items()
            if details.get("value") is not None
        }

        creation = await self.nifi_param_mgmt.create_parameter_context(
            name=f"{base_name}-edit",
            description=description,
            parameters=parameters_payload,
        )

        new_context_id = creation["parameter_context_id"]

        await self.nifi_param_mgmt.assign_parameter_context_to_process_group(
            process_group_id,
            new_context_id,
        )

        try:
            await self.nifi_param_mgmt.delete_parameter_context(
                current_context["parameter_context_id"]
            )
        except Exception as cleanup_exc:
            self.logger.debug(
                "Failed to delete superseded parameter context %s: %s",
                current_context["parameter_context_id"],
                cleanup_exc,
            )

        updated_context = await self.nifi_param_mgmt.get_parameter_context(new_context_id)

        return {
            "success": True,
            "process_group_id": process_group_id,
            "parameter_context_id": new_context_id,
            "updated_parameters": list(parameters_payload.keys()),
            "parameter_count": updated_context["parameter_count"],
            "revision": updated_context["revision"],
            "update_details": creation,
            "message": "Parameter context recreated to apply updates",
        }

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

    async def update_flow_parameters(
        self,
        process_group_id: str,
        parameter_updates: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Update parameters for a flow's parameter context."""

        normalized = self._normalize_parameter_updates(parameter_updates, None)
        if not normalized:
            raise WorkflowOrchestratorError("No parameter updates provided")

        return await self._update_parameter_context(process_group_id, normalized)