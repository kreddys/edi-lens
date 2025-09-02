"""
Low-level service for interacting with the NiFi API.

This service provides a thin wrapper around the NiFiAPIClient, offering methods
for common NiFi operations like managing process groups, parameter contexts, and
version control. It is not intended to contain high-level business logic, but
rather to abstract the direct API calls.
"""

import logging
from typing import Dict, Any, Optional, List
from uuid import UUID

from src.core.config import settings
from src.models.workflow_models import Workflow
from src.nifi.clients.nifi_client import NiFiAPIClient
from src.nifi.clients.registry_client import NiFiRegistryClient

log = logging.getLogger(__name__)


class NiFiServiceError(Exception):
    """Exception raised for NiFi service errors."""
    pass


class NiFiService:
    """Service for managing NiFi resources via the API."""

    async def get_process_group_status(self, process_group_id: str) -> Dict[str, Any]:
        """Get the status of a NiFi process group."""
        async with NiFiAPIClient(
            settings.NIFI_URL,
            username=settings.NIFI_USERNAME,
            password=settings.NIFI_PASSWORD
        ) as nifi_client:
            pg_info = await nifi_client.get_process_group(process_group_id)
            # Extract relevant status information
            status = pg_info.get("status", {})
            aggregate_snapshot = status.get("aggregateSnapshot", {})
            
            return {
                "id": process_group_id,
                "name": pg_info["component"]["name"],
                "nifi_status": aggregate_snapshot.get("state"),
                "flow_files_queued": aggregate_snapshot.get("flowFilesQueued"),
                "bytes_queued": aggregate_snapshot.get("bytesQueued"),
                "active_threads": aggregate_snapshot.get("activeThreadCount"),
                "terminated_threads": aggregate_snapshot.get("terminatedThreadCount"),
                "input_content_size": aggregate_snapshot.get("inputContentSize"),
                "output_content_size": aggregate_snapshot.get("outputContentSize"),
                "queued_content_size": aggregate_snapshot.get("queuedContentSize"),
                "bytes_read": aggregate_snapshot.get("bytesRead"),
                "bytes_written": aggregate_snapshot.get("bytesWritten"),
                "read_write_duration": aggregate_snapshot.get("readWriteDuration"),
                "flow_files_received": aggregate_snapshot.get("flowFilesReceived"),
                "flow_files_sent": aggregate_snapshot.get("flowFilesSent"),
                "flow_files_transferred": aggregate_snapshot.get("flowFilesTransferred"),
                "flow_files_removed": aggregate_snapshot.get("flowFilesRemoved"),
                "flow_files_processed": aggregate_snapshot.get("flowFilesProcessed"),
                "bytes_received": aggregate_snapshot.get("bytesReceived"),
                "bytes_sent": aggregate_snapshot.get("bytesSent"),
                "bytes_transferred": aggregate_snapshot.get("bytesTransferred"),
                "bytes_removed": aggregate_snapshot.get("bytesRemoved"),
                "bytes_processed": aggregate_snapshot.get("bytesProcessed"),
                "processing_nanos": aggregate_snapshot.get("processingNanos"),
                "transfer_nanos": aggregate_snapshot.get("transferNanos"),
                "active_thread_count": aggregate_snapshot.get("activeThreadCount"),
                "terminated_thread_count": aggregate_snapshot.get("terminatedThreadCount"),
                "input_count": aggregate_snapshot.get("inputCount"),
                "output_count": aggregate_snapshot.get("outputCount"),
                "queued_count": aggregate_snapshot.get("queuedCount"),
                "uptime": aggregate_snapshot.get("uptime"),
                "last_refreshed": aggregate_snapshot.get("lastRefreshed")
            }

    async def start_workflow(self, workflow: Workflow):
        """Start a workflow in NiFi."""
        if not workflow.nifi_process_group_id:
            raise NiFiServiceError("Workflow has no process group ID and cannot be started.")
        async with NiFiAPIClient(
            settings.NIFI_URL,
            username=settings.NIFI_USERNAME,
            password=settings.NIFI_PASSWORD
        ) as nifi_client:
            await nifi_client.start_process_group(workflow.nifi_process_group_id)

    async def stop_workflow(self, workflow: Workflow):
        """Stop a workflow in NiFi."""
        if not workflow.nifi_process_group_id:
            raise NiFiServiceError("Workflow has no process group ID and cannot be stopped.")
        async with NiFiAPIClient(
            settings.NIFI_URL,
            username=settings.NIFI_USERNAME,
            password=settings.NIFI_PASSWORD
        ) as nifi_client:
            await nifi_client.stop_process_group(workflow.nifi_process_group_id)

    async def undeploy_workflow(self, workflow: Workflow):
        """Undeploy a workflow from NiFi."""
        if not workflow.nifi_process_group_id:
            raise NiFiServiceError("Workflow has no process group ID and cannot be undeployed.")
        async with NiFiAPIClient(
            settings.NIFI_URL,
            username=settings.NIFI_USERNAME,
            password=settings.NIFI_PASSWORD
        ) as nifi_client:
            await nifi_client.delete_process_group(workflow.nifi_process_group_id, version=0) # Assuming version 0 for deletion
            if workflow.nifi_parameter_context_id:
                await nifi_client.delete_parameter_context(workflow.nifi_parameter_context_id, version=0)

    async def create_parameter_context(
        self,
        workflow: Workflow,
        nifi_client: NiFiAPIClient
    ) -> Optional[Dict[str, Any]]:
        """Create parameter context for workflow configuration."""
        if not workflow.configuration:
            return None

        parameters = []
        for key, value in workflow.configuration.items():
            parameters.append({
                "name": key,
                "value": str(value) if value is not None else "",
                "sensitive": False,
                "description": f"Configuration parameter {key}"
            })

        param_context = await nifi_client.create_parameter_context(
            name=f"workflow-{workflow.workflow_id}",
            description=f"Parameters for workflow {workflow.name}",
            parameters=parameters
        )

        return param_context

    async def setup_registry_integration(self, nifi_client: NiFiAPIClient) -> Dict[str, Any]:
        """
        Set up NiFi Registry integration by registering the Registry client with NiFi.
        """
        try:
            existing_clients = await self._list_registry_clients(nifi_client)
            for client in existing_clients:
                component = client.get("component", {})
                if (component.get("uri") == settings.NIFI_REGISTRY_URL or
                    component.get("properties", {}).get("url") == settings.NIFI_REGISTRY_URL or
                    component.get("properties", {}).get("URL") == settings.NIFI_REGISTRY_URL or
                    "EDI Lens Registry" in component.get("name", "")):
                    log.info(f"Registry client already exists: {client['component']['name']}")
                    return client

            registry_client = await self._create_registry_client(nifi_client)
            log.info(f"Created registry client: {registry_client['component']['name']}")
            return registry_client
        except Exception as e:
            log.error(f"Failed to setup registry integration: {str(e)}")
            raise NiFiServiceError(f"Failed to setup registry integration: {str(e)}")

    async def deploy_from_registry(
        self,
        nifi_client: NiFiAPIClient,
        parent_group_id: str,
        bucket_id: str,
        flow_id: str,
        flow_version: int,
        process_group_name: str,
        position: Dict[str, int] = None
    ) -> Dict[str, Any]:
        """Deploy a process group from Registry using NiFi's version control."""
        try:
            registry_clients = await self._list_registry_clients(nifi_client)
            registry_client = None
            for client in registry_clients:
                component = client.get("component", {})
                name = component.get("name", "")
                uri = (component.get("uri") or
                       component.get("url") or
                       component.get("properties", {}).get("url") or
                       component.get("properties", {}).get("URL"))
                if (uri == settings.NIFI_REGISTRY_URL or
                    "EDI Lens Registry" in name):
                    registry_client = client
                    log.info(f"Found matching registry client: {name} with URI: {uri}")
                    break

            if not registry_client:
                raise ValueError("Registry client not found. Run setup_registry_integration() first.")

            registry_client_id = registry_client["component"]["id"]

            async with NiFiRegistryClient(settings.NIFI_REGISTRY_URL) as registry_client_api:
                flow_snapshot = await registry_client_api.get_flow_version(
                    bucket_id=bucket_id,
                    flow_id=flow_id,
                    version=flow_version
                )

            import_data = {
                "disconnectedNodeAcknowledged": False,
                "groupName": process_group_name,
                "positionDTO": position or {"x": 100, "y": 100},
                "revisionDTO": {"version": 0},
                "flowSnapshot": flow_snapshot
            }

            import_response = await nifi_client.session.post(
                f"{nifi_client.nifi_url}/process-groups/{parent_group_id}/process-groups/import",
                json=import_data
            )

            if import_response.status == 200:
                process_group = await import_response.json()
                await self._setup_version_control(
                    nifi_client, process_group, registry_client_id,
                    bucket_id, flow_id, flow_version
                )
                return process_group
            else:
                log.warning(f"Direct import failed ({import_response.status}), using fallback approach")
                pg_data = {
                    "revision": {"version": 0},
                    "component": {
                        "name": process_group_name,
                        "position": position or {"x": 100, "y": 100}
                    }
                }
                response = await nifi_client.session.post(
                    f"{nifi_client.nifi_url}/process-groups/{parent_group_id}/process-groups",
                    json=pg_data
                )
                response.raise_for_status()
                process_group = await response.json()
                await self._populate_process_group_from_registry(
                    nifi_client, process_group, flow_snapshot
                )
                await self._setup_version_control(
                    nifi_client, process_group, registry_client_id,
                    bucket_id, flow_id, flow_version
                )
                return process_group
        except Exception as e:
            log.error(f"Failed to deploy from Registry: {str(e)}")
            raise NiFiServiceError(f"Failed to deploy from Registry: {str(e)}")

    async def change_flow_version(
        self,
        nifi_client: NiFiAPIClient,
        process_group_id: str,
        new_version: int
    ) -> Dict[str, Any]:
        """Change the version of a version-controlled process group."""
        try:
            pg_info = await nifi_client.get_process_group(process_group_id)
            version_control_info = pg_info["component"].get("versionControlInformation")

            if not version_control_info:
                raise ValueError(f"Process group {process_group_id} is not version controlled")

            async with NiFiRegistryClient(settings.NIFI_REGISTRY_URL) as registry_client:
                flow_snapshot = await registry_client.get_flow_version(
                    bucket_id=version_control_info["bucketId"],
                    flow_id=version_control_info["flowId"],
                    version=new_version
                )

            update_data = {
                "processGroupRevision": pg_info["revision"],
                "versionedFlowSnapshot": flow_snapshot,
                "disconnectedNodeAcknowledged": False
            }

            response = await nifi_client.session.put(
                f"{nifi_client.nifi_url}/versions/process-groups/{process_group_id}",
                json=update_data
            )
            response.raise_for_status()
            result = await response.json()
            log.info(f"Changed process group {process_group_id} to version {new_version}")
            return result
        except Exception as e:
            log.error(f"Failed to change flow version: {str(e)}")
            raise NiFiServiceError(f"Failed to change flow version: {str(e)}")

    async def _setup_version_control(
        self,
        nifi_client: NiFiAPIClient,
        process_group: Dict[str, Any],
        registry_client_id: str,
        bucket_id: str,
        flow_id: str,
        flow_version: int
    ) -> bool:
        """Set up version control on a process group."""
        try:
            start_version_control_data = {
                "processGroupRevision": process_group["revision"],
                "versionControlInformation": {
                    "registryId": registry_client_id,
                    "bucketId": bucket_id,
                    "flowId": flow_id,
                    "version": flow_version,
                    "storageLocation": bucket_id
                },
                "disconnectedNodeAcknowledged": False
            }
            vc_response = await nifi_client.session.post(
                f"{nifi_client.nifi_url}/versions/process-groups/{process_group['component']['id']}",
                json=start_version_control_data
            )
            if vc_response.status == 200:
                log.info(f"Successfully set up version control for process group {process_group['component']['id']}")
                return True
            else:
                vc_response_text = await vc_response.text()
                log.warning(f"Version control setup returned {vc_response.status}: {vc_response_text}")
                return False
        except Exception as e:
            log.warning(f"Failed to set up version control: {str(e)}")
            return False

    async def _populate_process_group_from_registry(
        self,
        nifi_client: NiFiAPIClient,
        process_group: Dict[str, Any],
        flow_snapshot: Dict[str, Any]
    ) -> None:
        """Manually populate a process group with content from a Registry flow snapshot."""
        try:
            flow_contents = flow_snapshot.get("flowContents", {})
            pg_id = process_group["component"]["id"]
            log.info(f"Manually populating process group {pg_id} with Registry content")
            processors = flow_contents.get("processors", [])
            processor_id_map = {}
            for processor in processors:
                processor_data = {
                    "revision": {"version": 0},
                    "component": {
                        "name": processor.get("name", "Unknown Processor"),
                        "type": processor.get("type", "org.apache.nifi.processors.standard.LogMessage"),
                        "position": processor.get("position", {"x": 100, "y": 100}),
                        "config": {
                            "properties": processor.get("properties", {}),
                            "schedulingStrategy": processor.get("schedulingStrategy", "TIMER_DRIVEN"),
                            "schedulingPeriod": processor.get("schedulingPeriod", "1 sec"),
                            "concurrentlySchedulableTaskCount": processor.get("concurrentlySchedulableTaskCount", 1),
                            "bulletinLevel": processor.get("bulletinLevel", "WARN")
                        }
                    }
                }
                try:
                    response = await nifi_client.session.post(
                        f"{nifi_client.nifi_url}/process-groups/{pg_id}/processors",
                        json=processor_data
                    )
                    if response.status == 201:
                        created_processor = await response.json()
                        processor_id_map[processor.get("identifier")] = created_processor["component"]["id"]
                    else:
                        log.warning(f"Failed to create processor {processor.get('name')}: {response.status}")
                except Exception as proc_error:
                    log.warning(f"Error creating processor {processor.get('name')}: {str(proc_error)}")

            connections = flow_contents.get("connections", [])
            for connection in connections:
                try:
                    source_id = processor_id_map.get(connection.get("source", {}).get("id"))
                    dest_id = processor_id_map.get(connection.get("destination", {}).get("id"))
                    if source_id and dest_id:
                        connection_data = {
                            "revision": {"version": 0},
                            "component": {
                                "name": connection.get("name", ""),
                                "source": {
                                    "id": source_id,
                                    "groupId": pg_id,
                                    "type": "PROCESSOR"
                                },
                                "destination": {
                                    "id": dest_id,
                                    "groupId": pg_id,
                                    "type": "PROCESSOR"
                                },
                                "selectedRelationships": connection.get("selectedRelationships", ["success"])
                            }
                        }
                        response = await nifi_client.session.post(
                            f"{nifi_client.nifi_url}/process-groups/{pg_id}/connections",
                            json=connection_data
                        )
                        if response.status != 201:
                            log.warning(f"Failed to create connection: {response.status}")
                    else:
                        log.warning(f"Could not map connection source/destination IDs")
                except Exception as conn_error:
                    log.warning(f"Error creating connection: {str(conn_error)}")
        except Exception as e:
            log.warning(f"Failed to manually populate process group: {str(e)}")

    async def _list_registry_clients(self, nifi_client: NiFiAPIClient) -> list:
        """List all registry clients in NiFi."""
        response = await nifi_client.session.get(f"{nifi_client.nifi_url}/controller/registry-clients")
        response.raise_for_status()
        data = await response.json()
        return data.get("registries", [])

    async def _create_registry_client(self, nifi_client: NiFiAPIClient) -> Dict[str, Any]:
        """Create a new registry client in NiFi."""
        registry_data = {
            "revision": {"version": 0},
            "component": {
                "name": "EDI Lens Registry",
                "type": "org.apache.nifi.registry.flow.NifiRegistryFlowRegistryClient",
                "properties": {
                    "url": settings.NIFI_REGISTRY_URL
                },
                "description": "EDI Lens NiFi Registry for workflow templates"
            }
        }
        response = await nifi_client.session.post(
            f"{nifi_client.nifi_url}/controller/registry-clients",
            json=registry_data
        )
        response.raise_for_status()
        return await response.json()
