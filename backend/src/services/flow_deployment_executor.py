"""Shared component-level deployment executor for NiFi flows."""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List, Optional

from ..clients.nifi_client import NiFiClient, NiFiClientError
from ..core.logging import get_logger

log = get_logger(__name__)


class FlowDeploymentExecutor:
    """Builds versioned flow contents inside NiFi, collecting detailed failures."""

    def __init__(self, nifi_client: NiFiClient):
        self.nifi_client = nifi_client

    async def execute(
        self,
        flow_contents: Dict[str, Any],
        *,
        parameters: Optional[Dict[str, Any]] = None,
        parent_group_id: str = "root",
        parameter_context_name: Optional[str] = None,
        cleanup_on_success: bool = False,
        create_connections: bool = True,
    ) -> Dict[str, Any]:
        """Attempt component-level deployment, optionally cleaning up on success."""

        deployment_info: Dict[str, Any] = {}
        created_processors: List[Dict[str, Any]] = []
        created_connections: List[Dict[str, Any]] = []
        failures: List[Dict[str, Any]] = []

        parameter_context_id: Optional[str] = None
        parameter_context_revision: Optional[int] = None
        parameter_context_created = False
        process_group_id: Optional[str] = None
        process_group_revision: Optional[int] = None

        should_cleanup = True

        try:
            if parameters:
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

                context_name = parameter_context_name or f"validator-{int(time.time())}"
                param_context = await self.nifi_client.create_parameter_context(
                    name=context_name,
                    description="Flow validation context",
                    parameters=param_list,
                )
                parameter_context_id = param_context.get("id")
                parameter_context_revision = param_context.get("revision", {}).get("version", 0)
                parameter_context_created = True
                deployment_info["parameter_context_id"] = parameter_context_id
                log.debug("Validator parameter context %s created", parameter_context_id)

            process_group = await self.nifi_client.create_process_group(
                parent_group_id=parent_group_id,
                name=f"validator-{int(time.time())}",
                position={"x": 100.0, "y": 100.0},
            )
            process_group_id = process_group.get("id")
            process_group_revision = process_group.get("revision", {}).get("version", 0)
            deployment_info["process_group_id"] = process_group_id
            log.debug("Validator process group %s created", process_group_id)

            if parameter_context_id:
                updated_pg = await self.nifi_client.set_parameter_context_for_process_group(
                    process_group_id=process_group_id,
                    parameter_context_id=parameter_context_id,
                    revision=process_group_revision or 0,
                )
                process_group_revision = updated_pg.get("revision", {}).get("version", process_group_revision)

            processor_map: Dict[str, str] = {}
            processor_name_map: Dict[str, str] = {}
            pending_revalidation: List[Dict[str, Any]] = []

            for processor_def in flow_contents.get("processors", []):
                try:
                    processor = await self.nifi_client.create_processor(
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

                    created_processors.append({"definition": processor_def, "entity": processor})
                    new_id = processor.get("id") or processor.get("component", {}).get("id")
                    original_id = processor_def.get("identifier")
                    name = processor_def.get("name")

                    if original_id and new_id:
                        processor_map[original_id] = new_id
                    if name and new_id:
                        processor_name_map[name] = new_id

                    validation_status = processor.get("component", {}).get("validationStatus")
                    if validation_status == "INVALID":
                        pending_revalidation.append({"definition": processor_def, "entity": processor})

                except NiFiClientError as exc:
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

            for connection_def in flow_contents.get("connections", []):
                source_meta = connection_def.get("source", {})
                dest_meta = connection_def.get("destination", {})
                source_id = processor_map.get(source_meta.get("id"))
                dest_id = processor_map.get(dest_meta.get("id"))

                if not source_id and source_meta.get("name"):
                    source_id = processor_name_map.get(source_meta.get("name"))
                if not dest_id and dest_meta.get("name"):
                    dest_id = processor_name_map.get(dest_meta.get("name"))

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
                            },
                        }
                    )
                    continue

                if not create_connections:
                    created_connections.append({"definition": connection_def, "entity": {"id": "skipped"}})
                    continue

                try:
                    connection = await self.nifi_client.create_connection(
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
                    created_connections.append({"definition": connection_def, "entity": connection})
                except NiFiClientError as exc:
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

            if create_connections and pending_revalidation and process_group_id:
                await asyncio.sleep(1)
                for item in pending_revalidation:
                    entity = item.get("entity", {})
                    proc_id = entity.get("id") or entity.get("component", {}).get("id")
                    if not proc_id:
                        continue
                    try:
                        current = await self.nifi_client.get_processor(proc_id)
                        status = current.get("component", {}).get("validationStatus")
                        if status == "INVALID":
                            failures.append(
                                {
                                    "component_type": "processor",
                                    "component_name": item["definition"].get("name", "Unnamed Processor"),
                                    "error_type": "validation",
                                    "message": "Processor remains invalid after connections",
                                    "details": {
                                        "validation_errors": current.get("component", {}).get("validationErrors", []),
                                    },
                                }
                            )
                    except NiFiClientError as exc:
                        failures.append(
                            {
                                "component_type": "processor",
                                "component_name": item["definition"].get("name", "Unnamed Processor"),
                                "error_type": "validation",
                                "message": str(exc),
                                "details": {},
                            }
                        )

            summary = {
                "total_processors": len(flow_contents.get("processors", [])),
                "created_processors": len(created_processors),
                "failed_processors": len([f for f in failures if f["component_type"] == "processor"]),
                "total_connections": len(flow_contents.get("connections", [])),
                "created_connections": len(created_connections),
                "failed_connections": len([f for f in failures if f["component_type"] == "connection"]),
            }

            success = not failures

            if success and not cleanup_on_success:
                should_cleanup = False

            return {
                "success": success,
                "summary": summary,
                "failures": failures,
                "process_group_id": process_group_id,
                "parameter_context_id": parameter_context_id,
            }

        except NiFiClientError as exc:
            failures.append(
                {
                    "component_type": "deployment",
                    "component_name": "flow",
                    "error_type": "nifi_error",
                    "message": str(exc),
                    "details": {},
                }
            )
            return {
                "success": False,
                "summary": {},
                "failures": failures,
                "process_group_id": process_group_id,
                "parameter_context_id": parameter_context_id,
            }
        finally:
            if should_cleanup:
                await self._rollback(
                    process_group_id,
                    process_group_revision,
                    created_processors,
                    created_connections,
                    parameter_context_id,
                    parameter_context_revision,
                    parameter_context_created,
                )

    async def _rollback(
        self,
        process_group_id: Optional[str],
        process_group_revision: Optional[int],
        processors: List[Dict[str, Any]],
        connections: List[Dict[str, Any]],
        parameter_context_id: Optional[str],
        parameter_context_revision: Optional[int],
        parameter_context_created: bool,
    ) -> None:
        if not process_group_id:
            return

        for connection in reversed(connections):
            entity = connection.get("entity", {})
            connection_id = entity.get("id") or entity.get("component", {}).get("id")
            if not connection_id or connection_id == "skipped":
                continue
            revision = entity.get("revision", {}).get("version", 0)
            try:
                await self.nifi_client.delete_connection(connection_id, revision=revision)
            except NiFiClientError:
                log.debug("Failed to delete validator connection %s", connection_id)

        for processor in reversed(processors):
            entity = processor.get("entity", {})
            processor_id = entity.get("id") or entity.get("component", {}).get("id")
            revision = entity.get("revision", {}).get("version", 0)
            if processor_id:
                try:
                    await self.nifi_client.delete_processor(processor_id, revision=revision)
                except NiFiClientError:
                    log.debug("Failed to delete validator processor %s", processor_id)

        revision = process_group_revision
        if revision is None and process_group_id:
            try:
                current_pg = await self.nifi_client.get_process_group(process_group_id)
                revision = current_pg.get("revision", {}).get("version", 0)
            except NiFiClientError:
                revision = 0

        if process_group_id is not None and revision is not None:
            try:
                await self.nifi_client.delete_process_group(process_group_id, revision=revision)
            except NiFiClientError:
                log.debug("Failed to delete validator process group %s", process_group_id)

        if parameter_context_created and parameter_context_id is not None and parameter_context_revision is not None:
            try:
                await self.nifi_client.delete_parameter_context(
                    parameter_context_id,
                    revision=parameter_context_revision,
                )
            except NiFiClientError:
                log.debug("Failed to delete validator parameter context %s", parameter_context_id)
