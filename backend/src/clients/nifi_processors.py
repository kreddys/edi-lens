"""NiFi client for processor operations."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..core.logging import get_logger, LoggerMixin
from .nifi_base import NiFiBaseClient, NiFiClientError

log = get_logger(__name__)


class NiFiProcessorClient(LoggerMixin):
    """Client for NiFi processor operations."""

    def __init__(self, base_client: NiFiBaseClient):
        self.base = base_client
        self.logger.info("Initialized NiFi Processor client")

    async def create_processor(
        self,
        parent_group_id: str,
        processor_type: str,
        name: str,
        position: Optional[Dict[str, float]] = None,
        properties: Optional[Dict[str, str]] = None,
        scheduling: Optional[Dict[str, Any]] = None,
        auto_terminated_relationships: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Create a new processor."""
        if position is None:
            position = {"x": 100.0, "y": 100.0}

        component = {
            "type": processor_type,
            "name": name,
            "position": position,
        }

        if properties:
            component["config"] = {
                "properties": properties,
                "autoTerminatedRelationships": auto_terminated_relationships or [],
            }

        if scheduling:
            if "config" not in component:
                component["config"] = {}

            scheduling_config = {}
            if scheduling.get("period"):
                scheduling_config["schedulingPeriod"] = scheduling["period"]
            if scheduling.get("strategy"):
                scheduling_config["schedulingStrategy"] = scheduling["strategy"]
            if scheduling.get("executionNode"):
                scheduling_config["executionNode"] = scheduling["executionNode"]
            if scheduling.get("concurrentlySchedulableTaskCount"):
                scheduling_config["concurrentlySchedulableTaskCount"] = scheduling[
                    "concurrentlySchedulableTaskCount"
                ]
            if scheduling.get("bulletinLevel"):
                scheduling_config["bulletinLevel"] = scheduling["bulletinLevel"]

            component["config"].update(scheduling_config)

        payload = {
            "revision": {"version": 0},
            "component": component,
        }

        self.logger.debug(
            "Creating processor '%s' (%s) in group %s", name, processor_type, parent_group_id
        )
        result = await self.base.post(f"/process-groups/{parent_group_id}/processors", payload)

        processor_id = result.get("id")
        self.logger.info("Created processor '%s' with ID: %s", name, processor_id)
        return result

    async def get_processor(self, processor_id: str) -> Dict[str, Any]:
        """Get processor details."""
        self.logger.debug("Getting processor: %s", processor_id)
        return await self.base.get(f"/processors/{processor_id}")

    async def update_processor(
        self,
        processor_id: str,
        properties: Optional[Dict[str, str]] = None,
        revision: int = 0,
    ) -> Dict[str, Any]:
        """Update processor configuration."""
        component = {"id": processor_id}

        if properties:
            component["config"] = {"properties": properties}

        payload = {
            "revision": {"version": revision},
            "component": component,
        }

        self.logger.debug("Updating processor: %s", processor_id)
        result = await self.base.put(f"/processors/{processor_id}", payload)
        self.logger.info("Updated processor: %s", processor_id)
        return result

    async def delete_processor(self, processor_id: str, revision: int = 0) -> None:
        """Delete a processor."""
        self.logger.debug("Deleting processor: %s (revision: %d)", processor_id, revision)
        await self.base.delete(f"/processors/{processor_id}", params={"version": revision})
        self.logger.info("Deleted processor: %s", processor_id)

    async def start_processor(self, processor_id: str) -> Dict[str, Any]:
        """Start a processor."""
        processor_info = await self.get_processor(processor_id)
        revision = processor_info.get("revision", {}).get("version", 0)

        payload = {
            "revision": {"version": revision},
            "component": {
                "id": processor_id,
                "state": "RUNNING",
            },
        }

        self.logger.debug("Starting processor: %s", processor_id)
        result = await self.base.put(f"/processors/{processor_id}", payload)
        self.logger.info("Started processor: %s", processor_id)
        return result

    async def stop_processor(self, processor_id: str) -> Dict[str, Any]:
        """Stop a processor."""
        processor_info = await self.get_processor(processor_id)
        revision = processor_info.get("revision", {}).get("version", 0)

        payload = {
            "revision": {"version": revision},
            "component": {
                "id": processor_id,
                "state": "STOPPED",
            },
        }

        self.logger.debug("Stopping processor: %s", processor_id)
        result = await self.base.put(f"/processors/{processor_id}", payload)
        self.logger.info("Stopped processor: %s", processor_id)
        return result

    async def get_processor_types(self) -> List[Dict[str, Any]]:
        """Get available processor types."""
        self.logger.debug("Getting available processor types")
        result = await self.base.get("/flow/processor-types")
        return result.get("processorTypes", [])