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

    async def update_process_group(
        self,
        process_group_id: str,
        *,
        name: Optional[str] = None,
        comments: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update process group metadata without disturbing parameter context assignments."""

        pg_info = await self.get_process_group(process_group_id)
        revision = pg_info.get("revision", {}) if isinstance(pg_info, dict) else {}
        component = pg_info.get("component", {}) if isinstance(pg_info, dict) else {}

        payload: Dict[str, Any] = {
            "revision": {"version": revision.get("version", 0)},
            "component": {"id": process_group_id},
        }

        if revision.get("clientId"):
            payload["revision"]["clientId"] = revision["clientId"]

        # Preserve existing values when updates are not provided so we don't clear metadata
        if name is not None:
            payload["component"]["name"] = name
        elif isinstance(component, dict) and component.get("name") is not None:
            payload["component"]["name"] = component.get("name")

        if comments is not None:
            payload["component"]["comments"] = comments
        elif isinstance(component, dict) and component.get("comments") is not None:
            payload["component"]["comments"] = component.get("comments", "")

        # Keep the existing parameter context assignment so metadata edits don't detach it
        parameter_context = None
        if isinstance(component, dict):
            parameter_context = component.get("parameterContext")
        if parameter_context:
            payload["component"]["parameterContext"] = parameter_context

        self.logger.debug(
            "Updating process group %s with payload: %s",
            process_group_id,
            payload,
        )

        result = await self.base.put(f"/process-groups/{process_group_id}", payload)
        self.logger.info("Updated process group: %s", process_group_id)
        return result

    async def get_process_group_flow(self, process_group_id: str) -> Dict[str, Any]:
        """Get process group flow contents."""
        self.logger.debug("Getting process group flow: %s", process_group_id)
        return await self.base.get(f"/flow/process-groups/{process_group_id}")

    async def delete_process_group(
        self,
        process_group_id: str,
        revision: Optional[int] = None,
        client_id: Optional[str] = None,
    ) -> None:
        """Delete a process group."""

        if revision is None or client_id is None:
            current_pg = await self.get_process_group(process_group_id)
            current_revision = current_pg.get("revision", {})
            if revision is None:
                revision = current_revision.get("version", 0)
            if client_id is None:
                client_id = current_revision.get("clientId")

        params = {"version": revision}
        if client_id:
            params["clientId"] = client_id

        self.logger.debug(
            "Deleting process group: %s (revision: %s, clientId: %s)",
            process_group_id,
            revision,
            client_id,
        )
        await self.base.delete(f"/process-groups/{process_group_id}", params=params)
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
        revision: Optional[int] = None,
        client_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Set parameter context for a process group."""
        if revision is None or client_id is None:
            pg_info = await self.get_process_group(process_group_id)
            current_revision = pg_info.get("revision", {})
            if revision is None:
                revision = current_revision.get("version", 0)
            if client_id is None:
                client_id = current_revision.get("clientId")

        payload = {
            "revision": {"version": revision},
            "component": {
                "id": process_group_id,
                "parameterContext": {"id": parameter_context_id},
            },
        }

        if client_id:
            payload["revision"]["clientId"] = client_id

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

    async def get_processors(self, process_group_id: str) -> List[Dict[str, Any]]:
        """List processors within a process group."""
        self.logger.debug(
            "Listing processors for process group: %s", process_group_id
        )
        result = await self.base.get(f"/process-groups/{process_group_id}/processors")
        processors = result.get("processors", [])
        self.logger.info(
            "Retrieved %d processors for process group %s",
            len(processors),
            process_group_id,
        )
        return processors

    async def get_process_groups(self, parent_group_id: str) -> Dict[str, Any]:
        """List child process groups within a parent group."""
        self.logger.debug("Listing process groups under parent: %s", parent_group_id)
        result = await self.base.get(
            f"/process-groups/{parent_group_id}/process-groups"
        )
        self.logger.info(
            "Retrieved %d process groups under parent %s",
            len(result.get("processGroups", [])) if isinstance(result, dict) else 0,
            parent_group_id,
        )
        return result
