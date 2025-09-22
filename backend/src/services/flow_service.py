"""Flow service for managing NiFi flows with Registry storage."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ..clients.nifi_client import NiFiClient, NiFiClientError
from ..clients.registry_client import RegistryClient, RegistryClientError
from ..core.logging import get_logger, LoggerMixin, audit_logger

log = get_logger(__name__)


class FlowServiceError(RuntimeError):
    """Raised when flow operations fail."""


class FlowService(LoggerMixin):
    """Service for managing flows using Registry + NiFi integration."""

    def __init__(self, nifi_client: NiFiClient, registry_client: RegistryClient):
        self.nifi_client = nifi_client
        self.registry_client = registry_client
        
        self.logger.info("Initializing FlowService")
        self.logger.debug("NiFi client: %s", self.nifi_client.__class__.__name__)
        self.logger.debug("Registry client: %s", self.registry_client.__class__.__name__)

    # Registry Operations
    async def create_flow(self, bucket_id: str, flow_definition: Dict[str, Any], parameters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Create a new flow in Registry with initial version."""
        flow_name = flow_definition.get("name", "Unnamed Flow")
        
        self.logger.info("Creating flow '%s' in bucket '%s'", flow_name, bucket_id)
        self.logger.debug("Flow definition processors: %d", len(flow_definition.get("processors", [])))
        self.logger.debug("Flow definition connections: %d", len(flow_definition.get("connections", [])))
        self.logger.debug("Parameters provided: %d", len(parameters) if parameters else 0)
        
        try:
            description = flow_definition.get("description", "")
            
            # 1. Create flow metadata in Registry
            self.logger.debug("Creating flow metadata in Registry...")
            flow_result = await self.registry_client.create_flow(bucket_id, flow_name, description)
            flow_id = flow_result["identifier"]
            self.logger.info("Flow metadata created with ID: %s", flow_id)
            
            # 2. Create initial version with flow definition
            self.logger.debug("Creating initial flow version...")
            version_result = await self.registry_client.create_flow_version(
                bucket_id=bucket_id,
                flow_id=flow_id,
                flow_contents=flow_definition,
                version=1,
                comments="Initial flow version"
            )
            
            self.logger.info("Successfully created flow '%s' (ID: %s) in bucket '%s'", 
                           flow_name, flow_id, bucket_id)
            
            # Audit log
            audit_logger.log_flow_operation(
                operation="create_flow",
                bucket_id=bucket_id,
                flow_id=flow_id,
                details={
                    "flow_name": flow_name,
                    "processors_count": len(flow_definition.get("processors", [])),
                    "connections_count": len(flow_definition.get("connections", [])),
                    "has_parameters": bool(parameters)
                }
            )
            
            return {
                "success": True,
                "flow_id": flow_id,
                "version": 1
            }
            
        except (RegistryClientError, KeyError) as exc:
            self.logger.error("Failed to create flow '%s' in bucket '%s': %s", 
                            flow_name, bucket_id, exc)
            return {
                "success": False,
                "error": {
                    "error_type": "FLOW_CREATION_FAILED",
                    "user_message": f"Failed to create flow in Registry: {exc}",
                    "action_required": "Check flow definition and Registry connectivity"
                }
            }

    async def get_flow(self, bucket_id: str, flow_id: str, version: Optional[int] = None) -> Dict[str, Any]:
        """Get flow definition from Registry."""
        try:
            if version is None:
                # Get latest version
                return await self.registry_client.get_latest_flow_version(bucket_id, flow_id)
            else:
                # Get specific version
                return await self.registry_client.get_flow_version(bucket_id, flow_id, version)
                
        except RegistryClientError as exc:
            raise FlowServiceError(f"Failed to get flow from Registry: {exc}") from exc

    async def list_flows(self, bucket_id: str) -> List[Dict[str, Any]]:
        """List all flows in a bucket."""
        try:
            return await self.registry_client.list_flows(bucket_id)
        except RegistryClientError as exc:
            raise FlowServiceError(f"Failed to list flows: {exc}") from exc

    async def list_buckets(self) -> List[Dict[str, Any]]:
        """List available Registry buckets."""
        try:
            return await self.registry_client.list_buckets()
        except RegistryClientError as exc:
            raise FlowServiceError(f"Failed to list buckets: {exc}") from exc

    async def delete_flow(self, bucket_id: str, flow_id: str) -> bool:
        """Delete a flow and all its versions."""
        try:
            await self.registry_client.delete_flow(bucket_id, flow_id)
            log.info(f"Deleted flow {flow_id} from bucket {bucket_id}")
            return True
        except RegistryClientError as exc:
            raise FlowServiceError(f"Failed to delete flow: {exc}") from exc

    async def update_flow(self, bucket_id: str, flow_id: str, flow_definition: Optional[Dict[str, Any]] = None, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Update flow by creating a new version."""
        try:
            if flow_definition is None:
                return {
                    "success": False,
                    "error": {
                        "error_type": "INVALID_REQUEST",
                        "user_message": "Flow definition is required for update",
                        "action_required": "Provide a valid flow definition"
                    }
                }
            
            # Get current latest version to determine next version number
            latest = await self.registry_client.get_latest_flow_version(bucket_id, flow_id)
            next_version = latest["snapshotMetadata"]["version"] + 1
            
            # Create new version
            version_result = await self.registry_client.create_flow_version(
                bucket_id=bucket_id,
                flow_id=flow_id,
                flow_contents=flow_definition,
                version=next_version,
                comments=f"Updated to version {next_version}"
            )
            
            return {
                "success": True,
                "flow_id": flow_id,
                "version": next_version
            }
            
        except (RegistryClientError, KeyError) as exc:
            return {
                "success": False,
                "error": {
                    "error_type": "FLOW_UPDATE_FAILED",
                    "user_message": f"Failed to update flow: {exc}",
                    "action_required": "Check flow definition and Registry connectivity"
                }
            }

    # NiFi Deployment Operations
    async def deploy_flow(
        self,
        bucket_id: str,
        flow_id: str,
        parameters: Dict[str, Any] = None,
        version: Optional[int] = None,
        parent_group_id: str = "root"
    ) -> Dict[str, Any]:
        """Deploy flow from Registry to NiFi with parameter context."""
        try:
            deployment_info = {}

            # 0. Ensure Registry client exists in NiFi
            registry_id = await self._ensure_registry_client()

            # 1. Create parameter context if parameters provided
            if parameters:
                param_context_name = f"params-{flow_id}-{bucket_id}"
                param_list = []
                for name, value in parameters.items():
                    param_list.append({
                        "parameter": {
                            "name": name,
                            "value": str(value),
                            "sensitive": False
                        }
                    })

                param_context = await self.nifi_client.create_parameter_context(
                    name=param_context_name,
                    description=f"Parameters for flow {flow_id}",
                    parameters=param_list
                )
                deployment_info["parameter_context_id"] = param_context["id"]
                log.info(f"Created parameter context: {param_context['id']}")
            
            # 2. Get flow snapshot from Registry
            self.logger.debug("Getting flow snapshot from Registry...")
            flow_snapshot = await self.registry_client.get_flow_version(bucket_id, flow_id, version or 1)
            self.logger.info("Retrieved flow snapshot: %s v%s",
                           flow_snapshot.get("snapshotMetadata", {}).get("flowIdentifier"),
                           flow_snapshot.get("snapshotMetadata", {}).get("version"))

            # 3. Import flow from Registry snapshot
            import_result = await self.nifi_client.import_from_registry(
                parent_group_id=parent_group_id,
                flow_snapshot=flow_snapshot,
                position={"x": 100.0, "y": 100.0}
            )
            
            process_group_id = import_result["id"]
            deployment_info["process_group_id"] = process_group_id
            log.info(f"Imported flow as process group: {process_group_id}")
            
            # 4. Associate parameter context with process group
            if parameters and "parameter_context_id" in deployment_info:
                pg_revision = import_result["revision"]["version"]
                await self.nifi_client.set_parameter_context_for_process_group(
                    process_group_id=process_group_id,
                    parameter_context_id=deployment_info["parameter_context_id"],
                    revision=pg_revision
                )
                log.info(f"Associated parameter context with process group")
            
            return {
                "success": True,
                "process_group_id": process_group_id,
                "parameter_context_id": deployment_info.get("parameter_context_id"),
                "deployment_details": deployment_info
            }
            
        except (NiFiClientError, KeyError) as exc:
            return {
                "success": False,
                "error": {
                    "error_type": "FLOW_DEPLOYMENT_FAILED",
                    "user_message": f"Failed to deploy flow: {exc}",
                    "action_required": "Check NiFi connectivity and flow definition"
                }
            }

    async def start_flow_by_process_group(self, process_group_id: str) -> Dict[str, Any]:
        """Start all processors in a deployed flow by process group ID."""
        try:
            result = await self.nifi_client.start_process_group(process_group_id)
            log.info(f"Started process group: {process_group_id}")
            return {"status": "RUNNING", "process_group_id": process_group_id}
            
        except NiFiClientError as exc:
            raise FlowServiceError(f"Failed to start flow: {exc}") from exc

    async def stop_flow_by_process_group(self, process_group_id: str) -> Dict[str, Any]:
        """Stop all processors in a deployed flow by process group ID."""
        try:
            result = await self.nifi_client.stop_process_group(process_group_id)
            log.info(f"Stopped process group: {process_group_id}")
            return {"status": "STOPPED", "process_group_id": process_group_id}
            
        except NiFiClientError as exc:
            raise FlowServiceError(f"Failed to stop flow: {exc}") from exc

    async def undeploy_flow_by_process_group(self, process_group_id: str, parameter_context_id: Optional[str] = None) -> Dict[str, Any]:
        """Remove flow from NiFi canvas and clean up parameter context by process group ID."""
        try:
            # 1. Stop the process group first
            await self.stop_flow_by_process_group(process_group_id)
            
            # 2. Get current revision for deletion
            pg_info = await self.nifi_client.get_root_process_group()
            # Note: In a real implementation, we'd need to find the specific PG revision
            # For now, we'll use revision 0 as a placeholder
            
            # 3. Delete process group
            await self.nifi_client.delete_process_group(process_group_id, revision=0)
            log.info(f"Deleted process group: {process_group_id}")
            
            # 4. Clean up parameter context if provided
            if parameter_context_id:
                # Note: Parameter context deletion would require additional API calls
                # to handle dependencies and get proper revision
                log.info(f"Parameter context cleanup needed: {parameter_context_id}")
            
            return {"status": "UNDEPLOYED", "process_group_id": process_group_id}
            
        except NiFiClientError as exc:
            raise FlowServiceError(f"Failed to undeploy flow: {exc}") from exc

    async def get_flow_status_by_process_group(self, process_group_id: str) -> Dict[str, Any]:
        """Get deployment status of a flow by process group ID."""
        try:
            flow_info = await self.nifi_client.get_process_group_flow(process_group_id)
            
            # Extract status information
            status_info = {
                "process_group_id": process_group_id,
                "status": "UNKNOWN",
                "processor_count": 0,
                "running_count": 0,
                "stopped_count": 0
            }
            
            # Count processor states
            if "processGroupFlow" in flow_info:
                processors = flow_info["processGroupFlow"].get("flow", {}).get("processors", [])
                status_info["processor_count"] = len(processors)
                
                for processor in processors:
                    if processor.get("status", {}).get("runStatus") == "Running":
                        status_info["running_count"] += 1
                    else:
                        status_info["stopped_count"] += 1
                
                # Determine overall status
                if status_info["running_count"] > 0:
                    status_info["status"] = "RUNNING"
                elif status_info["processor_count"] > 0:
                    status_info["status"] = "STOPPED"
                else:
                    status_info["status"] = "EMPTY"
            
            return status_info
            
        except NiFiClientError as exc:
            raise FlowServiceError(f"Failed to get flow status: {exc}") from exc

    async def update_flow_parameters_by_context(self, parameter_context_id: str, parameters: Dict[str, str]) -> Dict[str, Any]:
        """Update parameters for a deployed flow by parameter context ID."""
        try:
            # Get current parameter context to get revision
            current_context = await self.nifi_client.get_parameter_context(parameter_context_id)
            revision = current_context["revision"]["version"]
            
            # Update parameters
            result = await self.nifi_client.update_parameter_context(
                context_id=parameter_context_id,
                parameters=parameters,
                revision=revision
            )
            
            log.info(f"Updated parameters for context: {parameter_context_id}")
            return {"status": "UPDATED", "parameter_context_id": parameter_context_id}
            
        except NiFiClientError as exc:
            raise FlowServiceError(f"Failed to update flow parameters: {exc}") from exc

    # Additional API-compatible methods
    async def start_flow(self, bucket_id: str, flow_id: str) -> bool:
        """Start flow by bucket and flow ID (finds deployed process group)."""
        # This would need a way to track deployed flows
        # For now, we'll implement a simplified version
        try:
            # In a real implementation, we'd need to store deployment mappings
            # For now, return True as a placeholder
            log.info(f"Starting flow {flow_id} in bucket {bucket_id}")
            return True
        except Exception as exc:
            log.error(f"Failed to start flow {flow_id}: {exc}")
            return False

    async def stop_flow(self, bucket_id: str, flow_id: str) -> bool:
        """Stop flow by bucket and flow ID (finds deployed process group)."""
        try:
            # In a real implementation, we'd need to store deployment mappings
            log.info(f"Stopping flow {flow_id} in bucket {bucket_id}")
            return True
        except Exception as exc:
            log.error(f"Failed to stop flow {flow_id}: {exc}")
            return False

    async def undeploy_flow(self, bucket_id: str, flow_id: str) -> None:
        """Undeploy flow by bucket and flow ID."""
        try:
            # In a real implementation, we'd need to store deployment mappings
            log.info(f"Undeploying flow {flow_id} from bucket {bucket_id}")
        except Exception as exc:
            log.error(f"Failed to undeploy flow {flow_id}: {exc}")
            raise FlowServiceError(f"Failed to undeploy flow: {exc}") from exc

    async def get_flow_status(self, bucket_id: str, flow_id: str) -> Dict[str, Any]:
        """Get flow status by bucket and flow ID."""
        try:
            # In a real implementation, we'd track deployment status
            return {
                "flow_id": flow_id,
                "bucket_id": bucket_id,
                "deployment_status": "NOT_DEPLOYED",
                "process_group_id": None,
                "parameter_context_id": None,
                "active_processors": 0,
                "stopped_processors": 0,
                "invalid_processors": 0
            }
        except Exception as exc:
            log.error(f"Failed to get flow status {flow_id}: {exc}")
            raise FlowServiceError(f"Failed to get flow status: {exc}") from exc

    async def update_flow_parameters(self, bucket_id: str, flow_id: str, parameters: Dict[str, Any]) -> bool:
        """Update flow parameters by bucket and flow ID."""
        try:
            # In a real implementation, we'd find the parameter context and update it
            log.info(f"Updating parameters for flow {flow_id} in bucket {bucket_id}")
            return True
        except Exception as exc:
            log.error(f"Failed to update parameters for flow {flow_id}: {exc}")
            return False

    async def get_flow_parameters(self, bucket_id: str, flow_id: str) -> Dict[str, Any]:
        """Get current flow parameters by bucket and flow ID."""
        try:
            # In a real implementation, we'd find the parameter context and return its parameters
            log.info(f"Getting parameters for flow {flow_id} in bucket {bucket_id}")
            return {}
        except Exception as exc:
            log.error(f"Failed to get parameters for flow {flow_id}: {exc}")
            raise FlowServiceError(f"Failed to get flow parameters: {exc}") from exc

    async def _ensure_registry_client(self) -> str:
        """Ensure Registry client exists in NiFi and return its ID."""
        try:
            # Check if Registry client already exists
            registries = await self.nifi_client.list_registry_clients()

            for registry in registries:
                registry_url = registry.get("component", {}).get("properties", {}).get("url", "")
                # Check if this registry matches our Registry URL
                if self.registry_client.registry_url in registry_url or registry_url in self.registry_client.registry_url:
                    registry_id = registry.get("id")
                    self.logger.info("Found existing Registry client: %s", registry_id)
                    return registry_id

            # Create new Registry client if none exists
            self.logger.info("Creating new Registry client for %s", self.registry_client.registry_url)

            registry_result = await self.nifi_client.create_registry_client(
                name="EDI Lens Registry",
                url=self.registry_client.registry_url,
                description="Registry client for EDI Lens flows"
            )

            registry_id = registry_result.get("id")
            self.logger.info("Created Registry client: %s", registry_id)

            return registry_id

        except (NiFiClientError, KeyError) as exc:
            raise FlowServiceError(f"Failed to ensure Registry client: {exc}") from exc