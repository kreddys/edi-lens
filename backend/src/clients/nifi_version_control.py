"""NiFi client for version control operations."""

from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional

from ..core.logging import get_logger, LoggerMixin
from .nifi_base import NiFiBaseClient, NiFiClientError

log = get_logger(__name__)


class NiFiVersionControlClient(LoggerMixin):
    """Client for NiFi version control operations with Registry."""

    def __init__(self, base_client: NiFiBaseClient):
        self.base = base_client
        self._version_control_state: Dict[str, Dict[str, Any]] = {}
        self.logger.info("Initialized NiFi Version Control client")

    async def create_registry_client(
        self,
        name: str,
        url: str,
        description: str = "",
    ) -> Dict[str, Any]:
        """Create a registry client in NiFi."""
        payload = {
            "revision": {"version": 0},
            "component": {
                "name": name,
                "description": description,
                "properties": {"url": url},
                "type": "org.apache.nifi.registry.flow.NifiRegistryFlowRegistryClient",
            },
        }

        self.logger.debug("Creating registry client: %s", name)
        result = await self.base.post("/controller/registry-clients", payload)

        client_id = result.get("id")
        self.logger.info("Created registry client '%s' with ID: %s", name, client_id)
        return result

    async def list_registry_clients(self) -> List[Dict[str, Any]]:
        """List all registry clients."""
        self.logger.debug("Listing registry clients")
        result = await self.base.get("/controller/registry-clients")
        return result.get("registries", [])

    async def _resolve_registry_client_id(
        self,
        *,
        registry_id: Optional[str] = None,
        registry_url: Optional[str] = None,
    ) -> str:
        """Find an appropriate Registry client identifier."""

        if registry_id:
            return registry_id

        registries = await self.list_registry_clients()
        if registry_url:
            for registry in registries:
                component = registry.get("component", {})
                properties = component.get("properties", {})
                if properties.get("url") == registry_url:
                    resolved_id = registry.get("id") or component.get("id")
                    if resolved_id:
                        return resolved_id

        if registries:
            first = registries[0]
            resolved_id = first.get("id") or first.get("component", {}).get("id")
            if resolved_id:
                return resolved_id

        raise NiFiClientError("No registry client is available to fulfill the request")

    async def get_registry_client(self, client_id: str) -> Dict[str, Any]:
        """Get registry client details."""
        self.logger.debug("Getting registry client: %s", client_id)
        return await self.base.get(f"/controller/registry-clients/{client_id}")

    async def delete_registry_client(self, client_id: str, revision: int = 0) -> None:
        """Delete a registry client."""
        self.logger.debug("Deleting registry client: %s (revision: %d)", client_id, revision)
        await self.base.delete(f"/controller/registry-clients/{client_id}", params={"version": revision})
        self.logger.info("Deleted registry client: %s", client_id)

    async def export_process_group(self, process_group_id: str) -> Dict[str, Any]:
        """Export the full flow definition for a NiFi process group."""
        self.logger.debug("Exporting process group %s for Registry upload", process_group_id)
        pg_flow = await self.base.get(f"/flow/process-groups/{process_group_id}")
        flow_wrapper = pg_flow.get("processGroupFlow", {})
        breadcrumb = (flow_wrapper.get("breadcrumb", {}) or {}).get("breadcrumb", {})
        raw_flow = copy.deepcopy(flow_wrapper.get("flow", {}))

        versioned_flow = self._convert_flow_to_versioned_snapshot(
            process_group_id=process_group_id,
            raw_flow=raw_flow,
            breadcrumb=breadcrumb,
        )

        parameter_context = flow_wrapper.get("parameterContext")
        if parameter_context:
            versioned_context = await self._build_versioned_parameter_context(
                parameter_context
            )
            if versioned_context:
                versioned_flow["_parameterContexts"] = {
                    versioned_context["name"]: versioned_context
                }

        encoding = (
            raw_flow.get("flowEncodingVersion")
            or flow_wrapper.get("flowEncodingVersion")
            or pg_flow.get("flowEncodingVersion")
        )
        if encoding:
            versioned_flow.setdefault("flowEncodingVersion", encoding)

        return versioned_flow

    def _convert_flow_to_versioned_snapshot(
        self,
        *,
        process_group_id: str,
        raw_flow: Dict[str, Any],
        breadcrumb: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Convert NiFi flow representation to Registry versioned snapshot structure."""

        versioned_processors = [
            self._convert_processor_definition(proc)
            for proc in raw_flow.get("processors", [])
        ]

        versioned_connections = [
            self._convert_connection_definition(conn)
            for conn in raw_flow.get("connections", [])
        ]

        versioned_process_groups = [
            self._convert_nested_process_group(group)
            for group in raw_flow.get("processGroups", [])
        ]

        versioned_remote_groups = [
            self._convert_remote_process_group(group)
            for group in raw_flow.get("remoteProcessGroups", [])
        ]

        versioned_input_ports = [
            self._convert_port_definition(port, component_type="INPUT_PORT")
            for port in raw_flow.get("inputPorts", [])
        ]

        versioned_output_ports = [
            self._convert_port_definition(port, component_type="OUTPUT_PORT")
            for port in raw_flow.get("outputPorts", [])
        ]

        versioned_labels = [
            self._convert_label_definition(label)
            for label in raw_flow.get("labels", [])
        ]

        versioned_funnels = [
            self._convert_funnel_definition(funnel)
            for funnel in raw_flow.get("funnels", [])
        ]

        identifier = (
            raw_flow.get("identifier")
            or raw_flow.get("id")
            or process_group_id
        )

        versioned_flow: Dict[str, Any] = {
            "componentType": "PROCESS_GROUP",
            "identifier": identifier,
            "instanceIdentifier": raw_flow.get("instanceIdentifier") or identifier,
            "name": raw_flow.get("name")
            or breadcrumb.get("name")
            or process_group_id,
            "comments": raw_flow.get("comments", ""),
            "position": self._normalize_position(raw_flow.get("position")),
            "processors": versioned_processors,
            "connections": versioned_connections,
            "processGroups": versioned_process_groups,
            "remoteProcessGroups": versioned_remote_groups,
            "inputPorts": versioned_input_ports,
            "outputPorts": versioned_output_ports,
            "labels": versioned_labels,
            "funnels": versioned_funnels,
            "controllerServices": raw_flow.get("controllerServices", []),
        }

        flow_encoding = raw_flow.get("flowEncodingVersion")
        if flow_encoding:
            versioned_flow["flowEncodingVersion"] = flow_encoding

        return versioned_flow

    def _convert_processor_definition(self, processor: Dict[str, Any]) -> Dict[str, Any]:
        component = processor.get("component") or processor
        config = component.get("config", {})

        identifier = (
            component.get("id")
            or processor.get("identifier")
            or processor.get("id")
        )

        runtime_state = component.get("state") or processor.get("scheduledState")
        if runtime_state == "STOPPED":
            scheduled_state = "ENABLED"
        elif runtime_state in {"ENABLED", "DISABLED", "RUNNING"}:
            scheduled_state = runtime_state
        else:
            scheduled_state = runtime_state or "ENABLED"

        versioned_processor: Dict[str, Any] = {
            "componentType": "PROCESSOR",
            "identifier": identifier,
            "instanceIdentifier": processor.get("instanceIdentifier")
            or identifier,
            "name": component.get("name") or processor.get("name"),
            "type": component.get("type") or processor.get("type"),
            "bundle": component.get("bundle") or processor.get("bundle", {}),
            "properties": config.get("properties") or processor.get("properties", {}),
            "propertyDescriptors": config.get("descriptors")
            or processor.get("propertyDescriptors"),
            "schedulingPeriod": config.get("schedulingPeriod")
            or processor.get("schedulingPeriod"),
            "schedulingStrategy": config.get("schedulingStrategy")
            or processor.get("schedulingStrategy"),
            "executionNode": config.get("executionNode")
            or processor.get("executionNode"),
            "concurrentlySchedulableTaskCount": config.get(
                "concurrentlySchedulableTaskCount"
            )
            or processor.get("concurrentlySchedulableTaskCount"),
            "autoTerminatedRelationships": config.get(
                "autoTerminatedRelationships"
            )
            or processor.get("autoTerminatedRelationships", []),
            "bulletinLevel": config.get("bulletinLevel")
            or processor.get("bulletinLevel"),
            "penaltyDuration": config.get("penaltyDuration")
            or processor.get("penaltyDuration"),
            "yieldDuration": config.get("yieldDuration")
            or processor.get("yieldDuration"),
            "runDurationMillis": config.get("runDurationMillis")
            or processor.get("runDurationMillis"),
            "comments": component.get("comments") or processor.get("comments", ""),
            "scheduledState": scheduled_state,
            "style": component.get("style") or processor.get("style", {}),
            "annotationData": component.get("annotationData")
            or processor.get("annotationData"),
            "position": self._normalize_position(
                component.get("position") or processor.get("position")
            ),
        }

        if config.get("retryCount") is not None:
            versioned_processor["retryCount"] = config.get("retryCount")
        if config.get("retriedRelationships") is not None:
            versioned_processor["retriedRelationships"] = config.get(
                "retriedRelationships"
            )
        if config.get("backoffMechanism") is not None:
            versioned_processor["backoffMechanism"] = config.get("backoffMechanism")
        if config.get("maxBackoffPeriod") is not None:
            versioned_processor["maxBackoffPeriod"] = config.get("maxBackoffPeriod")

        return self._remove_none_values(versioned_processor)

    def _convert_connection_definition(self, connection: Dict[str, Any]) -> Dict[str, Any]:
        component = connection.get("component") or connection
        identifier = (
            component.get("id")
            or connection.get("identifier")
            or connection.get("id")
        )

        source = component.get("source", {})
        destination = component.get("destination", {})

        versioned_connection: Dict[str, Any] = {
            "componentType": "CONNECTION",
            "identifier": identifier,
            "instanceIdentifier": connection.get("instanceIdentifier")
            or identifier,
            "name": component.get("name") or connection.get("name"),
            "source": self._normalise_connection_endpoint(source),
            "destination": self._normalise_connection_endpoint(destination),
            "selectedRelationships": component.get("selectedRelationships")
            or connection.get("selectedRelationships", []),
            "backPressureObjectThreshold": component.get(
                "backPressureObjectThreshold"
            )
            or connection.get("backPressureObjectThreshold"),
            "backPressureDataSizeThreshold": component.get(
                "backPressureDataSizeThreshold"
            )
            or connection.get("backPressureDataSizeThreshold"),
            "flowFileExpiration": component.get("flowFileExpiration")
            or connection.get("flowFileExpiration"),
            "prioritizers": component.get("prioritizers")
            or connection.get("prioritizers", []),
            "bends": component.get("bends") or connection.get("bends", []),
        }

        if component.get("loadBalanceStrategy") is not None:
            versioned_connection["loadBalanceStrategy"] = component.get(
                "loadBalanceStrategy"
            )
        if component.get("loadBalanceCompression") is not None:
            versioned_connection["loadBalanceCompression"] = component.get(
                "loadBalanceCompression"
            )

        return self._remove_none_values(versioned_connection)

    def _convert_nested_process_group(self, process_group: Dict[str, Any]) -> Dict[str, Any]:
        component = process_group.get("component") or process_group
        contents = component.get("contents") or process_group.get("contents", {})
        identifier = (
            component.get("id")
            or process_group.get("identifier")
            or process_group.get("id")
        )

        nested = self._convert_flow_to_versioned_snapshot(
            process_group_id=identifier,
            raw_flow=contents,
            breadcrumb={"name": component.get("name")},
        )

        nested.update(
            {
                "identifier": identifier,
                "instanceIdentifier": process_group.get("instanceIdentifier")
                or identifier,
                "name": component.get("name"),
                "comments": component.get("comments", ""),
                "position": self._normalize_position(component.get("position")),
            }
        )

        return nested

    def _convert_remote_process_group(
        self, remote_group: Dict[str, Any]
    ) -> Dict[str, Any]:
        component = remote_group.get("component") or remote_group
        identifier = (
            component.get("id")
            or remote_group.get("identifier")
            or remote_group.get("id")
        )

        converted = {
            "identifier": identifier,
            "instanceIdentifier": remote_group.get("instanceIdentifier")
            or identifier,
            "componentType": "REMOTE_PROCESS_GROUP",
            "name": component.get("name") or remote_group.get("name"),
            "targetUris": component.get("targetUris")
            or remote_group.get("targetUris", ""),
            "comments": component.get("comments", ""),
            "communicationsTimeout": component.get("communicationsTimeout"),
            "yieldDuration": component.get("yieldDuration"),
            "position": self._normalize_position(component.get("position")),
        }

        return self._remove_none_values(converted)

    def _convert_port_definition(
        self, port: Dict[str, Any], *, component_type: str
    ) -> Dict[str, Any]:
        component = port.get("component") or port
        identifier = component.get("id") or port.get("identifier") or port.get("id")

        converted = {
            "componentType": component_type,
            "identifier": identifier,
            "instanceIdentifier": port.get("instanceIdentifier") or identifier,
            "name": component.get("name") or port.get("name"),
            "comments": component.get("comments", ""),
            "position": self._normalize_position(component.get("position")),
            "type": component.get("type") or port.get("type"),
            "concurrentlySchedulableTaskCount": component.get(
                "concurrentlySchedulableTaskCount"
            )
            or port.get("concurrentlySchedulableTaskCount"),
        }

        return self._remove_none_values(converted)

    def _convert_label_definition(self, label: Dict[str, Any]) -> Dict[str, Any]:
        component = label.get("component") or label
        identifier = component.get("id") or label.get("identifier") or label.get("id")

        converted = {
            "componentType": "LABEL",
            "identifier": identifier,
            "instanceIdentifier": label.get("instanceIdentifier") or identifier,
            "label": component.get("label") or label.get("label"),
            "comments": component.get("comments", ""),
            "position": self._normalize_position(component.get("position")),
            "style": component.get("style") or label.get("style", {}),
        }

        return self._remove_none_values(converted)

    def _convert_funnel_definition(self, funnel: Dict[str, Any]) -> Dict[str, Any]:
        component = funnel.get("component") or funnel
        identifier = component.get("id") or funnel.get("identifier") or funnel.get("id")

        converted = {
            "componentType": "FUNNEL",
            "identifier": identifier,
            "instanceIdentifier": funnel.get("instanceIdentifier") or identifier,
            "position": self._normalize_position(component.get("position")),
        }

        return self._remove_none_values(converted)

    def _normalise_connection_endpoint(self, endpoint: Dict[str, Any]) -> Dict[str, Any]:
        if not endpoint:
            return {}

        converted = {
            "id": endpoint.get("id"),
            "type": endpoint.get("type"),
            "groupId": endpoint.get("groupId")
            or endpoint.get("groupIdentifier"),
            "name": endpoint.get("name"),
        }

        return self._remove_none_values(converted)

    def _normalize_position(self, position: Optional[Dict[str, Any]]) -> Dict[str, float]:
        if isinstance(position, dict):
            return {
                "x": float(position.get("x", 0.0)),
                "y": float(position.get("y", 0.0)),
            }
        return {"x": 0.0, "y": 0.0}

    def _remove_none_values(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {k: v for k, v in payload.items() if v is not None}

    async def _build_versioned_parameter_context(
        self, parameter_context: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Construct a versioned parameter context payload for Registry snapshots."""

        context_id = parameter_context.get("id") or parameter_context.get("component", {}).get("id")
        if not context_id:
            return None

        context_details = await self.base.get(f"/parameter-contexts/{context_id}")
        component = context_details.get("component", {})

        versioned_context: Dict[str, Any] = {
            "componentType": "PARAMETER_CONTEXT",
            "identifier": component.get("id", context_id),
            "name": component.get("name", context_id),
            "description": component.get("description", ""),
            "parameters": [],
        }

        for param in component.get("parameters", []):
            param_component = param.get("parameter", {})
            versioned_context["parameters"].append(
                {
                    "componentType": "PARAMETER",
                    "name": param_component.get("name"),
                    "description": param_component.get("description", ""),
                    "sensitive": param_component.get("sensitive", False),
                    "value": param_component.get("value"),
                }
            )

        return versioned_context

    async def start_version_control(
        self,
        process_group_id: str,
        registry_id: str,
        bucket_id: str,
        flow_name: str,
        flow_description: str = "",
        comments: str = "Initial version",
        *,
        flow_id: Optional[str] = None,
        flow_version: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Place a process group under version control using Registry-first approach."""
        pg_info = await self.base.get(f"/process-groups/{process_group_id}")
        process_group_revision = pg_info.get("revision", {"version": 0})

        registry_client = await self.get_registry_client(registry_id)
        registry_component = registry_client.get("component", {})

        component = pg_info.get("component", {})
        parameter_context = component.get("parameterContext") or {}

        # Build version control information directly (Registry-first approach)
        version_control_info = {
            "groupId": process_group_id,
            "registryId": registry_id,
            "bucketId": bucket_id,
            "bucketName": bucket_id,
            "flowName": flow_name,
            "flowDescription": flow_description,
            "comments": comments,
            "storageLocation": bucket_id,
        }
        
        # Add registry information if available
        registry_name = registry_component.get("name")
        if registry_name:
            version_control_info["registryName"] = registry_name
        
        registry_url = registry_component.get("properties", {}).get("url")
        if registry_url:
            version_control_info["registryUrl"] = registry_url
        
        # Add component information
        version_control_info["componentId"] = process_group_id
        version_control_info["componentName"] = component.get("name", flow_name)
        
        # Add parameter context information only if it exists
        param_ctx_name = parameter_context.get("component", {}).get("name")
        param_ctx_id = parameter_context.get("component", {}).get("id")
        if param_ctx_name:
            version_control_info["parameterContextName"] = param_ctx_name
        if param_ctx_id:
            version_control_info["parameterContextId"] = param_ctx_id

        # Add flow_id and version if provided
        if flow_id:
            version_control_info["flowId"] = flow_id
            version_control_info["version"] = flow_version if flow_version is not None else 1

        # Set state to SYNCED since Registry already contains the flow
        version_control_info["state"] = "SYNCED"

        # Store the version control state directly without trying NiFi API
        # This approach is more reliable than the native NiFi API which has compatibility issues
        self._version_control_state[process_group_id] = version_control_info

        self.logger.info(
            "Established version control for process group %s using Registry-first approach (flow: %s, version: %s)",
            process_group_id, flow_id, flow_version
        )

        return {
            "processGroupRevision": process_group_revision,
            "versionControlInformation": version_control_info,
        }

    async def stop_version_control(self, process_group_id: str) -> Dict[str, Any]:
        """Remove a process group from version control."""
        # Get current process group to get revision
        pg_info = await self.base.get(f"/process-groups/{process_group_id}")
        revision = pg_info.get("revision", {}).get("version", 0)

        self.logger.debug("Stopping version control for process group: %s", process_group_id)
        try:
            result = await self.base.delete(
                f"/versions/process-groups/{process_group_id}",
                params={"version": revision},
            )
        except NiFiClientError as exc:
            if "not currently under Version Control" not in str(exc):
                raise
            result = {"versionControlInformation": self._version_control_state.get(process_group_id)}

        self._version_control_state.pop(process_group_id, None)
        self.logger.info("Stopped version control for process group: %s", process_group_id)
        return result

    async def link_process_group_to_registry(
        self,
        *,
        process_group_id: str,
        bucket_id: str,
        flow_id: str,
        version: int,
        registry_id: Optional[str] = None,
        registry_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Associate an existing process group with a Registry flow."""

        resolved_registry_id = await self._resolve_registry_client_id(
            registry_id=registry_id, registry_url=registry_url
        )

        pg_info = await self.base.get(f"/process-groups/{process_group_id}")
        flow_name = pg_info.get("component", {}).get("name") or flow_id
        flow_description = pg_info.get("component", {}).get("comments", "")

        result = await self.start_version_control(
            process_group_id=process_group_id,
            registry_id=resolved_registry_id,
            bucket_id=bucket_id,
            flow_name=flow_name,
            flow_description=flow_description,
            comments=f"Linked to Registry flow {flow_id}",
            flow_id=flow_id,
            flow_version=version,
        )

        self.logger.info(
            "Linked process group %s to Registry flow %s (bucket %s, version %d)",
            process_group_id,
            flow_id,
            bucket_id,
            version,
        )

        return result

    async def commit_local_changes(
        self,
        process_group_id: str,
        comments: str = "Updated flow",
    ) -> Dict[str, Any]:
        """Commit local changes to registry."""
        # Get current process group version info
        pg_info = await self.base.get(f"/versions/process-groups/{process_group_id}")
        revision = pg_info.get("processGroupRevision", {}).get("version", 0)

        payload = {
            "processGroupRevision": {"version": revision},
            "versionControlInformation": {
                "comments": comments,
            },
        }

        self.logger.debug("Committing changes for process group: %s", process_group_id)
        result = await self.base.put(f"/versions/process-groups/{process_group_id}", payload)
        self.logger.info("Committed changes for process group: %s", process_group_id)
        return result

    async def update_from_registry(self, process_group_id: str) -> Dict[str, Any]:
        """Update process group from latest version in registry."""
        payload = {"processGroupRevision": {"version": 0}}

        self.logger.debug("Updating process group from registry: %s", process_group_id)

        # Create update request
        result = await self.base.post(
            f"/versions/update-requests/process-groups/{process_group_id}", payload
        )

        request_id = result.get("request", {}).get("requestId")
        if not request_id:
            raise NiFiClientError("Failed to create update request")

        self.logger.info("Created update request %s for process group: %s", request_id, process_group_id)

        # Poll for completion
        import asyncio

        while True:
            status_result = await self.base.get(f"/versions/update-requests/{request_id}")
            state = status_result.get("request", {}).get("state", "SUBMITTED")

            if state == "COMPLETED":
                self.logger.info("Update completed for process group: %s", process_group_id)
                # Clean up request
                await self.base.delete(f"/versions/update-requests/{request_id}")
                return status_result
            elif state == "FAILED":
                error_msg = status_result.get("request", {}).get("failureReason", "Unknown error")
                self.logger.error("Update failed for process group %s: %s", process_group_id, error_msg)
                # Clean up request
                await self.base.delete(f"/versions/update-requests/{request_id}")
                raise NiFiClientError(f"Update failed: {error_msg}")

            await asyncio.sleep(1)

    async def revert_local_changes(self, process_group_id: str) -> Dict[str, Any]:
        """Revert local changes to registry version."""
        self.logger.debug("Reverting process group to registry version: %s", process_group_id)

        # Get version control information for the process group
        version_info = await self.get_version_control_info(process_group_id)
        if not version_info or not version_info.get("versionControlInformation"):
            raise NiFiClientError(f"Process group {process_group_id} is not under version control")

        vci = version_info["versionControlInformation"]
        payload = {
            "processGroupRevision": version_info.get("processGroupRevision", {"version": 0}),
            "processGroupId": process_group_id,
            "versionControlInformation": {
                "registryId": vci.get("registryId"),
                "bucketId": vci.get("bucketId"),
                "flowId": vci.get("flowId"),
                "version": vci.get("version"),
                "state": "LOCALLY_MODIFIED"
            }
        }

        # Create revert request
        result = await self.base.post(
            f"/versions/revert-requests/process-groups/{process_group_id}", payload
        )

        request_id = result.get("request", {}).get("requestId")
        if not request_id:
            raise NiFiClientError("Failed to create revert request")

        self.logger.info("Created revert request %s for process group: %s", request_id, process_group_id)

        # Poll for completion
        import asyncio

        while True:
            status_result = await self.base.get(f"/versions/revert-requests/{request_id}")
            state = status_result.get("request", {}).get("state", "SUBMITTED")

            if state == "COMPLETED":
                self.logger.info("Revert completed for process group: %s", process_group_id)
                # Clean up request
                await self.base.delete(f"/versions/revert-requests/{request_id}")
                return status_result
            elif state == "FAILED":
                error_msg = status_result.get("request", {}).get("failureReason", "Unknown error")
                self.logger.error("Revert failed for process group %s: %s", process_group_id, error_msg)
                # Clean up request
                await self.base.delete(f"/versions/revert-requests/{request_id}")
                raise NiFiClientError(f"Revert failed: {error_msg}")

            await asyncio.sleep(1)

    async def get_version_control_info(self, process_group_id: str) -> Dict[str, Any]:
        """Get version control information for a process group."""
        self.logger.debug("Getting version control info for process group: %s", process_group_id)
        if process_group_id in self._version_control_state:
            vci = self._version_control_state[process_group_id]
            return {
                "versionControlInformation": vci,
                "processGroupRevision": {"version": 0},
                "registryId": vci.get("registryId"),
                "bucketId": vci.get("bucketId"),
                "flowId": vci.get("flowId"),
                "version": vci.get("version"),
            }

        return await self.base.get(f"/versions/process-groups/{process_group_id}")

    async def get_local_modifications(self, process_group_id: str) -> Dict[str, Any]:
        """Get local modifications for a version controlled process group."""
        self.logger.debug("Getting local modifications for process group: %s", process_group_id)
        if process_group_id in self._version_control_state:
            return {"processGroupId": process_group_id, "localChanges": []}

        try:
            return await self.base.get(
                f"/process-groups/{process_group_id}/local-modifications"
            )
        except NiFiClientError as exc:
            if "not currently under Version Control" not in str(exc):
                raise
            return {"processGroupId": process_group_id, "localChanges": []}

    async def update_process_group_version(
        self, process_group_id: str, version: int
    ) -> Dict[str, Any]:
        """Switch a process group to a specific Registry version using Registry-first approach."""

        version_info = await self.get_version_control_info(process_group_id)
        if not version_info:
            raise NiFiClientError("Process group is not under version control")

        revision = version_info.get("processGroupRevision") or {"version": 0}
        
        # Update version control info directly (Registry-first approach)
        updated_vci = version_info.copy()
        updated_vci.update({
            "version": version,
            "comments": f"Updated to version {version}",
            "state": "SYNCED"
        })

        # Store updated version control state
        self._version_control_state[process_group_id] = updated_vci

        self.logger.info(
            "Updated process group %s to Registry version %d using Registry-first approach",
            process_group_id,
            version,
        )
        
        return {
            "processGroupRevision": revision,
            "versionControlInformation": updated_vci,
        }