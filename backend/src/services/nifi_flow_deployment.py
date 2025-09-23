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

        try:
            self.logger.info("Starting flow deployment: %s", flow_name)

            # Step 1: Create parameter context if parameters provided
            if parameters:
                parameter_context_id = await self._create_parameter_context(
                    flow_name, parameters
                )
                deployment_info["parameter_context_id"] = parameter_context_id

            # Step 2: Create process group for flow
            process_group_id = await self._create_process_group(
                flow_name, parent_group_id
            )
            deployment_info["process_group_id"] = process_group_id

            # Step 3: Set parameter context on process group if we have one
            if parameter_context_id:
                await self._set_parameter_context(process_group_id, parameter_context_id)

            # Step 4: Deploy processors
            processor_map, processor_failures = await self._deploy_processors(
                flow_definition.get("processors", []), process_group_id
            )
            failures.extend(processor_failures)

            # Step 5: Deploy connections
            connection_failures = await self._deploy_connections(
                flow_definition.get("connections", []), process_group_id, processor_map
            )
            failures.extend(connection_failures)

            # Step 6: Validate all components
            validation_failures = await self._validate_components(processor_map)
            failures.extend(validation_failures)

            # Determine success
            success = len(failures) == 0

            if success:
                should_cleanup = False  # Keep successful deployment
                self.logger.info("Successfully deployed flow: %s", flow_name)
            else:
                self.logger.warning("Flow deployment failed with %d errors", len(failures))

            summary = {
                "total_processors": len(flow_definition.get("processors", [])),
                "created_processors": len(processor_map),
                "failed_processors": len([f for f in failures if f["component_type"] == "processor"]),
                "total_connections": len(flow_definition.get("connections", [])),
                "created_connections": len([f for f in failures if f["component_type"] == "connection"]),
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
                await self.cleanup_failed_deployment(process_group_id, parameter_context_id)

    async def cleanup_failed_deployment(
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

    async def _create_parameter_context(
        self, flow_name: str, parameters: Dict[str, Any]
    ) -> str:
        """Create parameter context for the flow."""
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
        self.logger.info("Created parameter context: %s", parameter_context_id)
        return parameter_context_id

    async def _create_process_group(self, flow_name: str, parent_group_id: str) -> str:
        """Create process group for the flow."""
        process_group = await self.nifi.process_groups.create_process_group(
            parent_group_id=parent_group_id,
            name=flow_name,
            position={"x": 100.0, "y": 100.0},
        )
        process_group_id = process_group.get("id")
        self.logger.info("Created process group: %s", process_group_id)
        return process_group_id

    async def _set_parameter_context(
        self, process_group_id: str, parameter_context_id: str
    ) -> None:
        """Set parameter context on process group."""
        await self.nifi.process_groups.set_parameter_context(
            process_group_id=process_group_id,
            parameter_context_id=parameter_context_id,
            revision=0,
        )
        self.logger.info("Applied parameter context to process group")

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
                        "concurrentlySchedulableTaskCount": processor_def.get("concurrentlySchedulableTaskCount"),
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

        # Merge name map into processor map for connection resolution
        processor_map.update(processor_name_map)
        return processor_map, failures

    async def _deploy_connections(
        self,
        connections: List[Dict[str, Any]],
        process_group_id: str,
        processor_map: Dict[str, str],
    ) -> List[Dict[str, Any]]:
        """Deploy connections and return failures."""
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
                    name=connection_def.get("name", ""),
                    relationships=connection_def.get("selectedRelationships"),
                    back_pressure_object_threshold=connection_def.get("backPressureObjectThreshold"),
                    back_pressure_data_size_threshold=connection_def.get("backPressureDataSizeThreshold"),
                    flow_file_expiration=connection_def.get("flowFileExpiration"),
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
                    failures.append({
                        "component_type": "processor",
                        "component_name": processor.get("component", {}).get("name", "Unknown"),
                        "error_type": "validation",
                        "message": "Processor validation failed",
                        "details": {
                            "validation_errors": validation_errors,
                            "validation_status": validation_status,
                        },
                    })

            except Exception as exc:
                failures.append({
                    "component_type": "processor",
                    "component_name": f"Processor {processor_id}",
                    "error_type": "validation",
                    "message": f"Failed to validate processor: {exc}",
                    "details": {},
                })

        return failures