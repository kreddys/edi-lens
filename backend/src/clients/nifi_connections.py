"""NiFi client for connection operations."""

from __future__ import annotations

import asyncio
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
        source_group_id: Optional[str] = None,
        destination_group_id: Optional[str] = None,
        name: str = "",
        relationships: Optional[List[str]] = None,
        back_pressure_object_threshold: Optional[int] = None,
        back_pressure_data_size_threshold: Optional[str] = None,
        flow_file_expiration: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new connection."""
        if relationships is None:
            relationships = []

        if source_group_id is None:
            source_group_id = parent_group_id
        if destination_group_id is None:
            destination_group_id = parent_group_id

        source = {
            "id": source_id,
            "type": source_type,
            "groupId": source_group_id,
        }

        destination = {
            "id": destination_id,
            "type": destination_type,
            "groupId": destination_group_id,
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

    async def drop_connection_flow_files(
        self,
        connection_id: str,
        *,
        poll_interval: float = 0.5,
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        """Drop all FlowFiles queued on a connection before deletion.

        NiFi requires connections to have empty queues before they can be
        removed. This helper issues a drop request and polls until the queue is
        drained or the request reports completion.
        """

        self.logger.debug("Dropping queued FlowFiles for connection: %s", connection_id)

        try:
            drop_request = await self.base.post(
                f"/flowfile-queues/{connection_id}/drop-requests",
                {"revision": {"version": 0}},
            )
        except NiFiClientError:
            self.logger.warning(
                "Failed to initiate drop request for connection %s", connection_id
            )
            raise

        drop_metadata = drop_request.get("dropRequest", drop_request)
        drop_request_id = drop_metadata.get("id")

        if not drop_request_id:
            # NiFi responded without a request identifier; return the raw response.
            self.logger.debug(
                "Drop request for connection %s returned without id", connection_id
            )
            return drop_request

        start_time = asyncio.get_running_loop().time()

        while True:
            status = await self.base.get(
                f"/flowfile-queues/{connection_id}/drop-requests/{drop_request_id}"
            )
            request_status = status.get("dropRequest", status)

            finished = request_status.get("finished")
            percent_complete = request_status.get("percentCompleted")
            current_count = request_status.get("currentCount")

            try:
                percent_value = float(str(percent_complete)) if percent_complete is not None else None
            except (TypeError, ValueError):
                percent_value = None

            try:
                count_value = int(str(current_count)) if current_count is not None else None
            except (TypeError, ValueError):
                count_value = None

            if finished or (percent_value is not None and percent_value >= 100.0):
                await self.base.delete(
                    f"/flowfile-queues/{connection_id}/drop-requests/{drop_request_id}"
                )
                self.logger.info(
                    "Dropped queued FlowFiles for connection %s", connection_id
                )
                return status

            if count_value is not None and count_value <= 0:
                await self.base.delete(
                    f"/flowfile-queues/{connection_id}/drop-requests/{drop_request_id}"
                )
                self.logger.info(
                    "No queued FlowFiles remained for connection %s", connection_id
                )
                return status

            if asyncio.get_running_loop().time() - start_time > timeout:
                raise NiFiClientError(
                    f"Timed out while dropping FlowFiles for connection {connection_id}"
                )

            await asyncio.sleep(poll_interval)
