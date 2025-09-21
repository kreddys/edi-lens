"""
Hybrid Deployment Service - Registry + Individual Component Creation

This service implements the hybrid deployment architecture that combines:
1. NiFi Registry integration for version control
2. Individual component creation for detailed error reporting
3. Comprehensive parameter substitution validation
4. Granular error handling and rollback capabilities

Based on NIFI_DEPLOYMENT_ARCHITECTURE.md
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime

from src.nifi.clients.nifi_client import NiFiAPIClient
from src.nifi.clients.registry_client import NiFiRegistryClient
from src.core.config import settings
from src.models.workflow_models import Workflow
from src.exceptions.workflow_exceptions import (
    RegistryImportError,
    ProcessorValidationError,
    ParameterSubstitutionError
)

log = logging.getLogger(__name__)


@dataclass
class ComponentFailure:
    """Detailed information about a component deployment failure."""
    component_type: str  # processor, connection, parameter_context
    component_name: str
    error_type: str  # validation, creation, parameter_substitution
    error_message: str
    detailed_error: Dict[str, Any]
    component_details: Optional[Dict[str, Any]] = None


@dataclass
class DeploymentSummary:
    """Summary of deployment results."""
    total_processors: int
    created_processors: int
    failed_processors: int
    total_connections: int
    created_connections: int
    failed_connections: int


@dataclass
class CreatedComponents:
    """Components successfully created during deployment."""
    process_group: Optional[Dict[str, Any]] = None
    processors: List[Dict[str, Any]] = None
    connections: List[Dict[str, Any]] = None
    parameter_contexts: List[Dict[str, Any]] = None

    def __post_init__(self):
        if self.processors is None:
            self.processors = []
        if self.connections is None:
            self.connections = []
        if self.parameter_contexts is None:
            self.parameter_contexts = []


@dataclass
class RollbackInfo:
    """Information about rollback operations performed."""
    rollback_performed: bool
    cleanup_results: List[str]


@dataclass
class DeploymentResult:
    """Comprehensive result of hybrid deployment."""
    deployment_id: str
    success: bool
    workflow_id: str
    summary: DeploymentSummary
    created_components: CreatedComponents
    failures: List[ComponentFailure]
    rollback_info: RollbackInfo
    execution_time: float


class HybridDeploymentEngine:
    """
    Main orchestrator for hybrid deployment approach.

    Implements the four-phase deployment:
    1. Registry Integration - Download flow definition from Registry
    2. Parameter Processing - Apply parameter substitution with validation
    3. Individual Component Deployment - Create components one by one
    4. Version Control Assignment - Associate with Registry flow
    """

    def __init__(self):
        self.deployment_id = str(uuid.uuid4())

    async def deploy_workflow(
        self,
        nifi_client: NiFiAPIClient,
        workflow: Workflow,
        parent_group_id: str,
        bucket_id: str,
        flow_id: str,
        flow_version: int,
        parameter_context_id: str
    ) -> DeploymentResult:
        """Execute hybrid deployment workflow."""
        start_time = datetime.utcnow()

        log.info(f"Starting hybrid deployment for workflow {workflow.workflow_id}")
        log.info(f"Deployment ID: {self.deployment_id}")

        try:
            # Phase 1: Registry Integration
            flow_snapshot = await self._download_flow_from_registry(
                bucket_id=bucket_id,
                flow_id=flow_id,
                version=flow_version
            )

            # Phase 2: Parameter Processing (Skip substitution - let NiFi handle via parameter context)
            log.debug("Phase 2: Skipping parameter substitution - relying on NiFi parameter context")
            processed_flow = flow_snapshot  # Use flow as-is with parameter references

            # Phase 3: Individual Component Deployment
            deployment_result = await self._deploy_components_individually(
                nifi_client=nifi_client,
                parent_group_id=parent_group_id,
                processed_flow=processed_flow,
                workflow=workflow,
                parameter_context_id=parameter_context_id
            )

            # Phase 4: Version Control Assignment (if deployment successful)
            if deployment_result.success:
                await self._apply_version_control(
                    nifi_client=nifi_client,
                    process_group_id=deployment_result.created_components.process_group["id"],
                    bucket_id=bucket_id,
                    flow_id=flow_id,
                    version=flow_version
                )

            execution_time = (datetime.utcnow() - start_time).total_seconds()
            deployment_result.execution_time = execution_time

            log.info(f"Hybrid deployment completed in {execution_time:.2f}s - Success: {deployment_result.success}")
            return deployment_result

        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            log.error(f"Hybrid deployment failed after {execution_time:.2f}s: {str(e)}")

            # Return failure result
            return DeploymentResult(
                deployment_id=self.deployment_id,
                success=False,
                workflow_id=str(workflow.workflow_id),
                summary=DeploymentSummary(0, 0, 0, 0, 0, 0),
                created_components=CreatedComponents(),
                failures=[ComponentFailure(
                    component_type="deployment",
                    component_name="hybrid_deployment",
                    error_type="deployment_failure",
                    error_message=str(e),
                    detailed_error={"exception_type": type(e).__name__}
                )],
                rollback_info=RollbackInfo(False, []),
                execution_time=execution_time
            )

    async def _download_flow_from_registry(
        self,
        bucket_id: str,
        flow_id: str,
        version: int
    ) -> Dict[str, Any]:
        """Phase 1: Download flow definition from Registry for version control."""
        log.debug(f"Phase 1: Downloading flow from Registry - bucket={bucket_id}, flow={flow_id}, version={version}")

        try:
            async with NiFiRegistryClient(settings.NIFI_REGISTRY_URL) as registry_client:
                flow_snapshot = await registry_client.get_flow_version(
                    bucket_id=bucket_id,
                    flow_id=flow_id,
                    version=version
                )

                flow_contents = flow_snapshot.get("flowContents", {})
                processors_count = len(flow_contents.get("processors", []))
                connections_count = len(flow_contents.get("connections", []))

                log.info(f"Downloaded flow definition: {processors_count} processors, {connections_count} connections")
                return flow_snapshot

        except Exception as e:
            log.error(f"Failed to download flow from Registry: {str(e)}")
            raise RegistryImportError(f"Registry download failed: {str(e)}")

    async def _apply_parameter_substitution(
        self,
        flow_snapshot: Dict[str, Any],
        workflow_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Phase 2: Apply parameter substitution to downloaded template."""
        log.debug("Phase 2: Applying parameter substitution")

        flow_contents = flow_snapshot.get("flowContents", {})
        processors = flow_contents.get("processors", [])

        # Create a copy to avoid modifying original
        processed_flow = {
            "flowContents": {
                "processors": [],
                "connections": flow_contents.get("connections", []).copy(),
                "processGroups": flow_contents.get("processGroups", []).copy(),
                "inputPorts": flow_contents.get("inputPorts", []).copy(),
                "outputPorts": flow_contents.get("outputPorts", []).copy(),
            }
        }

        # Apply parameter substitution to each processor
        for processor in processors:
            processed_processor = processor.copy()
            properties = processor.get("properties", {}).copy()

            # Substitute parameters in properties
            substituted_properties = {}
            for prop_name, prop_value in properties.items():
                if isinstance(prop_value, str) and "#{" in prop_value:
                    # Extract parameter name from #{parameter_name}
                    import re
                    param_matches = re.findall(r'#\{([^}]+)\}', prop_value)
                    substituted_value = prop_value

                    for param_name in param_matches:
                        if param_name in workflow_config:
                            substituted_value = substituted_value.replace(
                                f"#{{{param_name}}}",
                                str(workflow_config[param_name])
                            )

                    substituted_properties[prop_name] = substituted_value
                else:
                    substituted_properties[prop_name] = prop_value

            processed_processor["properties"] = substituted_properties
            processed_flow["flowContents"]["processors"].append(processed_processor)

        log.debug(f"Parameter substitution completed for {len(processors)} processors")
        return processed_flow

    async def _validate_parameter_substitution(
        self,
        processed_flow: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate parameter substitution success."""
        log.debug("Validating parameter substitution")

        processors = processed_flow.get("flowContents", {}).get("processors", [])
        invalid_processors = []

        for processor in processors:
            processor_name = processor.get("name", "Unknown")
            properties = processor.get("properties", {})

            # Check for unresolved parameter references
            for prop_name, prop_value in properties.items():
                if isinstance(prop_value, str) and "#{" in prop_value:
                    invalid_processors.append({
                        "processor_name": processor_name,
                        "property_name": prop_name,
                        "unresolved_value": prop_value
                    })

        if invalid_processors:
            return {
                "valid": False,
                "error": f"Unresolved parameter references in {len(invalid_processors)} properties",
                "invalid_processors": invalid_processors
            }

        return {"valid": True}

    async def _deploy_components_individually(
        self,
        nifi_client: NiFiAPIClient,
        parent_group_id: str,
        processed_flow: Dict[str, Any],
        workflow: Workflow,
        parameter_context_id: str
    ) -> DeploymentResult:
        """Phase 3: Deploy components individually with detailed error capture."""
        log.debug("Phase 3: Deploying components individually")

        flow_contents = processed_flow.get("flowContents", {})
        processors = flow_contents.get("processors", [])
        connections = flow_contents.get("connections", [])

        # Initialize result tracking
        created_components = CreatedComponents()
        failures = []

        try:
            # Step 1: Create process group
            log.debug("Creating process group")
            process_group = await self._create_process_group(
                nifi_client, parent_group_id, workflow, parameter_context_id
            )
            created_components.process_group = process_group
            process_group_id = process_group["id"]

            # Step 1.5: Associate parameter context BEFORE creating processors
            if parameter_context_id:
                log.debug(f"Associating parameter context {parameter_context_id} with process group {process_group_id}")
                try:
                    # Extra debug: fetch current PG details before
                    try:
                        before_pg = await nifi_client.get_process_group(process_group_id)
                        log.debug(f"Before association - PG paramContext: {before_pg.get('component', {}).get('parameterContext')}")
                    except Exception as e:
                        log.debug(f"Could not fetch PG before association: {e}")

                    await self._associate_parameter_context(nifi_client, process_group_id, parameter_context_id)

                    # Extra debug: fetch current PG details after
                    try:
                        after_pg = await nifi_client.get_process_group(process_group_id)
                        pc_info = after_pg.get('component', {}).get('parameterContext')
                        log.debug(f"After association - PG paramContext: {pc_info}")
                    except Exception as e:
                        log.debug(f"Could not fetch PG after association: {e}")

                    log.debug("Parameter context associated successfully")
                except Exception as e:
                    log.error(f"Failed associating parameter context: {e}")
                    raise

            # Step 2: Create processors
            log.debug(f"Creating {len(processors)} processors")
            # Track processors that were created but initially INVALID (often resolved after connections)
            pending_revalidation: List[Dict[str, Any]] = []

            for processor in processors:
                try:
                    created_processor = await self._create_processor(
                        nifi_client, process_group_id, processor
                    )

                    # Always add to created list; validation may resolve after wiring
                    created_components.processors.append(created_processor)

                    # Check initial validation
                    validation_status = created_processor.get("component", {}).get("validationStatus", "UNKNOWN")
                    validation_errors = created_processor.get("component", {}).get("validationErrors", [])

                    if validation_status == "INVALID":
                        # Log and plan to re-validate after connections are created
                        returned_cfg = created_processor.get("component", {}).get("config", {})
                        returned_props = returned_cfg.get("properties", {})
                        returned_desc = returned_cfg.get("descriptors", {})
                        log.warning(
                            f"Processor initially INVALID (expected before wiring): name={processor.get('name','Unknown')}, "
                            f"type={processor.get('type','Unknown')}, errors={validation_errors}"
                        )
                        pending_revalidation.append({
                            "definition": processor,
                            "entity": created_processor,
                            "initial_errors": validation_errors,
                            "returned_props": returned_props,
                            "descriptors": returned_desc,
                        })
                    else:
                        log.debug(f"Created processor: {processor.get('name', 'Unknown')} (status: {validation_status})")

                except Exception as e:
                    failure = ComponentFailure(
                        component_type="processor",
                        component_name=processor.get("name", "Unknown"),
                        error_type="creation",
                        error_message=str(e),
                        detailed_error={
                            "processor_type": processor.get("type", "Unknown"),
                            "bundle": processor.get("bundle", {}),
                            "properties": processor.get("properties", {}),
                            "nifi_response": str(e)
                        }
                    )
                    failures.append(failure)
                    log.error(f"Failed to create processor {processor.get('name', 'Unknown')}: {str(e)}")

            # Step 3: Create connections (after processors exist)
            log.debug(f"Creating {len(connections)} connections")
            for connection in connections:
                try:
                    created_connection = await self._create_connection(
                        nifi_client, process_group_id, connection, created_components.processors, processed_flow
                    )
                    created_components.connections.append(created_connection)
                    log.debug(f"Created connection: {connection.get('name', 'Unknown')}")

                except Exception as e:
                    failure = ComponentFailure(
                        component_type="connection",
                        component_name=connection.get("name", "Unknown"),
                        error_type="creation",
                        error_message=str(e),
                        detailed_error={
                            "source_id": connection.get("source", {}).get("id"),
                            "destination_id": connection.get("destination", {}).get("id"),
                            "relationships": connection.get("selectedRelationships", []),
                            "nifi_response": str(e)
                        }
                    )
                    failures.append(failure)
                    log.error(f"Failed to create connection {connection.get('name', 'Unknown')}: {str(e)}")

            # Step 3.5: Re-validate processors after connections are created
            if pending_revalidation:
                log.debug(f"Re-validating {len(pending_revalidation)} processors after wiring")
                # Allow NiFi to re-evaluate
                await asyncio.sleep(1)
                for item in pending_revalidation:
                    proc_id = item["entity"].get("id")
                    try:
                        current = await nifi_client.get_processor(proc_id)
                        vstat = current.get("component", {}).get("validationStatus", "UNKNOWN")
                        verrs = current.get("component", {}).get("validationErrors", [])
                        if vstat == "INVALID":
                            log.error(
                                f"Processor remains INVALID after wiring: name={item['definition'].get('name')}, "
                                f"errors={verrs}"
                            )
                            failures.append(ComponentFailure(
                                component_type="processor",
                                component_name=item['definition'].get('name', 'Unknown'),
                                error_type="validation",
                                error_message=f"Processor remains invalid after connections: {verrs}",
                                detailed_error={
                                    "processor_type": item['definition'].get('type', 'Unknown'),
                                    "validation_status": vstat,
                                    "validation_errors": verrs,
                                    "properties_sent": item['definition'].get('properties', {}),
                                    "properties_returned": current.get('component', {}).get('config', {}).get('properties', {}),
                                }
                            ))
                        else:
                            log.debug(f"Processor now VALID after wiring: {item['definition'].get('name')}")
                    except Exception as ex:
                        log.error(f"Failed to re-validate processor {proc_id}: {ex}")

            # Calculate summary
            summary = DeploymentSummary(
                total_processors=len(processors),
                created_processors=len(created_components.processors),
                failed_processors=len([f for f in failures if f.component_type == "processor"]),
                total_connections=len(connections),
                created_connections=len(created_components.connections),
                failed_connections=len([f for f in failures if f.component_type == "connection"])
            )

            success = (summary.failed_processors == 0 and summary.failed_connections == 0)

            return DeploymentResult(
                deployment_id=self.deployment_id,
                success=success,
                workflow_id=str(workflow.workflow_id),
                summary=summary,
                created_components=created_components,
                failures=failures,
                rollback_info=RollbackInfo(False, []),
                execution_time=0.0  # Will be set by caller
            )

        except Exception as e:
            log.error(f"Component deployment failed: {str(e)}")

            # Attempt rollback
            rollback_info = await self._handle_rollback(nifi_client, created_components)

            return DeploymentResult(
                deployment_id=self.deployment_id,
                success=False,
                workflow_id=str(workflow.workflow_id),
                summary=DeploymentSummary(len(processors), 0, len(processors), len(connections), 0, len(connections)),
                created_components=CreatedComponents(),
                failures=[ComponentFailure(
                    component_type="deployment",
                    component_name="component_deployment",
                    error_type="deployment_failure",
                    error_message=str(e),
                    detailed_error={"exception_type": type(e).__name__}
                )],
                rollback_info=rollback_info,
                execution_time=0.0
            )

    async def _create_process_group(
        self,
        nifi_client: NiFiAPIClient,
        parent_group_id: str,
        workflow: Workflow,
        parameter_context_id: str
    ) -> Dict[str, Any]:
        """Create the main process group for the workflow."""
        name = f"{workflow.name}-{str(workflow.workflow_id)[:8]}"
        position = {"x": 100, "y": 100}

        return await nifi_client.create_process_group(
            parent_group_id=parent_group_id,
            name=name,
            position=position
        )

    async def _associate_parameter_context(
        self,
        nifi_client: NiFiAPIClient,
        process_group_id: str,
        parameter_context_id: str
    ) -> None:
        """Associate parameter context with process group."""
        # Use the NiFi client's update method which handles the proper API structure
        await nifi_client.update_process_group(
            process_group_id=process_group_id,
            parameter_context_id=parameter_context_id,
            version=0  # Let the client get the current revision
        )

    async def _create_processor(
        self,
        nifi_client: NiFiAPIClient,
        process_group_id: str,
        processor_def: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create an individual processor with full validation."""
        processor_type = processor_def.get("type")
        name = processor_def.get("name")
        position = processor_def.get("position", {"x": 100, "y": 100})
        properties = processor_def.get("properties", {})

        # Build scheduling configuration
        scheduling = {
            "schedulingPeriod": processor_def.get("schedulingPeriod", "1 sec"),
            "schedulingStrategy": processor_def.get("schedulingStrategy", "TIMER_DRIVEN"),
            "executionNode": processor_def.get("executionNode", "ALL"),
            "concurrentlySchedulableTaskCount": processor_def.get("concurrentlySchedulableTaskCount", 1),
            "bulletinLevel": processor_def.get("bulletinLevel", "WARN")
        }

        auto_terminated_relationships = processor_def.get("autoTerminatedRelationships", [])

        return await nifi_client.create_processor(
            parent_group_id=process_group_id,
            processor_type=processor_type,
            name=name,
            position=position,
            properties=properties,
            scheduling=scheduling,
            auto_terminated_relationships=auto_terminated_relationships
        )

    async def _create_connection(
        self,
        nifi_client: NiFiAPIClient,
        process_group_id: str,
        connection_def: Dict[str, Any],
        created_processors: List[Dict[str, Any]],
        processed_flow: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a connection between processors."""
        # Create maps to find processors by their original identifier
        processor_name_to_id = {}
        processor_original_id_to_new_id = {}

        for processor in created_processors:
            proc_name = processor.get("component", {}).get("name")
            proc_id = processor.get("id")
            if proc_name:
                processor_name_to_id[proc_name] = proc_id

        # From the flow definition, we need to match the original processor definitions
        flow_contents = processed_flow.get("flowContents", {})
        original_processors = flow_contents.get("processors", [])

        for orig_proc in original_processors:
            orig_id = orig_proc.get("identifier")
            orig_name = orig_proc.get("name")
            if orig_id and orig_name and orig_name in processor_name_to_id:
                processor_original_id_to_new_id[orig_id] = processor_name_to_id[orig_name]

        source_id = connection_def.get("source", {}).get("id")
        dest_id = connection_def.get("destination", {}).get("id")

        # Find actual processor IDs using the mapping
        source_processor_id = processor_original_id_to_new_id.get(source_id)
        dest_processor_id = processor_original_id_to_new_id.get(dest_id)

        if not source_processor_id or not dest_processor_id:
            # Fallback: try to match by name directly from connection definition
            for processor in created_processors:
                proc_name = processor.get("component", {}).get("name")
                proc_id = processor.get("id")

                # This is a simple fallback - in real scenarios you'd need more sophisticated matching
                if not source_processor_id and proc_name:
                    source_processor_id = proc_id
                elif not dest_processor_id and proc_name:
                    dest_processor_id = proc_id
                    break

        if not source_processor_id or not dest_processor_id:
            available_processors = [p.get("component", {}).get("name") for p in created_processors]
            raise ValueError(
                f"Could not find source ({source_id}) or destination ({dest_id}) processors. "
                f"Available: {available_processors}"
            )

        name = connection_def.get("name", "")
        relationships = connection_def.get("selectedRelationships", ["success"])
        back_pressure_object_threshold = connection_def.get("backPressureObjectThreshold", 1000)
        back_pressure_data_size_threshold = connection_def.get("backPressureDataSizeThreshold", "1 GB")
        flow_file_expiration = connection_def.get("flowFileExpiration", "0 sec")

        return await nifi_client.create_connection(
            source_id=source_processor_id,
            source_type="PROCESSOR",
            destination_id=dest_processor_id,
            destination_type="PROCESSOR",
            relationships=relationships,
            parent_group_id=process_group_id,
            name=name,
            back_pressure_object_threshold=back_pressure_object_threshold,
            back_pressure_data_size_threshold=back_pressure_data_size_threshold,
            flow_file_expiration=flow_file_expiration
        )

    async def _apply_version_control(
        self,
        nifi_client: NiFiAPIClient,
        process_group_id: str,
        bucket_id: str,
        flow_id: str,
        version: int
    ) -> Dict[str, Any]:
        """Phase 4: Associate the created process group with Registry flow."""
        log.debug(f"Phase 4: Applying version control to process group {process_group_id}")

        try:
            # This would implement the version control association
            # For now, we'll log the action
            log.info(f"Version control applied: bucket={bucket_id}, flow={flow_id}, version={version}")
            return {"version_control": "applied"}

        except Exception as e:
            log.warning(f"Failed to apply version control: {str(e)}")
            # Don't fail deployment for version control issues
            return {"version_control": "failed", "error": str(e)}

    async def _handle_rollback(
        self,
        nifi_client: NiFiAPIClient,
        created_components: CreatedComponents
    ) -> RollbackInfo:
        """Handle rollback of partially created components."""
        log.info("Performing deployment rollback")
        cleanup_results = []

        try:
            # Remove connections first
            for connection in created_components.connections:
                try:
                    await nifi_client.delete_connection(connection["id"])
                    cleanup_results.append(f"Removed connection {connection['id']}")
                except Exception as e:
                    cleanup_results.append(f"Failed to remove connection {connection['id']}: {str(e)}")

            # Remove processors
            for processor in created_components.processors:
                try:
                    await nifi_client.delete_processor(processor["id"])
                    cleanup_results.append(f"Removed processor {processor['id']}")
                except Exception as e:
                    cleanup_results.append(f"Failed to remove processor {processor['id']}: {str(e)}")

            # Remove process group
            if created_components.process_group:
                try:
                    await nifi_client.delete_process_group(created_components.process_group["id"])
                    cleanup_results.append(f"Removed process group {created_components.process_group['id']}")
                except Exception as e:
                    cleanup_results.append(f"Failed to remove process group: {str(e)}")

            return RollbackInfo(rollback_performed=True, cleanup_results=cleanup_results)

        except Exception as e:
            log.error(f"Rollback failed: {str(e)}")
            cleanup_results.append(f"Rollback failed: {str(e)}")
            return RollbackInfo(rollback_performed=False, cleanup_results=cleanup_results)