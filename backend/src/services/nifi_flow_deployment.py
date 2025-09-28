"""NiFi flow deployment service - deploys and validates flows in NiFi."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

from ..clients.nifi_unified import NiFiUnifiedClient
from ..core.logging import get_logger, LoggerMixin

log = get_logger(__name__)


class NiFiFlowDeploymentError(RuntimeError):
    """Raised when NiFi flow deployment operations fail."""


class NiFiFlowDeployment(LoggerMixin):
    """Service for deploying and validating flows in NiFi."""

    def __init__(self, nifi_client: NiFiUnifiedClient):
        self.nifi = nifi_client
        self.logger.info("Initialized NiFi Flow Deployment service")

    async def deploy_flow(
        self,
        flow_definition: Dict[str, Any],
        flow_name: str,
        parameters: Dict[str, Any] = None,
        parent_group_id: str = "root",
    ) -> Dict[str, Any]:
        """
        Deploy a flow to NiFi with validation.
        Returns deployment result with process group ID and parameter context ID.
        """
        parameters = parameters or {}

        deployment_info: Dict[str, Any] = {}
        failures: List[Dict[str, Any]] = []
        parameter_context_id: Optional[str] = None
        process_group_id: Optional[str] = None
        should_cleanup = True

        # Debug logging for deployment tracking
        deployment_id = f"{flow_name}-{int(time.time())}"
        self.logger.info("=== DEPLOYMENT START [%s] ===", deployment_id)
        self.logger.debug("Flow definition: processors=%d, connections=%d", 
                         len(flow_definition.get("processors", [])), 
                         len(flow_definition.get("connections", [])))
        self.logger.debug("Parameters provided: %s (count=%d)", 
                         list(parameters.keys()) if parameters else "None", 
                         len(parameters))
        self.logger.debug("Parent group ID: %s", parent_group_id)

        try:
            self.logger.info("Starting flow deployment: %s", flow_name)

            # Step 1: Create parameter context if parameters provided
            if parameters:
                self.logger.debug("[%s] Creating parameter context with %d parameters", deployment_id, len(parameters))
                parameter_context_id = await self._create_parameter_context(
                    flow_name, parameters
                )
                deployment_info["parameter_context_id"] = parameter_context_id
                self.logger.debug("[%s] Parameter context created: %s", deployment_id, parameter_context_id)
            else:
                self.logger.debug("[%s] No parameters provided - skipping parameter context creation", deployment_id)

            # Step 2: Create process group for flow
            self.logger.debug("[%s] Creating process group for flow", deployment_id)
            process_group = await self._create_process_group(
                flow_name, parent_group_id
            )
            process_group_id = process_group.get("id")
            deployment_info["process_group_id"] = process_group_id
            self.logger.debug("[%s] Process group created: %s (name=%s)", 
                             deployment_id, process_group_id, process_group.get("component", {}).get("name"))

            # Step 3: Set parameter context on process group if we have one
            if parameter_context_id:
                self.logger.debug("[%s] Setting parameter context %s on process group %s", 
                                 deployment_id, parameter_context_id, process_group_id)
                await self._set_parameter_context(
                    process_group_id,
                    parameter_context_id,
                    revision=process_group.get("revision", {}).get("version"),
                    client_id=process_group.get("revision", {}).get("clientId"),
                )
                self.logger.debug("[%s] Parameter context applied successfully", deployment_id)
            else:
                self.logger.debug("[%s] No parameter context to apply", deployment_id)

            # Step 4: Deploy processors
            self.logger.debug("[%s] Deploying %d processors", deployment_id, len(flow_definition.get("processors", [])))
            processor_map, processor_failures = await self._deploy_processors(
                flow_definition.get("processors", []), process_group_id, deployment_id, parameters
            )
            failures.extend(processor_failures)
            self.logger.debug("[%s] Processor deployment complete: %d created, %d failed", 
                             deployment_id, len(processor_map), len(processor_failures))

            # Step 5: Deploy connections
            self.logger.debug("[%s] Deploying %d connections", deployment_id, len(flow_definition.get("connections", [])))
            connection_failures = await self._deploy_connections(
                flow_definition.get("connections", []), process_group_id, processor_map, deployment_id
            )
            failures.extend(connection_failures)
            self.logger.debug("[%s] Connection deployment complete: %d failed", deployment_id, len(connection_failures))

            # Step 6: Validate all components
            self.logger.debug("[%s] Starting component validation", deployment_id)
            validation_failures = await self._validate_components(processor_map, deployment_id)
            failures.extend(validation_failures)
            self.logger.debug("[%s] Validation complete: %d validation failures", deployment_id, len(validation_failures))

            # Determine success
            success = len(failures) == 0

            if success:
                should_cleanup = False  # Keep successful deployment
                self.logger.info("[%s] ✅ DEPLOYMENT SUCCESS: %s", deployment_id, flow_name)
                self.logger.debug("[%s] Final process group: %s, parameter context: %s", 
                                 deployment_id, process_group_id, parameter_context_id)
            else:
                self.logger.warning("[%s] ❌ DEPLOYMENT FAILED: %d total failures", deployment_id, len(failures))
                for i, failure in enumerate(failures):
                    self.logger.debug("[%s] Failure %d: %s/%s - %s", 
                                     deployment_id, i+1, failure.get("component_type"), 
                                     failure.get("component_name"), failure.get("message"))

            # Calculate actual success counts
            total_processors = len(flow_definition.get("processors", []))
            failed_processors = len([f for f in failures if f["component_type"] == "processor"])
            created_processors = total_processors - failed_processors
            
            total_connections = len(flow_definition.get("connections", []))
            failed_connections = len([f for f in failures if f["component_type"] == "connection"])
            created_connections = total_connections - failed_connections

            summary = {
                "total_processors": total_processors,
                "created_processors": max(0, created_processors),
                "failed_processors": failed_processors,
                "total_connections": total_connections,
                "created_connections": max(0, created_connections),
                "failed_connections": failed_connections,
            }

            return {
                "success": success,
                "summary": summary,
                "failures": failures,
                "process_group_id": process_group_id,
                "parameter_context_id": parameter_context_id,
                "deployment_info": deployment_info,
            }

        except Exception as exc:
            failures.append({
                "component_type": "deployment",
                "component_name": "flow",
                "error_type": "nifi_error",
                "message": str(exc),
                "details": {},
            })
            self.logger.error("Deployment failed with exception: %s", exc)
            return {
                "success": False,
                "summary": {},
                "failures": failures,
                "process_group_id": process_group_id,
                "parameter_context_id": parameter_context_id,
                "deployment_info": deployment_info,
            }

        finally:
            if should_cleanup and process_group_id:
                self.logger.info("[%s] 🧹 CLEANUP: Removing failed deployment resources", deployment_id)
                await self.cleanup_failed_deployment(process_group_id, parameter_context_id, deployment_id)
            
            self.logger.info("=== DEPLOYMENT END [%s] ===", deployment_id)

    async def cleanup_failed_deployment(
        self, process_group_id: Optional[str], parameter_context_id: Optional[str], deployment_id: str = "unknown"
    ) -> None:
        """Clean up resources from a failed deployment."""
        if process_group_id:
            try:
                self.logger.debug("[%s] Deleting failed process group: %s", deployment_id, process_group_id)
                await self.nifi.process_groups.delete_process_group(process_group_id)
                self.logger.info("[%s] ✅ Cleaned up failed process group: %s", deployment_id, process_group_id)
            except Exception as exc:
                self.logger.warning("[%s] ❌ Failed to clean up process group %s: %s", deployment_id, process_group_id, exc)

        if parameter_context_id:
            try:
                self.logger.debug("[%s] Deleting failed parameter context: %s", deployment_id, parameter_context_id)
                await self.nifi.parameter_contexts.delete_parameter_context(parameter_context_id)
                self.logger.info("[%s] ✅ Cleaned up failed parameter context: %s", deployment_id, parameter_context_id)
            except Exception as exc:
                self.logger.warning(
                    "[%s] ❌ Failed to clean up parameter context %s: %s", deployment_id, parameter_context_id, exc
                )

    async def _create_parameter_context(
        self, flow_name: str, parameters: Dict[str, Any]
    ) -> str:
        """Create parameter context for the flow with proper parameter structure."""
        param_context_name = f"params-{flow_name}-{int(time.time())}"
        param_list = []
        
        for name, value in parameters.items():
            # Handle both simple values and parameter objects with metadata
            if isinstance(value, dict):
                # Parameter object with metadata
                param_list.append({
                    "parameter": {
                        "name": name,
                        "value": str(value.get("value", value.get("default", ""))),
                        "description": value.get("description", f"Parameter {name}"),
                        "sensitive": value.get("sensitive", False),
                    }
                })
            else:
                # Simple value
                param_list.append({
                    "parameter": {
                        "name": name,
                        "value": str(value),
                        "description": f"Parameter {name}",
                        "sensitive": False,
                    }
                })

        param_context = await self.nifi.parameter_contexts.create_parameter_context(
            name=param_context_name,
            description=f"Parameters for {flow_name}",
            parameters=param_list,
        )
        parameter_context_id = param_context.get("id")
        self.logger.info("Created parameter context: %s with %d parameters", parameter_context_id, len(param_list))
        return parameter_context_id

    async def _create_process_group(self, flow_name: str, parent_group_id: str) -> Dict[str, Any]:
        """Create process group for the flow."""
        # Make process group name unique to avoid conflicts from previous deployments
        unique_flow_name = f"{flow_name}-{int(time.time())}"
        process_group = await self.nifi.process_groups.create_process_group(
            parent_group_id=parent_group_id,
            name=unique_flow_name,
            position={"x": 100.0, "y": 100.0},
        )
        process_group_id = process_group.get("id")
        self.logger.info("Created process group: %s (name: %s)", process_group_id, unique_flow_name)
        return process_group

    async def _set_parameter_context(
        self,
        process_group_id: str,
        parameter_context_id: str,
        revision: Optional[int] = None,
        client_id: Optional[str] = None,
    ) -> None:
        """Set parameter context on process group."""
        await self.nifi.process_groups.set_parameter_context(
            process_group_id=process_group_id,
            parameter_context_id=parameter_context_id,
            revision=revision,
            client_id=client_id,
        )
        self.logger.info("Applied parameter context to process group")

    async def _deploy_processors(
        self, processors: List[Dict[str, Any]], process_group_id: str, deployment_id: str = "unknown", parameters: Dict[str, Any] = None
    ) -> Tuple[Dict[str, str], List[Dict[str, Any]]]:
        """Deploy processors with parameter substitution and return ID mapping and failures."""
        processor_map: Dict[str, str] = {}
        processor_name_map: Dict[str, str] = {}
        failures: List[Dict[str, Any]] = []
        parameters = parameters or {}

        for processor_def in processors:
            processor_name = processor_def.get("name", "Unnamed Processor")
            self.logger.debug("[%s] Creating processor: %s", deployment_id, processor_name)
            
            try:
                component_def = processor_def.get("component") or processor_def
                config_def = component_def.get("config", {})

                processor_type = processor_def.get("type") or component_def.get("type", "")
                processor_name = processor_def.get("name") or component_def.get("name", "Unnamed Processor")
                position = processor_def.get("position") or component_def.get("position")
                properties = processor_def.get("properties") or config_def.get("properties")
                
                # Keep parameter references intact - they will be resolved by NiFi parameter context
                # No parameter substitution needed when using proper parameter contexts
                if properties and parameters:
                    self.logger.debug("[%s] Keeping parameter references intact for %s (will be resolved by parameter context)", 
                                     deployment_id, processor_name)
                
                self.logger.debug("[%s] Processor %s: type=%s, properties=%s", 
                                 deployment_id, processor_name, processor_type, 
                                 list(properties.keys()) if properties else "None")
                auto_terminated = (
                    processor_def.get("autoTerminatedRelationships")
                    or config_def.get("autoTerminatedRelationships")
                )

                scheduling_period = (
                    processor_def.get("schedulingPeriod")
                    or config_def.get("schedulingPeriod")
                )
                scheduling_strategy = (
                    processor_def.get("schedulingStrategy")
                    or config_def.get("schedulingStrategy")
                )
                execution_node = (
                    processor_def.get("executionNode")
                    or config_def.get("executionNode")
                )
                concurrent_tasks = (
                    processor_def.get("concurrentlySchedulableTaskCount")
                    or config_def.get("concurrentlySchedulableTaskCount")
                )
                bulletin_level = (
                    processor_def.get("bulletinLevel") or config_def.get("bulletinLevel")
                )

                processor = await self.nifi.processors.create_processor(
                    parent_group_id=process_group_id,
                    processor_type=processor_type,
                    name=processor_name,
                    position=position,
                    properties=properties,
                    scheduling={
                        "period": scheduling_period,
                        "strategy": scheduling_strategy,
                        "executionNode": execution_node,
                        "concurrentlySchedulableTaskCount": concurrent_tasks,
                        "bulletinLevel": bulletin_level,
                    },
                    auto_terminated_relationships=auto_terminated,
                )

                new_id = processor.get("id") or processor.get("component", {}).get("id")
                original_id = processor_def.get("identifier") or component_def.get("id")
                name = processor_name

                if original_id and new_id:
                    processor_map[original_id] = new_id
                if name and new_id:
                    processor_name_map[name] = new_id

                self.logger.debug("[%s] ✅ Created processor: %s -> %s (id=%s)", 
                                 deployment_id, name, new_id, original_id)

            except Exception as exc:
                self.logger.error("[%s] ❌ Failed to create processor %s: %s", 
                                 deployment_id, processor_name, exc)
                failures.append({
                    "component_type": "processor",
                    "component_name": processor_def.get("name", "Unnamed Processor"),
                    "error_type": "creation",
                    "message": str(exc),
                    "details": {
                        "processor_type": processor_def.get("type"),
                        "properties": processor_def.get("properties", {}),
                    },
                })

        # Merge name map into processor map for connection resolution (avoid duplicates)
        for name, proc_id in processor_name_map.items():
            if name not in processor_map:  # Only add if not already present by ID
                processor_map[name] = proc_id
        
        self.logger.debug("Final processor map: %s", processor_map)
        return processor_map, failures

    async def _deploy_connections(
        self,
        connections: List[Dict[str, Any]],
        process_group_id: str,
        processor_map: Dict[str, str],
        deployment_id: str = "unknown",
    ) -> List[Dict[str, Any]]:
        """Deploy connections and return failures."""
        failures: List[Dict[str, Any]] = []

        for connection_def in connections:
            component_def = connection_def.get("component") or connection_def
            source_meta = component_def.get("source", connection_def.get("source", {}))
            dest_meta = component_def.get("destination", connection_def.get("destination", {}))

            # Resolve source and destination IDs
            source_id = processor_map.get(source_meta.get("id")) or processor_map.get(
                source_meta.get("name")
            )
            dest_id = processor_map.get(dest_meta.get("id")) or processor_map.get(
                dest_meta.get("name")
            )

            if not source_id or not dest_id:
                failures.append({
                    "component_type": "connection",
                    "component_name": connection_def.get("name", "Unnamed Connection"),
                    "error_type": "resolution",
                    "message": "Unable to resolve connection endpoints",
                    "details": {
                        "source": source_meta,
                        "destination": dest_meta,
                        "available_processors": list(processor_map.keys()),
                    },
                })
                continue

            try:
                await self.nifi.connections.create_connection(
                    parent_group_id=process_group_id,
                    source_id=source_id,
                    source_type=source_meta.get("type", "PROCESSOR"),
                    destination_id=dest_id,
                    destination_type=dest_meta.get("type", "PROCESSOR"),
                    name=connection_def.get("name")
                    or component_def.get("name", ""),
                    relationships=connection_def.get("selectedRelationships")
                    or component_def.get("selectedRelationships"),
                    back_pressure_object_threshold=connection_def.get("backPressureObjectThreshold")
                    or component_def.get("backPressureObjectThreshold"),
                    back_pressure_data_size_threshold=connection_def.get("backPressureDataSizeThreshold")
                    or component_def.get("backPressureDataSizeThreshold"),
                    flow_file_expiration=connection_def.get("flowFileExpiration")
                    or component_def.get("flowFileExpiration"),
                )

                self.logger.debug("Created connection: %s", connection_def.get("name"))

            except Exception as exc:
                failures.append({
                    "component_type": "connection",
                    "component_name": connection_def.get("name", "Unnamed Connection"),
                    "error_type": "creation",
                    "message": str(exc),
                    "details": {
                        "source": source_meta,
                        "destination": dest_meta,
                        "relationships": connection_def.get("selectedRelationships"),
                    },
                })

        return failures

    async def _validate_components(self, processor_map: Dict[str, str], deployment_id: str = "unknown") -> List[Dict[str, Any]]:
        """Validate all deployed components."""
        failures: List[Dict[str, Any]] = []

        # Give connections time to be established
        import asyncio
        await asyncio.sleep(1)

        # Get unique processor IDs to avoid duplicate validation
        unique_processor_ids = set(processor_map.values())
        self.logger.debug("[%s] Validating %d unique processors", deployment_id, len(unique_processor_ids))
        
        for processor_id in unique_processor_ids:
            try:
                processor = await self.nifi.processors.get_processor(processor_id)
                processor_name = processor.get("component", {}).get("name", "Unknown")
                validation_status = processor.get("component", {}).get("validationStatus")
                
                self.logger.debug("[%s] Processor %s (%s): validation_status=%s", 
                                 deployment_id, processor_name, processor_id, validation_status)

                if validation_status == "INVALID":
                    validation_errors = processor.get("component", {}).get("validationErrors", [])
                    self.logger.warning("[%s] ❌ Processor %s validation failed: %s", 
                                      deployment_id, processor_name, validation_errors)
                    failures.append({
                        "component_type": "processor",
                        "component_name": processor_name,
                        "error_type": "validation",
                        "message": "Processor validation failed",
                        "details": {
                            "validation_errors": validation_errors,
                            "validation_status": validation_status,
                        },
                    })
                else:
                    self.logger.debug("[%s] ✅ Processor %s validation passed", deployment_id, processor_name)

            except Exception as exc:
                self.logger.error("[%s] ❌ Failed to validate processor %s: %s", deployment_id, processor_id, exc)
                failures.append({
                    "component_type": "processor",
                    "component_name": f"Processor {processor_id}",
                    "error_type": "validation",
                    "message": f"Failed to validate processor: {exc}",
                    "details": {},
                })

        return failures