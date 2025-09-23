"""NiFi client for connection operations."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..core.logging import get_logger, LoggerMixin
from .nifi_base import NiFiBaseClient, NiFiClientError

log = get_logger(__name__)


class NiFiConnectionClient(LoggerMixin):
    """Client for NiFi connection operations."""

    def __init__(self, base_client: NiFiBaseClient):
        self.base = base_client
        self.logger.info("Initialized NiFi Connection client")

    async def create_connection(
        self,
        parent_group_id: str,
        source_id: str,
        destination_id: str,
        source_type: str = "PROCESSOR",
        destination_type: str = "PROCESSOR",
        name: str = "",
        relationships: Optional[List[str]] = None,
        back_pressure_object_threshold: Optional[int] = None,
        back_pressure_data_size_threshold: Optional[str] = None,
        flow_file_expiration: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new connection."""
        if relationships is None:
            relationships = []

        source = {
            "id": source_id,
            "type": source_type,
        }

        destination = {
            "id": destination_id,
            "type": destination_type,
        }

        component = {
            "name": name,
            "source": source,
            "destination": destination,
            "selectedRelationships": relationships,
        }

        # Set back pressure and expiration settings if provided
        if (
            back_pressure_object_threshold is not None
            or back_pressure_data_size_threshold is not None
            or flow_file_expiration is not None
        ):
            component["backPressureObjectThreshold"] = back_pressure_object_threshold or 10000
            component["backPressureDataSizeThreshold"] = back_pressure_data_size_threshold or "1 GB"
            component["flowFileExpiration"] = flow_file_expiration or "0 sec"

        payload = {
            "revision": {"version": 0},
            "component": component,
        }

        self.logger.debug(
            "Creating connection from %s to %s in group %s",
            source_id,
            destination_id,
            parent_group_id,
        )
        result = await self.base.post(f"/process-groups/{parent_group_id}/connections", payload)

        connection_id = result.get("id")
        self.logger.info("Created connection with ID: %s", connection_id)
        return result

    async def get_connection(self, connection_id: str) -> Dict[str, Any]:
        """Get connection details."""
        self.logger.debug("Getting connection: %s", connection_id)
        return await self.base.get(f"/connections/{connection_id}")

    async def update_connection(
        self,
        connection_id: str,
        name: Optional[str] = None,
        relationships: Optional[List[str]] = None,
        back_pressure_object_threshold: Optional[int] = None,
        back_pressure_data_size_threshold: Optional[str] = None,
        flow_file_expiration: Optional[str] = None,
        revision: int = 0,
    ) -> Dict[str, Any]:
        """Update connection configuration."""
        component = {"id": connection_id}

        if name is not None:
            component["name"] = name
        if relationships is not None:
            component["selectedRelationships"] = relationships
        if back_pressure_object_threshold is not None:
            component["backPressureObjectThreshold"] = back_pressure_object_threshold
        if back_pressure_data_size_threshold is not None:
            component["backPressureDataSizeThreshold"] = back_pressure_data_size_threshold
        if flow_file_expiration is not None:
            component["flowFileExpiration"] = flow_file_expiration

        payload = {
            "revision": {"version": revision},
            "component": component,
        }

        self.logger.debug("Updating connection: %s", connection_id)
        result = await self.base.put(f"/connections/{connection_id}", payload)
        self.logger.info("Updated connection: %s", connection_id)
        return result

    async def delete_connection(self, connection_id: str, revision: int = 0) -> None:
        """Delete a connection."""
        self.logger.debug("Deleting connection: %s (revision: %d)", connection_id, revision)
        await self.base.delete(f"/connections/{connection_id}", params={"version": revision})
        self.logger.info("Deleted connection: %s", connection_id)

    async def get_connection_status(self, connection_id: str) -> Dict[str, Any]:
        """Get connection status including queue information."""
        self.logger.debug("Getting connection status: %s", connection_id)
        return await self.base.get(f"/flow/connections/{connection_id}/status")