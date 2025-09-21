"""
Low-level service for interacting with the NiFi API.

This service provides a thin wrapper around the NiFiAPIClient, offering methods
for common NiFi operations like managing process groups, parameter contexts, and
version control. It is not intended to contain high-level business logic, but
rather to abstract the direct API calls.
"""

import logging
import json
import time
from typing import Dict, Any, Optional, List
from uuid import UUID

from src.core.config import settings
from src.models.workflow_models import Workflow
from src.nifi.clients.nifi_client import NiFiAPIClient
from src.nifi.clients.registry_client import NiFiRegistryClient
from src.exceptions.workflow_exceptions import (
    RegistryImportError, 
    VersionControlError,
    ProcessorValidationError,
    ProcessorCreationError,
    ConnectionCreationError
)

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
            await nifi_client.start_process_group(str(workflow.nifi_process_group_id))

    async def stop_workflow(self, workflow: Workflow):
        """Stop a workflow in NiFi."""
        if not workflow.nifi_process_group_id:
            raise NiFiServiceError("Workflow has no process group ID and cannot be stopped.")
        async with NiFiAPIClient(
            settings.NIFI_URL,
            username=settings.NIFI_USERNAME,
            password=settings.NIFI_PASSWORD
        ) as nifi_client:
            await nifi_client.stop_process_group(str(workflow.nifi_process_group_id))

    async def undeploy_workflow(self, workflow: Workflow):
        """Undeploy a workflow from NiFi."""
        if not workflow.nifi_process_group_id:
            raise NiFiServiceError("Workflow has no process group ID and cannot be undeployed.")
        async with NiFiAPIClient(
            settings.NIFI_URL,
            username=settings.NIFI_USERNAME,
            password=settings.NIFI_PASSWORD
        ) as nifi_client:
            # Refresh process group info to get current revision version
            try:
                pg_info = await nifi_client.get_process_group(str(workflow.nifi_process_group_id))
                current_version = pg_info.get("revision", {}).get("version", 0)
            except Exception as e:
                log.warning(f"Failed to get current process group info, using version 0: {e}")
                current_version = 0
            
            await nifi_client.delete_process_group(str(workflow.nifi_process_group_id), version=current_version)
            if workflow.nifi_parameter_context_id:
                # Refresh parameter context info to get current revision version
                try:
                    param_context_info = await nifi_client.get_parameter_context(str(workflow.nifi_parameter_context_id))
                    param_context_version = param_context_info.get("revision", {}).get("version", 0)
                except Exception as e:
                    log.warning(f"Failed to get current parameter context info, using version 0: {e}")
                    param_context_version = 0
                await nifi_client.delete_parameter_context(str(workflow.nifi_parameter_context_id), version=param_context_version)

    async def create_parameter_context(
        self,
        workflow: Workflow,
        nifi_client: NiFiAPIClient
    ) -> Dict[str, Any]:
        """Create parameter context for workflow configuration."""
        parameters = []
        
        log.info(f"Creating parameter context for workflow {workflow.workflow_id}")
        log.debug(f"Workflow name: {workflow.name}")
        log.debug(f"Workflow configuration: {workflow.configuration}")
        log.debug(f"Configuration type: {type(workflow.configuration)}")
        
        # Only add parameters if configuration is not empty
        if workflow.configuration and len(workflow.configuration) > 0:
            log.info(f"Processing {len(workflow.configuration)} configuration parameters")
            for key, value in workflow.configuration.items():
                param_def = {
                    "name": key,
                    "value": str(value) if value is not None else "",
                    "sensitive": False,
                    "description": f"Configuration parameter {key}"
                }
                parameters.append(param_def)
                log.debug(f"Added parameter: {key} = '{param_def['value']}'")
        else:
            log.warning(f"No configuration parameters found for workflow {workflow.workflow_id}")
        
        log.debug(f"Total parameters to create: {len(parameters)}")

        # Always create a parameter context (even if empty) to avoid None issues
        context_name = f"workflow-{str(workflow.workflow_id)}"
        log.info(f"Creating parameter context with name: {context_name}")
        
        param_context = await nifi_client.create_parameter_context(
            name=context_name,
            description=f"Parameters for workflow {workflow.name}",
            parameters=parameters
        )
        
        log.info(f"Parameter context created successfully: {param_context.get('id', 'unknown')}")
        log.debug(f"Parameter context details: name={param_context.get('component', {}).get('name')}")
        log.debug(f"Parameter context parameters: {len(param_context.get('component', {}).get('parameters', []))} parameters")
        
        # Log each parameter in the created context
        context_params = param_context.get('component', {}).get('parameters', [])
        for param in context_params:
            log.debug(f"Context parameter: {param.get('parameter', {}).get('name')} = '{param.get('parameter', {}).get('value')}'")

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
        position: Dict[str, int] = None,
        parameter_context_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Deploy a process group from Registry using NiFi's version control."""
        try:
            log.debug(f"Deploying from registry: bucket_id={bucket_id}, flow_id={flow_id}, flow_version={flow_version}")
            
            # Get registry client for NiFi
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
                log.debug(f"Getting flow version from registry")
                flow_snapshot = await registry_client_api.get_flow_version(
                    bucket_id=bucket_id,
                    flow_id=flow_id,
                    version=flow_version
                )
                
                # Debug: Log the flow definition retrieved from Registry
                log.debug("Retrieved flow snapshot from Registry")
                flow_contents = flow_snapshot.get("flowContents", {})
                log.debug(f"Flow contents keys: {list(flow_contents.keys()) if isinstance(flow_contents, dict) else 'Not a dict'}")
                
                if isinstance(flow_contents, dict) and 'processors' in flow_contents:
                    processors = flow_contents['processors']
                    log.debug(f"Found {len(processors)} processors in retrieved flow")
                    for i, proc in enumerate(processors):
                        if isinstance(proc, dict):
                            log.debug(f"Processor {i} structure keys: {list(proc.keys())}")
                            
                            # Try different ways to get processor name
                            proc_name = (proc.get('component', {}).get('name') or 
                                        proc.get('name') or 
                                        f'Processor {i}')
                            proc_type = (proc.get('component', {}).get('type') or 
                                        proc.get('type') or 
                                        'Unknown')
                            
                            log.debug(f"Processor: {proc_name} ({proc_type})")
                            
                            # Try different ways to get properties
                            proc_props = (proc.get('component', {}).get('config', {}).get('properties') or 
                                         proc.get('config', {}).get('properties') or
                                         proc.get('properties') or {})
                            
                            if proc_props:
                                log.debug(f"Properties count: {len(proc_props)}")
                                for prop_name, prop_value in proc_props.items():
                                    if prop_value and ("${" in str(prop_value) or "directory" in prop_name.lower() or "filter" in prop_name.lower()):
                                        log.debug(f"Property {prop_name}: '{prop_value}'")
                            else:
                                log.debug("No properties found for this processor")

            # Convert VersionedFlowSnapshot from Registry to RegisteredFlowSnapshot for NiFi import
            # The Registry returns VersionedFlowSnapshot, but NiFi import expects RegisteredFlowSnapshot
            log.debug("=== DETAILED REGISTRY DATA ANALYSIS ===")
            log.debug(f"Original flow_snapshot keys: {list(flow_snapshot.keys()) if isinstance(flow_snapshot, dict) else 'Not a dict'}")
            log.debug(f"Flow snapshot type: {type(flow_snapshot)}")
            
            # Log detailed flow contents
            flow_contents = flow_snapshot.get("flowContents", {})
            log.debug(f"FlowContents type: {type(flow_contents)}")
            log.debug(f"FlowContents keys: {list(flow_contents.keys()) if isinstance(flow_contents, dict) else 'Not a dict'}")
            
            if isinstance(flow_contents, dict):
                processors = flow_contents.get("processors", [])
                connections = flow_contents.get("connections", [])
                log.debug(f"Processors count in flowContents: {len(processors)}")
                log.debug(f"Connections count in flowContents: {len(connections)}")
                
                # Log each processor in detail
                for i, proc in enumerate(processors):
                    log.debug(f"Processor {i}: {proc.get('name', 'Unknown')} ({proc.get('type', 'Unknown')})")
                    log.debug(f"  - ID: {proc.get('identifier', 'No ID')}")
                    log.debug(f"  - Properties: {list(proc.get('properties', {}).keys())}")
                
                # Log each connection in detail
                for i, conn in enumerate(connections):
                    log.debug(f"Connection {i}: {conn.get('name', 'Unknown')}")
                    log.debug(f"  - Source: {conn.get('source', {}).get('id', 'No source')}")
                    log.debug(f"  - Destination: {conn.get('destination', {}).get('id', 'No dest')}")
                    log.debug(f"  - Relationships: {conn.get('selectedRelationships', [])}")

            registered_flow_snapshot = {
                "bucket": flow_snapshot.get("bucket"),
                "flow": flow_snapshot.get("flow"), 
                "snapshotMetadata": flow_snapshot.get("snapshotMetadata"),
                "flowContents": flow_snapshot.get("flowContents"),
                "externalControllerServices": flow_snapshot.get("externalControllerServices", {}),
                "parameterContexts": flow_snapshot.get("parameterContexts", {}),
                "parameterProviders": flow_snapshot.get("parameterProviders", {}),
                "flowEncodingVersion": flow_snapshot.get("flowEncodingVersion")
            }

            log.debug("=== CONVERTED REGISTERED FLOW SNAPSHOT ===")
            log.debug(f"RegisteredFlowSnapshot keys: {list(registered_flow_snapshot.keys())}")
            log.debug(f"RegisteredFlowSnapshot flowContents type: {type(registered_flow_snapshot.get('flowContents'))}")
            
            # Verify the conversion preserved the processors
            converted_flow_contents = registered_flow_snapshot.get("flowContents", {})
            if isinstance(converted_flow_contents, dict):
                converted_processors = converted_flow_contents.get("processors", [])
                converted_connections = converted_flow_contents.get("connections", [])
                log.debug(f"CONVERTED - Processors count: {len(converted_processors)}")
                log.debug(f"CONVERTED - Connections count: {len(converted_connections)}")

            # Structure the import data according to ProcessGroupUploadEntity from NiFi OpenAPI
            import_data = {
                "flowSnapshot": registered_flow_snapshot,
                "groupName": process_group_name,
                "positionDTO": position or {"x": 100, "y": 100},
                "revisionDTO": {"version": 0},
                "disconnectedNodeAcknowledged": False
            }
            
            # Include parameter context in the flow snapshot according to NiFi API spec
            if parameter_context_id:
                log.debug(f"Including parameter context {parameter_context_id} in RegisteredFlowSnapshot")
                
                # Get the parameter context details
                param_context_details = await nifi_client.get_parameter_context(parameter_context_id)
                param_context_name = param_context_details.get("component", {}).get("name", "")
                
                if param_context_name:
                    # Add parameter context to the flow snapshot's parameterContexts map
                    if "parameterContexts" not in registered_flow_snapshot:
                        registered_flow_snapshot["parameterContexts"] = {}
                    
                    # Convert NiFi parameter context to VersionedParameterContext format
                    versioned_param_context = {
                        "identifier": parameter_context_id,
                        "name": param_context_name,
                        "description": param_context_details.get("component", {}).get("description", ""),
                        "parameters": []
                    }
                    
                    # Convert parameters to versioned format
                    for param in param_context_details.get("component", {}).get("parameters", []):
                        param_data = param.get("parameter", {})
                        versioned_param_context["parameters"].append({
                            "name": param_data.get("name", ""),
                            "description": param_data.get("description", ""),
                            "value": param_data.get("value", ""),
                            "sensitive": param_data.get("sensitive", False)
                        })
                    
                    registered_flow_snapshot["parameterContexts"][param_context_name] = versioned_param_context
                    
                    # Set parameterContextName in the flowContents (VersionedProcessGroup)
                    if "flowContents" in registered_flow_snapshot:
                        registered_flow_snapshot["flowContents"]["parameterContextName"] = param_context_name
                        log.debug(f"Set parameterContextName to '{param_context_name}' in flowContents")
                
                log.debug(f"Parameter context integration complete for import")

            log.debug("=== FINAL IMPORT DATA ===")
            log.debug(f"Import data keys: {list(import_data.keys())}")
            log.debug(f"Import data flowSnapshot type: {type(import_data.get('flowSnapshot'))}")
            
            # Log the size of the import payload
            import json as json_module
            try:
                import_json = json_module.dumps(import_data)
                log.debug(f"Import payload size: {len(import_json)} characters")
                log.debug(f"Import payload preview (first 500 chars): {import_json[:500]}...")
            except Exception as e:
                log.error(f"Failed to serialize import data: {e}")

            import_url = f"{nifi_client.nifi_url}/process-groups/{parent_group_id}/process-groups/import"
            log.info(f"Importing Registry flow snapshot for process group '{process_group_name}'")
            log.debug(f"Import URL: {import_url}")
            log.debug(f"Flow snapshot contains: processors={len(flow_snapshot.get('flowContents', {}).get('processors', []))}, connections={len(flow_snapshot.get('flowContents', {}).get('connections', []))}")

            log.debug(f"Sending import request to NiFi: {import_data.keys()}")
            import_response = await nifi_client.session.post(import_url, json=import_data)
            
            log.debug(f"Import response status: {import_response.status}")
            log.debug(f"Import response headers: {dict(import_response.headers)}")

            # NiFi import can return 200, 201, or sometimes other success codes
            if import_response.status in [200, 201, 202]:
                process_group = await import_response.json()
                log.info(f"Successfully imported Registry flow for process group '{process_group_name}'")
                await self._setup_version_control(
                    nifi_client, process_group, registry_client_id,
                    bucket_id, flow_id, flow_version
                )
                return process_group
            else:
                # Get the error details from the response
                error_text = await import_response.text()
                # Enhanced error logging for NiFi Registry import
                log.error(f"=== NIFI REGISTRY IMPORT FAILURE DEBUG ===")
                log.error(f"Process Group: '{process_group_name}'")
                log.error(f"NiFi API Endpoint: {import_url}")
                log.error(f"HTTP Status: {import_response.status} ({import_response.reason})")
                log.error(f"Response Headers: {dict(import_response.headers)}")
                log.error(f"Response Body: {error_text}")
                
                # Detailed request analysis
                flow_contents = flow_snapshot.get('flowContents', {})
                processors = flow_contents.get('processors', [])
                connections = flow_contents.get('connections', [])
                
                log.error(f"Import Request Analysis:")
                log.error(f"  - Total Processors: {len(processors)}")
                log.error(f"  - Total Connections: {len(connections)}")
                log.error(f"  - Payload Size: {len(json.dumps(import_data))} bytes")
                
                # Analyze each processor for potential import issues
                for i, processor in enumerate(processors):
                    proc_name = processor.get('name', 'Unknown')
                    proc_type = processor.get('type', 'Unknown')
                    bundle = processor.get('bundle', {})
                    properties = processor.get('properties', {})
                    
                    log.error(f"  Processor {i+1}: {proc_name}")
                    log.error(f"    - Type: {proc_type}")
                    log.error(f"    - Bundle: {bundle.get('group', 'N/A')}/{bundle.get('artifact', 'N/A')}/{bundle.get('version', 'N/A')}")
                    log.error(f"    - Properties: {len(properties)} configured")
                    log.error(f"    - Required fields: id={bool(processor.get('identifier'))}, name={bool(proc_name)}, type={bool(proc_type)}")
                    
                    # Check for parameter references that might cause issues
                    param_refs = []
                    for prop_name, prop_value in properties.items():
                        if isinstance(prop_value, str) and ('#{' in prop_value or '${' in prop_value):
                            param_refs.append(f"{prop_name}={prop_value}")
                    
                    if param_refs:
                        log.error(f"    - Parameter references: {param_refs}")
                
                # Analyze connections for potential issues
                for i, connection in enumerate(connections):
                    source = connection.get('source', {})
                    destination = connection.get('destination', {})
                    log.error(f"  Connection {i+1}: {source.get('id', 'Unknown')} -> {destination.get('id', 'Unknown')}")
                    log.error(f"    - Relationships: {connection.get('selectedRelationships', [])}")
                    log.error(f"    - Name: {connection.get('name', 'Unnamed')}")
                
                # Look for specific NiFi import error patterns
                if error_text:
                    if "validation" in error_text.lower():
                        log.error("NIFI VALIDATION ERROR detected in response")
                    if "bundle" in error_text.lower():
                        log.error("NIFI BUNDLE ERROR detected in response")
                    if "property" in error_text.lower():
                        log.error("NIFI PROPERTY ERROR detected in response")
                    if "parameter" in error_text.lower():
                        log.error("NIFI PARAMETER ERROR detected in response")
                    if "connection" in error_text.lower():
                        log.error("NIFI CONNECTION ERROR detected in response")
                        
                    # Try to extract structured error if it's JSON
                    try:
                        error_json = json.loads(error_text)
                        log.error(f"Structured NiFi error response: {json.dumps(error_json, indent=2)}")
                    except:
                        log.error(f"NiFi error response is not JSON, raw text: '{error_text}'")
                
                log.error(f"=== END NIFI IMPORT DEBUG ===")
                
                # Try to get detailed error information from NiFi bulletins
                processor_types = [p.get('type') for p in flow_snapshot.get('flowContents', {}).get('processors', [])]
                detailed_error_info = await self._get_recent_nifi_bulletins(
                    nifi_client, 
                    process_group_name=process_group_name,
                    parent_group_id=parent_group_id,
                    processor_types=processor_types
                )
                
                # Sometimes NiFi returns HTTP 500 even for successful operations
                # Let's check if the response actually contains valid process group data
                try:
                    import json as json_module
                    response_json = json_module.loads(error_text) if error_text else None
                    if response_json and isinstance(response_json, dict):
                        # Check if it looks like a valid process group response
                        if 'id' in response_json or ('component' in response_json and 'id' in response_json.get('component', {})):
                            log.warning(f"HTTP {import_response.status} but response contains valid process group data, treating as success")
                            process_group = response_json
                            log.info(f"Successfully imported Registry flow for process group '{process_group_name}' (despite HTTP {import_response.status})")
                            await self._setup_version_control(
                                nifi_client, process_group, registry_client_id,
                                bucket_id, flow_id, flow_version
                            )
                            return process_group
                except (json_module.JSONDecodeError, TypeError) as e:
                    log.debug(f"Could not parse response as JSON: {e}")
                    pass
                
                # NiFi sometimes returns HTTP 500 even for successful operations
                # Let's verify if the process group was actually created by checking the parent group
                log.warning(f"HTTP {import_response.status} received, verifying if process group was actually created...")
                try:
                    # Get the process group flow using the correct NiFi API endpoint
                    flow_response = await nifi_client.session.get(f"{nifi_client.nifi_url}/flow/process-groups/{parent_group_id}")
                    flow_response.raise_for_status()
                    process_group_flow = await flow_response.json()
                    process_groups = process_group_flow.get('processGroupFlow', {}).get('flow', {}).get('processGroups', [])
                    
                    # Look for a newly created process group with matching name
                    matching_group = None
                    for pg in process_groups:
                        component = pg.get('component', {})
                        if component.get('name') == process_group_name:
                            matching_group = pg
                            break
                    
                    if matching_group:
                        log.info(f"Process group '{process_group_name}' was created despite HTTP {import_response.status}")
                        log.info(f"Found process group with ID: {matching_group.get('id')}")
                        
                        # DEBUG: Check what actually got imported
                        log.debug("=== POST-IMPORT VERIFICATION ===")
                        expected_processors = flow_snapshot.get("flowContents", {}).get("processors", [])
                        expected_connections = flow_snapshot.get("flowContents", {}).get("connections", [])
                        
                        try:
                            # Get the actual processors in the imported process group
                            processors_response = await nifi_client.get_processors_in_group(matching_group.get('id'))
                            log.debug(f"EXPECTED: {len(expected_processors)} processors, {len(expected_connections)} connections")
                            log.debug(f"ACTUAL IMPORTED: {len(processors_response)} processors")
                            
                            # Check if import was complete
                            if len(processors_response) != len(expected_processors):
                                log.error(f"IMPORT INCOMPLETE: Expected {len(expected_processors)} processors, got {len(processors_response)}")
                                log.error("This indicates a partial NiFi import failure. Deleting incomplete process group...")
                                
                                # Delete the incomplete process group
                                try:
                                    await nifi_client.delete_process_group(matching_group.get('id'))
                                    log.info("Deleted incomplete process group")
                                except Exception as delete_error:
                                    log.error(f"Failed to delete incomplete process group: {delete_error}")
                                
                                # Raise an error to indicate import failure
                                raise Exception(
                                    f"NiFi Registry import failed: Expected {len(expected_processors)} processors "
                                    f"but only {len(processors_response)} were imported. "
                                    f"This indicates a NiFi import bug or template compatibility issue."
                                )
                            
                            # Verify connections if processors are correct
                            try:
                                connections_response = await nifi_client.session.get(
                                    f"{nifi_client.nifi_url}/process-groups/{matching_group.get('id')}/connections"
                                )
                                if connections_response.status == 200:
                                    connections_data = await connections_response.json()
                                    connections_list = connections_data.get("connections", [])
                                    log.debug(f"ACTUAL IMPORTED - Connections count: {len(connections_list)}")
                                    
                                    if len(connections_list) != len(expected_connections):
                                        log.error(f"CONNECTION IMPORT INCOMPLETE: Expected {len(expected_connections)} connections, got {len(connections_list)}")
                                        
                                        # Delete the incomplete process group
                                        try:
                                            await nifi_client.delete_process_group(matching_group.get('id'))
                                            log.info("Deleted process group with incomplete connections")
                                        except Exception as delete_error:
                                            log.error(f"Failed to delete incomplete process group: {delete_error}")
                                        
                                        raise Exception(
                                            f"NiFi Registry import failed: Expected {len(expected_connections)} connections "
                                            f"but only {len(connections_list)} were imported."
                                        )
                                    
                                    log.info("✅ Import verification passed: All processors and connections imported correctly")
                                else:
                                    log.error(f"Failed to verify connections: {connections_response.status}")
                            except Exception as e:
                                log.error(f"Error verifying connections: {e}")
                                raise
                                
                        except Exception as e:
                            log.error(f"Error during post-import verification: {e}")
                            raise
                        
                        # Process groups imported from Registry automatically have version control
                        # No need to manually set up version control
                        log.info(f"Process group imported from Registry already has version control configured")
                        return matching_group
                    else:
                        log.error(f"Process group '{process_group_name}' was not found in parent group after import attempt")
                        
                except Exception as verification_error:
                    log.error(f"Failed to verify process group creation: {verification_error}")
                
                # Try to parse error details from NiFi response
                try:
                    if error_text:
                        import json as json_module
                        error_data = json_module.loads(error_text)
                        if isinstance(error_data, dict) and 'message' in error_data:
                            detailed_error = error_data['message']
                        else:
                            detailed_error = error_text
                    else:
                        detailed_error = f"HTTP {import_response.status} with no response body"
                except json_module.JSONDecodeError:
                    detailed_error = error_text

                # Include detailed error information in the exception message
                error_summary = f"NiFi Registry import failed for '{process_group_name}'"
                
                # Add detailed error information if available
                if detailed_error_info:
                    error_summary += f": {detailed_error_info}"
                elif detailed_error and detailed_error != "An unexpected error has occurred. Please check the logs for additional details.":
                    error_summary += f": {detailed_error}"
                else:
                    # If no detailed error, provide our comprehensive analysis
                    processor_count = len(flow_snapshot.get('flowContents', {}).get('processors', []))
                    connection_count = len(flow_snapshot.get('flowContents', {}).get('connections', []))
                    
                    # Get detailed analysis of what was expected vs what happened
                    analysis_details = await self._analyze_import_failure(
                        nifi_client, flow_snapshot, parent_group_id, process_group_name
                    )
                    
                    if analysis_details:
                        error_summary += f": {analysis_details}"
                    else:
                        error_summary += f": Template defines {processor_count} processors and {connection_count} connections, but NiFi returned HTTP {import_response.status} during import. This typically indicates parameter context issues, bundle compatibility problems, or property validation failures during template synchronization."
                
                if import_response.status:
                    error_summary += f" (HTTP {import_response.status})"
                
                raise RegistryImportError(
                    error_summary,
                    status_code=import_response.status,
                    response_text=error_text
                )
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
    
    async def _get_recent_nifi_bulletins(
        self,
        nifi_client: NiFiAPIClient,
        process_group_name: str = None,
        parent_group_id: str = None,
        processor_types: List[str] = None
    ) -> str:
        """
        Get targeted NiFi bulletins for specific deployment failure.
        
        Args:
            nifi_client: NiFi API client
            process_group_name: Process group name to filter bulletins
            parent_group_id: Parent group ID to filter bulletins
            processor_types: List of processor types involved in the deployment
            
        Returns:
            String containing detailed error information from bulletins
        """
        try:
            log.debug(f"Fetching targeted NiFi bulletins for deployment failure: {process_group_name}")
            
            # Try multiple targeted approaches to get relevant bulletins
            error_messages = []
            
            # 1. Get bulletins filtered by group ID if available
            if parent_group_id:
                group_bulletins = await self._get_bulletins_by_group(nifi_client, parent_group_id)
                if group_bulletins:
                    error_messages.extend(group_bulletins)
            
            # 2. Get bulletins filtered by message patterns related to our deployment
            deployment_patterns = [
                "import",
                "processor.*create",
                "template",
                "registry",
                "flow.*synchroniz",
                "parameter.*context",
                "bundle.*missing",
                "property.*invalid"
            ]
            
            for pattern in deployment_patterns:
                pattern_bulletins = await self._get_bulletins_by_message_pattern(nifi_client, pattern)
                if pattern_bulletins:
                    error_messages.extend(pattern_bulletins)
            
            # 3. Get bulletins by processor types if we know what failed
            if processor_types:
                for proc_type in processor_types:
                    proc_name = proc_type.split('.')[-1]  # Get class name like "GetFile"
                    type_bulletins = await self._get_bulletins_by_message_pattern(nifi_client, proc_name)
                    if type_bulletins:
                        error_messages.extend(type_bulletins)
            
            # 4. Fall back to recent bulletins if nothing specific found
            if not error_messages:
                recent_bulletins = await self._get_recent_bulletins_fallback(nifi_client)
                if recent_bulletins:
                    error_messages.extend(recent_bulletins)
            
            if error_messages:
                # Remove duplicates and return most relevant errors
                unique_errors = list(dict.fromkeys(error_messages))[:5]
                detailed_error = " | ".join(unique_errors)
                log.info(f"Found {len(unique_errors)} specific error bulletins: {detailed_error}")
                return detailed_error
            else:
                log.debug("No specific error bulletins found for deployment failure")
                return None
                
        except Exception as e:
            log.error(f"Error fetching targeted NiFi bulletins: {e}")
            return None
    
    async def _get_bulletins_by_group(self, nifi_client: NiFiAPIClient, group_id: str) -> List[str]:
        """Get bulletins filtered by specific group ID."""
        try:
            params = {"groupId": group_id, "limit": "20"}
            url = f"{nifi_client.nifi_url}/flow/bulletin-board"
            
            bulletin_response = await nifi_client.session.get(url, params=params)
            if bulletin_response.status == 200:
                bulletin_data = await bulletin_response.json()
                return self._extract_error_messages_from_bulletins(bulletin_data.get("bulletins", []))
        except Exception as e:
            log.debug(f"Failed to get group bulletins: {e}")
        return []
    
    async def _get_bulletins_by_message_pattern(self, nifi_client: NiFiAPIClient, pattern: str) -> List[str]:
        """Get bulletins filtered by message pattern."""
        try:
            params = {"message": pattern, "limit": "10"}
            url = f"{nifi_client.nifi_url}/flow/bulletin-board"
            
            bulletin_response = await nifi_client.session.get(url, params=params)
            if bulletin_response.status == 200:
                bulletin_data = await bulletin_response.json()
                return self._extract_error_messages_from_bulletins(bulletin_data.get("bulletins", []))
        except Exception as e:
            log.debug(f"Failed to get bulletins by pattern '{pattern}': {e}")
        return []
    
    async def _get_recent_bulletins_fallback(self, nifi_client: NiFiAPIClient) -> List[str]:
        """Fallback to get recent bulletins."""
        try:
            params = {"limit": "50"}
            url = f"{nifi_client.nifi_url}/flow/bulletin-board"
            
            bulletin_response = await nifi_client.session.get(url, params=params)
            
            if bulletin_response.status == 200:
                bulletin_data = await bulletin_response.json()
                return self._extract_error_messages_from_bulletins(bulletin_data.get("bulletins", []))
        except Exception as e:
            log.debug(f"Failed to get recent bulletins: {e}")
        return []
    
    def _extract_error_messages_from_bulletins(self, bulletins: List[Dict]) -> List[str]:
        """Extract error messages from bulletin entities."""
        error_messages = []
        
        for bulletin_entity in bulletins:
            bulletin = bulletin_entity.get("bulletin", {})
            level = bulletin.get("level", "").upper()
            message = bulletin.get("message", "")
            source_name = bulletin.get("sourceName", "")
            
            # Focus on ERROR and WARN level bulletins
            if level in ["ERROR", "WARN"] and message:
                source = source_name if source_name else "NiFi"
                formatted_message = f"[{level}] {source}: {message}"
                error_messages.append(formatted_message)
        
        return error_messages

    async def _analyze_import_failure(
        self,
        nifi_client: NiFiAPIClient,
        flow_snapshot: Dict[str, Any],
        parent_group_id: str,
        process_group_name: str
    ) -> str:
        """Analyze what went wrong during import by comparing expected vs actual."""
        try:
            # Get expected processors and connections
            flow_contents = flow_snapshot.get('flowContents', {})
            expected_processors = flow_contents.get('processors', [])
            expected_connections = flow_contents.get('connections', [])
            
            log.debug(f"Analyzing import failure for {len(expected_processors)} processors, {len(expected_connections)} connections")
            
            # Check if process group was created
            try:
                flow_response = await nifi_client.session.get(f"{nifi_client.nifi_url}/flow/process-groups/{parent_group_id}")
                if flow_response.status == 200:
                    process_group_flow = await flow_response.json()
                    process_groups = process_group_flow.get('processGroupFlow', {}).get('flow', {}).get('processGroups', [])
                    
                    # Find our process group
                    matching_group = None
                    for pg in process_groups:
                        component = pg.get('component', {})
                        if component.get('name') == process_group_name:
                            matching_group = pg
                            break
                    
                    if matching_group:
                        # Get actual processors created
                        actual_processors = await nifi_client.get_processors_in_group(matching_group.get('id'))
                        
                        # Get detailed verification errors for failed processors
                        verification_errors = await self._get_processor_verification_errors(
                            nifi_client, expected_processors, actual_processors, matching_group.get('id')
                        )
                        
                        # Analyze the failure
                        analysis = []
                        analysis.append(f"Expected {len(expected_processors)} processors but only {len(actual_processors)} were created")
                        
                        # Identify which processors failed
                        expected_types = [p.get('type', 'Unknown') for p in expected_processors]
                        created_types = []
                        
                        for actual_proc in actual_processors:
                            proc_type = actual_proc.get('component', {}).get('type', 'Unknown')
                            created_types.append(proc_type)
                        
                        failed_types = [ptype for ptype in expected_types if ptype not in created_types]
                        succeeded_types = [ptype for ptype in expected_types if ptype in created_types]
                        
                        if failed_types:
                            failed_names = [ptype.split('.')[-1] for ptype in failed_types]
                            analysis.append(f"Failed processors: {', '.join(failed_names)}")
                        
                        if succeeded_types:
                            succeeded_names = [ptype.split('.')[-1] for ptype in succeeded_types]
                            analysis.append(f"Succeeded processors: {', '.join(succeeded_names)}")
                        
                        # Analyze likely causes based on failed processor types
                        likely_causes = []
                        for failed_type in failed_types:
                            if 'GetFile' in failed_type:
                                likely_causes.append("GetFile failure often indicates Input Directory parameter context issues")
                            elif 'UpdateAttribute' in failed_type:
                                likely_causes.append("UpdateAttribute failure may indicate bundle compatibility or property validation issues")
                            elif any(param_ref in str(expected_processors) for param_ref in ['#{', '${']):
                                likely_causes.append("Parameter context references may not be properly resolved")
                        
                        if likely_causes:
                            analysis.append(f"Likely causes: {'; '.join(likely_causes)}")
                        
                        # Add detailed verification errors if available
                        if verification_errors:
                            # Prioritize the detailed verification errors over generic causes
                            analysis = [analysis[0]]  # Keep only the main summary
                            analysis.append(f"Detailed NiFi validation errors: {verification_errors}")
                        
                        result = ". ".join(analysis)
                        log.debug(f"Full analysis result length: {len(result)} chars")
                        return result
            
            except Exception as e:
                log.debug(f"Failed to analyze import failure details: {e}")
                
            return None
            
        except Exception as e:
            log.error(f"Error analyzing import failure: {e}")
            return None

    async def _get_processor_verification_errors(
        self,
        nifi_client: NiFiAPIClient,
        expected_processors: List[Dict],
        actual_processors: List[Dict],
        process_group_id: str
    ) -> str:
        """Get detailed verification errors for processors that failed to be created."""
        try:
            verification_errors = []
            
            # Get the processors that were actually created
            created_processor_types = set()
            for actual_proc in actual_processors:
                proc_type = actual_proc.get('component', {}).get('type', '')
                created_processor_types.add(proc_type)
            
            # For each expected processor that wasn't created, try to get verification errors
            for expected_proc in expected_processors:
                expected_type = expected_proc.get('type', '')
                expected_name = expected_proc.get('name', 'Unknown')
                
                if expected_type not in created_processor_types:
                    # This processor failed to be created, try to get verification details
                    log.debug(f"Getting verification errors for failed processor: {expected_name} ({expected_type})")
                    
                    try:
                        # Create a temporary processor to test verification
                        temp_processor = await nifi_client.create_processor(
                            parent_group_id=process_group_id,
                            processor_type=expected_type,
                            name=f"TEMP_VERIFY_{expected_name}",
                            position={"x": 0, "y": 0}
                        )
                        
                        temp_id = temp_processor["id"]
                        
                        try:
                            # Apply the expected properties and get verification results
                            verification_request = {
                                "request": {
                                    "componentId": temp_id,
                                    "properties": expected_proc.get('properties', {})
                                }
                            }
                            
                            # Submit verification request
                            log.debug(f"Submitting verification request for {expected_name}")
                            verify_response = await nifi_client.session.post(
                                f"{nifi_client.nifi_url}/processors/{temp_id}/config/verification-requests",
                                json=verification_request
                            )
                            
                            log.debug(f"Verification request response status: {verify_response.status}")
                            if verify_response.status == 200:
                                verify_data = await verify_response.json()
                                request_id = verify_data.get("request", {}).get("requestId")
                                log.debug(f"Got verification request ID: {request_id}")
                                
                                if request_id:
                                    # Poll for verification results
                                    verification_result = await self._poll_verification_results(
                                        nifi_client, temp_id, request_id
                                    )
                                    
                                    log.debug(f"Verification result for {expected_name}: {verification_result}")
                                    if verification_result:
                                        verification_errors.append(f"{expected_name}: {verification_result}")
                                else:
                                    log.debug(f"No request ID returned for {expected_name}")
                            else:
                                # Get error details from verification request failure
                                error_text = await verify_response.text()
                                log.debug(f"Verification request failed for {expected_name}: {verify_response.status} - {error_text}")
                                
                                # Even if verification API fails, we can still provide useful info
                                # Since the processor was created successfully, the issue is likely in the properties
                                properties = expected_proc.get('properties', {})
                                if properties:
                                    param_refs = [f"{k}={v}" for k, v in properties.items() if isinstance(v, str) and ('#{' in v or '${' in v)]
                                    if param_refs:
                                        verification_errors.append(f"{expected_name}: Verification API failed, but processor has parameter references that may be unresolved: {', '.join(param_refs)}")
                                    else:
                                        verification_errors.append(f"{expected_name}: Verification API failed - may indicate property validation issues")
                            
                        finally:
                            # Clean up temporary processor
                            try:
                                current_processor = await nifi_client.get_processor(temp_id)
                                current_version = current_processor.get("revision", {}).get("version", 0)
                                await nifi_client.session.delete(f"{nifi_client.nifi_url}/processors/{temp_id}?version={current_version}")
                            except Exception as cleanup_error:
                                log.debug(f"Failed to clean up temp processor: {cleanup_error}")
                                
                    except Exception as e:
                        log.debug(f"Failed to get verification errors for {expected_name}: {e}")
                        # If we can't create the processor, that itself is valuable information
                        verification_errors.append(f"{expected_name}: Failed to create processor - {str(e)}")
            
            result = "; ".join(verification_errors) if verification_errors else None
            log.debug(f"Final verification errors result: {result}")
            return result
            
        except Exception as e:
            log.error(f"Error getting processor verification errors: {e}")
            return None

    async def _poll_verification_results(
        self,
        nifi_client: NiFiAPIClient,
        processor_id: str,
        request_id: str,
        max_polls: int = 10
    ) -> str:
        """Poll verification request results until complete."""
        import asyncio
        
        for _ in range(max_polls):
            try:
                result_response = await nifi_client.session.get(
                    f"{nifi_client.nifi_url}/processors/{processor_id}/config/verification-requests/{request_id}"
                )
                
                if result_response.status == 200:
                    result_data = await result_response.json()
                    request = result_data.get("request", {})
                    
                    if request.get("complete", False):
                        # Extract failure reasons and results
                        errors = []
                        
                        failure_reason = request.get("failureReason")
                        if failure_reason:
                            errors.append(failure_reason)
                        
                        # Check verification results
                        results = request.get("results", [])
                        for result in results:
                            if result.get("outcome") != "SUCCESSFUL":
                                step_name = result.get("verificationStepName", "Unknown step")
                                explanation = result.get("explanation", "No explanation provided")
                                errors.append(f"{step_name}: {explanation}")
                        
                        # Check update steps for failures
                        update_steps = request.get("updateSteps", [])
                        for step in update_steps:
                            step_failure = step.get("failureReason")
                            if step_failure:
                                step_desc = step.get("description", "Unknown step")
                                errors.append(f"{step_desc}: {step_failure}")
                        
                        return "; ".join(errors) if errors else "Verification completed without specific errors"
                
                # Wait before polling again
                await asyncio.sleep(0.5)
                
            except Exception as e:
                log.debug(f"Error polling verification results: {e}")
                break
        
        return "Verification timed out or failed to complete"

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
            log.debug(f"Version control setup - process_group keys: {list(process_group.keys())}")
            log.debug(f"Version control setup - process_group structure: {process_group}")
            
            # Handle different process group structures
            if 'component' in process_group and 'id' in process_group['component']:
                pg_id = process_group['component']['id']
                pg_revision = process_group.get('revision', {'version': 0})
            elif 'id' in process_group:
                pg_id = process_group['id']  
                pg_revision = process_group.get('revision', {'version': 0})
            else:
                raise ValueError(f"Cannot determine process group ID from structure: {process_group.keys()}")
                
            log.debug(f"Using process group ID: {pg_id}")
            log.debug(f"Using process group revision: {pg_revision}")
            start_version_control_data = {
                "processGroupRevision": pg_revision,
                "versionControlInformation": {
                    "registryId": registry_client_id,
                    "bucketId": bucket_id,
                    "flowId": flow_id,
                    "version": flow_version,
                    "storageLocation": bucket_id
                },
                "disconnectedNodeAcknowledged": False
            }
            
            log.debug(f"Version control request data: {start_version_control_data}")
            vc_response = await nifi_client.session.post(
                f"{nifi_client.nifi_url}/versions/process-groups/{pg_id}",
                json=start_version_control_data
            )
            if vc_response.status == 200:
                log.info(f"Successfully set up version control for process group {pg_id}")
                return True
            else:
                vc_response_text = await vc_response.text()
                log.error(f"Version control setup returned {vc_response.status}: {vc_response_text}")
                raise VersionControlError(
                    f"Version control setup failed with HTTP {vc_response.status}",
                    status_code=vc_response.status
                )
        except VersionControlError:
            raise
        except Exception as e:
            log.error(f"Failed to set up version control: {str(e)}")
            raise VersionControlError(f"Version control setup error: {str(e)}") from e

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
                        log.info(f"Successfully created processor: {processor.get('name')}")
                    else:
                        error_text = await response.text()
                        log.error(f"Failed to create processor {processor.get('name')}: {response.status} - {error_text}")
                        raise ProcessorCreationError(
                            f"HTTP {response.status} when creating processor",
                            processor_name=processor.get('name'),
                            errors=[error_text]
                        )
                except ProcessorCreationError:
                    raise
                except Exception as proc_error:
                    log.error(f"Error creating processor {processor.get('name')}: {str(proc_error)}")
                    raise ProcessorCreationError(
                        f"Unexpected error during processor creation: {str(proc_error)}",
                        processor_name=processor.get('name')
                    ) from proc_error

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
                        if response.status == 201:
                            log.info(f"Successfully created connection: {connection.get('name', 'unnamed')}")
                        else:
                            error_text = await response.text()
                            log.error(f"Failed to create connection {connection.get('name', 'unnamed')}: {response.status} - {error_text}")
                            raise ConnectionCreationError(
                                f"HTTP {response.status} when creating connection",
                                connection_name=connection.get('name'),
                                errors=[error_text]
                            )
                    else:
                        missing_ids = []
                        if not source_id:
                            missing_ids.append(f"source: {connection.get('source', {}).get('id')}")
                        if not dest_id:
                            missing_ids.append(f"destination: {connection.get('destination', {}).get('id')}")
                        
                        log.error(f"Cannot create connection {connection.get('name', 'unnamed')}: missing processor IDs for {', '.join(missing_ids)}")
                        raise ConnectionCreationError(
                            f"Cannot map processor IDs for connection",
                            connection_name=connection.get('name'),
                            errors=[f"Missing IDs: {', '.join(missing_ids)}"]
                        )
                except ConnectionCreationError:
                    raise
                except Exception as conn_error:
                    log.error(f"Error creating connection {connection.get('name', 'unnamed')}: {str(conn_error)}")
                    raise ConnectionCreationError(
                        f"Unexpected error during connection creation: {str(conn_error)}",
                        connection_name=connection.get('name')
                    ) from conn_error
        except (ProcessorCreationError, ConnectionCreationError):
            raise
        except Exception as e:
            log.error(f"Failed to manually populate process group: {str(e)}")
            raise ProcessorCreationError(f"Process group population failed: {str(e)}") from e

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
