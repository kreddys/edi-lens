"""NiFi client for process group operations."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..core.logging import get_logger, LoggerMixin
from .nifi_base import NiFiBaseClient, NiFiClientError

log = get_logger(__name__)


class NiFiProcessGroupClient(LoggerMixin):
    """Client for NiFi process group operations."""

    def __init__(self, base_client: NiFiBaseClient):
        self.base = base_client
        self.logger.info("Initialized NiFi Process Group client")

    async def create_process_group(
        self,
        parent_group_id: str,
        name: str,
        position: Dict[str, float] = None,
    ) -> Dict[str, Any]:
        """Create a new process group."""
        if position is None:
            position = {"x": 100.0, "y": 100.0}

        payload = {
            "revision": {"version": 0},
            "component": {
                "name": name,
                "position": position,
            },
        }

        self.logger.debug("Creating process group '%s' in parent '%s'", name, parent_group_id)
        result = await self.base.post(f"/process-groups/{parent_group_id}/process-groups", payload)

        process_group_id = result.get("id")
        self.logger.info("Created process group '%s' with ID: %s", name, process_group_id)
        return result

    async def get_process_group(self, process_group_id: str) -> Dict[str, Any]:
        """Get process group details."""
        self.logger.debug("Getting process group: %s", process_group_id)
        return await self.base.get(f"/process-groups/{process_group_id}")

    async def get_process_group_flow(self, process_group_id: str) -> Dict[str, Any]:
        """Get process group flow contents."""
        self.logger.debug("Getting process group flow: %s", process_group_id)
        return await self.base.get(f"/flow/process-groups/{process_group_id}")

    async def delete_process_group(self, process_group_id: str, revision: int = 0) -> None:
        """Delete a process group."""
        self.logger.debug("Deleting process group: %s (revision: %d)", process_group_id, revision)
        await self.base.delete(f"/process-groups/{process_group_id}", params={"version": revision})
        self.logger.info("Deleted process group: %s", process_group_id)

    async def start_process_group(self, process_group_id: str) -> Dict[str, Any]:
        """Start all processors in a process group."""
        # Get current process group details for revision
        pg_info = await self.get_process_group(process_group_id)
        revision = pg_info.get("revision", {}).get("version", 0)

        payload = {
            "id": process_group_id,
            "state": "RUNNING",
            "revision": {"version": revision},
        }

        self.logger.debug("Starting process group: %s", process_group_id)
        result = await self.base.put(f"/flow/process-groups/{process_group_id}", payload)
        self.logger.info("Started process group: %s", process_group_id)
        return result

    async def stop_process_group(self, process_group_id: str) -> Dict[str, Any]:
        """Stop all processors in a process group."""
        # Get current process group details for revision
        pg_info = await self.get_process_group(process_group_id)
        revision = pg_info.get("revision", {}).get("version", 0)

        payload = {
            "id": process_group_id,
            "state": "STOPPED",
            "revision": {"version": revision},
        }

        self.logger.debug("Stopping process group: %s", process_group_id)
        result = await self.base.put(f"/flow/process-groups/{process_group_id}", payload)
        self.logger.info("Stopped process group: %s", process_group_id)
        return result

    async def set_parameter_context(
        self,
        process_group_id: str,
        parameter_context_id: str,
        revision: int = 0,
    ) -> Dict[str, Any]:
        """Set parameter context for a process group."""
        payload = {
            "revision": {"version": revision},
            "component": {
                "id": process_group_id,
                "parameterContext": {"id": parameter_context_id},
            },
        }

        self.logger.debug(
            "Setting parameter context %s for process group %s",
            parameter_context_id,
            process_group_id,
        )
        result = await self.base.put(f"/process-groups/{process_group_id}", payload)
        self.logger.info(
            "Set parameter context %s for process group %s",
            parameter_context_id,
            process_group_id,
        )
        return result

    async def get_process_group_status(self, process_group_id: str) -> Dict[str, Any]:
        """Get process group status."""
        self.logger.debug("Getting process group status: %s", process_group_id)
        return await self.base.get(f"/flow/process-groups/{process_group_id}/status")