"""NiFi deployment service implementing the improved workflow."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

from ..clients.nifi_unified import NiFiUnifiedClient
from ..core.logging import get_logger, LoggerMixin

log = get_logger(__name__)


class NiFiDeploymentError(RuntimeError):
    """Raised when NiFi deployment operations fail."""


class NiFiDeploymentService(LoggerMixin):
    """Service for deploying and managing flows in NiFi."""

    def __init__(self, nifi_client: NiFiUnifiedClient):
        self.nifi = nifi_client
        self.logger.info("Initialized NiFi Deployment Service")

    async def deploy_and_validate_flow(
        self,
        flow_definition: Dict[str, Any],
        parameters: Dict[str, Any] = None,
        parent_group_id: str = "root",
        flow_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Deploy flow to NiFi with parameter context and validate.
        If successful, flow remains deployed. If errors occur, provide detailed feedback.
        """
        parameters = parameters or {}
        flow_name = flow_name or flow_definition.get("name", f"flow-{int(time.time())}")

        deployment_info: Dict[str, Any] = {}
        created_components: List[Dict[str, Any]] = []
        failures: List[Dict[str, Any]] = []

        parameter_context_id: Optional[str] = None
        process_group_id: Optional[str] = None
        should_cleanup = True

        try:
            self.logger.info("Starting deployment and validation for flow: %s", flow_name)

            # Step 1: Create parameter context if parameters provided
            if parameters:
                param_context_name = f"params-{flow_name}-{int(time.time())}"
                param_list = [
                    {
                        "parameter": {
                            "name": name,
                            "value": str(value),
                            "sensitive": False,
                        }
                    }
                    for name, value in parameters.items()
                ]

                param_context = await self.nifi.parameter_contexts.create_parameter_context(
                    name=param_context_name,
                    description=f"Parameters for {flow_name}",
                    parameters=param_list,
                )
                parameter_context_id = param_context.get("id")
                deployment_info["parameter_context_id"] = parameter_context_id
                self.logger.info("Created parameter context: %s", parameter_context_id)

            # Step 2: Create process group for flow
            process_group = await self.nifi.process_groups.create_process_group(
                parent_group_id=parent_group_id,
                name=flow_name,
                position={"x": 100.0, "y": 100.0},
            )
            process_group_id = process_group.get("id")
            deployment_info["process_group_id"] = process_group_id
            self.logger.info("Created process group: %s", process_group_id)

            # Step 3: Set parameter context on process group if we have one
            if parameter_context_id:
                await self.nifi.process_groups.set_parameter_context(
                    process_group_id=process_group_id,
                    parameter_context_id=parameter_context_id,
                    revision=process_group.get("revision", {}).get("version", 0),
                )
                self.logger.info("Applied parameter context to process group")

            # Step 4: Deploy processors
            processor_map, processor_failures = await self._deploy_processors(
                flow_definition.get("processors", []),
                process_group_id,
            )
            failures.extend(processor_failures)

            # Step 5: Deploy connections
            connection_map, connection_failures = await self._deploy_connections(
                flow_definition.get("connections", []),
                process_group_id,
                processor_map,
            )
            failures.extend(connection_failures)

            # Step 6: Final validation of all components
            validation_failures = await self._validate_components(processor_map)
            failures.extend(validation_failures)

            # Determine success
            success = len(failures) == 0

            if success:
                should_cleanup = False  # Keep successful deployment
                self.logger.info("Successfully deployed and validated flow: %s", flow_name)
            else:
                self.logger.warning("Flow deployment failed with %d errors", len(failures))

            summary = {
                "total_processors": len(flow_definition.get("processors", [])),
                "created_processors": len(processor_map),
                "failed_processors": len([f for f in failures if f["component_type"] == "processor"]),
                "total_connections": len(flow_definition.get("connections", [])),
                "created_connections": len(connection_map),
                "failed_connections": len([f for f in failures if f["component_type"] == "connection"]),
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
            failures.append(
                {
                    "component_type": "deployment",
                    "component_name": "flow",
                    "error_type": "nifi_error",
                    "message": str(exc),
                    "details": {},
                }
            )
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
                await self._cleanup_failed_deployment(process_group_id, parameter_context_id)

    async def _deploy_processors(
        self, processors: List[Dict[str, Any]], process_group_id: str
    ) -> Tuple[Dict[str, str], List[Dict[str, Any]]]:
        """Deploy processors and return ID mapping and failures."""
        processor_map: Dict[str, str] = {}
        processor_name_map: Dict[str, str] = {}
        failures: List[Dict[str, Any]] = []

        for processor_def in processors:
            try:
                processor = await self.nifi.processors.create_processor(
                    parent_group_id=process_group_id,
                    processor_type=processor_def.get("type", ""),
                    name=processor_def.get("name", "Unnamed Processor"),
                    position=processor_def.get("position"),
                    properties=processor_def.get("properties"),
                    scheduling={
                        "period": processor_def.get("schedulingPeriod"),
                        "strategy": processor_def.get("schedulingStrategy"),
                        "executionNode": processor_def.get("executionNode"),
                        "concurrentlySchedulableTaskCount": processor_def.get(
                            "concurrentlySchedulableTaskCount"
                        ),
                        "bulletinLevel": processor_def.get("bulletinLevel"),
                    },
                    auto_terminated_relationships=processor_def.get("autoTerminatedRelationships"),
                )

                new_id = processor.get("id") or processor.get("component", {}).get("id")
                original_id = processor_def.get("identifier")
                name = processor_def.get("name")

                if original_id and new_id:
                    processor_map[original_id] = new_id
                if name and new_id:
                    processor_name_map[name] = new_id

                self.logger.debug("Created processor: %s -> %s", name, new_id)

            except Exception as exc:
                failures.append(
                    {
                        "component_type": "processor",
                        "component_name": processor_def.get("name", "Unnamed Processor"),
                        "error_type": "creation",
                        "message": str(exc),
                        "details": {
                            "processor_type": processor_def.get("type"),
                            "properties": processor_def.get("properties", {}),
                        },
                    }
                )

        # Merge name map into processor map for connection resolution
        processor_map.update(processor_name_map)
        return processor_map, failures

    async def _deploy_connections(
        self,
        connections: List[Dict[str, Any]],
        process_group_id: str,
        processor_map: Dict[str, str],
    ) -> Tuple[Dict[str, str], List[Dict[str, Any]]]:
        """Deploy connections and return ID mapping and failures."""
        connection_map: Dict[str, str] = {}
        failures: List[Dict[str, Any]] = []

        for connection_def in connections:
            source_meta = connection_def.get("source", {})
            dest_meta = connection_def.get("destination", {})

            # Resolve source and destination IDs
            source_id = processor_map.get(source_meta.get("id")) or processor_map.get(
                source_meta.get("name")
            )
            dest_id = processor_map.get(dest_meta.get("id")) or processor_map.get(
                dest_meta.get("name")
            )

            if not source_id or not dest_id:
                failures.append(
                    {
                        "component_type": "connection",
                        "component_name": connection_def.get("name", "Unnamed Connection"),
                        "error_type": "resolution",
                        "message": "Unable to resolve connection endpoints",
                        "details": {
                            "source": source_meta,
                            "destination": dest_meta,
                            "available_processors": list(processor_map.keys()),
                        },
                    }
                )
                continue

            try:
                connection = await self.nifi.connections.create_connection(
                    parent_group_id=process_group_id,
                    source_id=source_id,
                    source_type=source_meta.get("type", "PROCESSOR"),
                    destination_id=dest_id,
                    destination_type=dest_meta.get("type", "PROCESSOR"),
                    name=connection_def.get("name", ""),
                    relationships=connection_def.get("selectedRelationships"),
                    back_pressure_object_threshold=connection_def.get("backPressureObjectThreshold"),
                    back_pressure_data_size_threshold=connection_def.get(
                        "backPressureDataSizeThreshold"
                    ),
                    flow_file_expiration=connection_def.get("flowFileExpiration"),
                )

                connection_id = connection.get("id")
                if connection_id:
                    connection_map[connection_def.get("identifier", connection_id)] = connection_id

                self.logger.debug(
                    "Created connection: %s -> %s", connection_def.get("name"), connection_id
                )

            except Exception as exc:
                failures.append(
                    {
                        "component_type": "connection",
                        "component_name": connection_def.get("name", "Unnamed Connection"),
                        "error_type": "creation",
                        "message": str(exc),
                        "details": {
                            "source": source_meta,
                            "destination": dest_meta,
                            "relationships": connection_def.get("selectedRelationships"),
                        },
                    }
                )

        return connection_map, failures

    async def _validate_components(self, processor_map: Dict[str, str]) -> List[Dict[str, Any]]:
        """Validate all deployed components."""
        failures: List[Dict[str, Any]] = []

        # Give connections time to be established
        import asyncio

        await asyncio.sleep(1)

        for original_id, processor_id in processor_map.items():
            try:
                processor = await self.nifi.processors.get_processor(processor_id)
                validation_status = processor.get("component", {}).get("validationStatus")

                if validation_status == "INVALID":
                    validation_errors = processor.get("component", {}).get("validationErrors", [])
                    failures.append(
                        {
                            "component_type": "processor",
                            "component_name": processor.get("component", {}).get("name", "Unknown"),
                            "error_type": "validation",
                            "message": "Processor validation failed",
                            "details": {
                                "validation_errors": validation_errors,
                                "validation_status": validation_status,
                            },
                        }
                    )

            except Exception as exc:
                failures.append(
                    {
                        "component_type": "processor",
                        "component_name": f"Processor {processor_id}",
                        "error_type": "validation",
                        "message": f"Failed to validate processor: {exc}",
                        "details": {},
                    }
                )

        return failures

    async def _cleanup_failed_deployment(
        self, process_group_id: Optional[str], parameter_context_id: Optional[str]
    ) -> None:
        """Clean up resources from a failed deployment."""
        if process_group_id:
            try:
                await self.nifi.process_groups.delete_process_group(process_group_id)
                self.logger.info("Cleaned up failed process group: %s", process_group_id)
            except Exception as exc:
                self.logger.warning("Failed to clean up process group %s: %s", process_group_id, exc)

        if parameter_context_id:
            try:
                await self.nifi.parameter_contexts.delete_parameter_context(parameter_context_id)
                self.logger.info("Cleaned up failed parameter context: %s", parameter_context_id)
            except Exception as exc:
                self.logger.warning(
                    "Failed to clean up parameter context %s: %s", parameter_context_id, exc
                )

    async def start_flow(self, process_group_id: str) -> Dict[str, Any]:
        """Start all processors in a flow."""
        result = await self.nifi.process_groups.start_process_group(process_group_id)
        self.logger.info("Started flow: %s", process_group_id)
        return {"status": "RUNNING", "process_group_id": process_group_id}

    async def stop_flow(self, process_group_id: str) -> Dict[str, Any]:
        """Stop all processors in a flow."""
        result = await self.nifi.process_groups.stop_process_group(process_group_id)
        self.logger.info("Stopped flow: %s", process_group_id)
        return {"status": "STOPPED", "process_group_id": process_group_id}

    async def delete_flow(self, process_group_id: str) -> Dict[str, Any]:
        """Delete a deployed flow."""
        # First stop the flow
        await self.stop_flow(process_group_id)

        # Then delete the process group
        await self.nifi.process_groups.delete_process_group(process_group_id)
        self.logger.info("Deleted flow: %s", process_group_id)
        return {"status": "DELETED", "process_group_id": process_group_id}

    async def get_flow_status(self, process_group_id: str) -> Dict[str, Any]:
        """Get status of a deployed flow."""
        flow_info = await self.nifi.process_groups.get_process_group_flow(process_group_id)

        status_info = {
            "process_group_id": process_group_id,
            "status": "UNKNOWN",
            "processor_count": 0,
            "running_count": 0,
            "stopped_count": 0,
            "invalid_count": 0,
        }

        # Count processor states
        if "processGroupFlow" in flow_info:
            processors = flow_info["processGroupFlow"].get("flow", {}).get("processors", [])
            status_info["processor_count"] = len(processors)

            for processor in processors:
                run_status = processor.get("status", {}).get("runStatus", "STOPPED")
                validation_status = processor.get("component", {}).get("validationStatus", "VALID")

                if validation_status == "INVALID":
                    status_info["invalid_count"] += 1
                elif run_status == "Running":
                    status_info["running_count"] += 1
                else:
                    status_info["stopped_count"] += 1

            # Determine overall status
            if status_info["invalid_count"] > 0:
                status_info["status"] = "INVALID"
            elif status_info["running_count"] > 0:
                status_info["status"] = "RUNNING"
            elif status_info["processor_count"] > 0:
                status_info["status"] = "STOPPED"
            else:
                status_info["status"] = "EMPTY"

        return status_info