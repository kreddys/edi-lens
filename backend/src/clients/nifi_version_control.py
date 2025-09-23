"""NiFi client for version control operations."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..core.logging import get_logger, LoggerMixin
from .nifi_base import NiFiBaseClient, NiFiClientError

log = get_logger(__name__)


class NiFiVersionControlClient(LoggerMixin):
    """Client for NiFi version control operations with Registry."""

    def __init__(self, base_client: NiFiBaseClient):
        self.base = base_client
        self.logger.info("Initialized NiFi Version Control client")

    async def create_registry_client(
        self,
        name: str,
        url: str,
        description: str = "",
    ) -> Dict[str, Any]:
        """Create a registry client in NiFi."""
        payload = {
            "revision": {"version": 0},
            "component": {
                "name": name,
                "description": description,
                "properties": {"url": url},
                "type": "org.apache.nifi.registry.flow.NifiRegistryFlowRegistryClient",
            },
        }

        self.logger.debug("Creating registry client: %s", name)
        result = await self.base.post("/controller/registry-clients", payload)

        client_id = result.get("id")
        self.logger.info("Created registry client '%s' with ID: %s", name, client_id)
        return result

    async def list_registry_clients(self) -> List[Dict[str, Any]]:
        """List all registry clients."""
        self.logger.debug("Listing registry clients")
        result = await self.base.get("/controller/registry-clients")
        return result.get("registries", [])

    async def get_registry_client(self, client_id: str) -> Dict[str, Any]:
        """Get registry client details."""
        self.logger.debug("Getting registry client: %s", client_id)
        return await self.base.get(f"/controller/registry-clients/{client_id}")

    async def delete_registry_client(self, client_id: str, revision: int = 0) -> None:
        """Delete a registry client."""
        self.logger.debug("Deleting registry client: %s (revision: %d)", client_id, revision)
        await self.base.delete(f"/controller/registry-clients/{client_id}", params={"version": revision})
        self.logger.info("Deleted registry client: %s", client_id)

    async def start_version_control(
        self,
        process_group_id: str,
        registry_id: str,
        bucket_id: str,
        flow_name: str,
        flow_description: str = "",
        comments: str = "Initial version",
        *,
        flow_id: Optional[str] = None,
        flow_version: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Place a process group under version control."""
        pg_info = await self.base.get(f"/process-groups/{process_group_id}")
        process_group_revision = pg_info.get("revision", {"version": 0})

        payload = {
            "processGroupRevision": process_group_revision,
            "versionControlInformation": {
                "groupId": process_group_id,
                "registryId": registry_id,
                "bucketId": bucket_id,
                "flowName": flow_name,
                "flowDescription": flow_description,
                "comments": comments,
                "storageLocation": bucket_id,
            },
            "componentId": process_group_id,
            "disconnectedNodeAcknowledged": False,
        }

        if flow_id:
            payload["versionControlInformation"]["flowId"] = flow_id
            payload["versionControlInformation"]["version"] = (
                flow_version if flow_version is not None else 0
            )

        self.logger.debug(
            "Starting version control for process group %s with payload %s",
            process_group_id,
            payload,
        )
        result = await self.base.post(f"/versions/process-groups/{process_group_id}", payload)
        self.logger.info("Started version control for process group: %s", process_group_id)
        return result

    async def stop_version_control(self, process_group_id: str) -> Dict[str, Any]:
        """Remove a process group from version control."""
        # Get current process group to get revision
        pg_info = await self.base.get(f"/process-groups/{process_group_id}")
        revision = pg_info.get("revision", {}).get("version", 0)

        self.logger.debug("Stopping version control for process group: %s", process_group_id)
        result = await self.base.delete(
            f"/versions/process-groups/{process_group_id}", params={"version": revision}
        )
        self.logger.info("Stopped version control for process group: %s", process_group_id)
        return result

    async def commit_local_changes(
        self,
        process_group_id: str,
        comments: str = "Updated flow",
    ) -> Dict[str, Any]:
        """Commit local changes to registry."""
        # Get current process group version info
        pg_info = await self.base.get(f"/versions/process-groups/{process_group_id}")
        revision = pg_info.get("processGroupRevision", {}).get("version", 0)

        payload = {
            "processGroupRevision": {"version": revision},
            "versionControlInformation": {
                "comments": comments,
            },
        }

        self.logger.debug("Committing changes for process group: %s", process_group_id)
        result = await self.base.put(f"/versions/process-groups/{process_group_id}", payload)
        self.logger.info("Committed changes for process group: %s", process_group_id)
        return result

    async def update_from_registry(self, process_group_id: str) -> Dict[str, Any]:
        """Update process group from latest version in registry."""
        payload = {"processGroupRevision": {"version": 0}}

        self.logger.debug("Updating process group from registry: %s", process_group_id)

        # Create update request
        result = await self.base.post(
            f"/versions/update-requests/process-groups/{process_group_id}", payload
        )

        request_id = result.get("request", {}).get("requestId")
        if not request_id:
            raise NiFiClientError("Failed to create update request")

        self.logger.info("Created update request %s for process group: %s", request_id, process_group_id)

        # Poll for completion
        import asyncio

        while True:
            status_result = await self.base.get(f"/versions/update-requests/{request_id}")
            state = status_result.get("request", {}).get("state", "SUBMITTED")

            if state == "COMPLETED":
                self.logger.info("Update completed for process group: %s", process_group_id)
                # Clean up request
                await self.base.delete(f"/versions/update-requests/{request_id}")
                return status_result
            elif state == "FAILED":
                error_msg = status_result.get("request", {}).get("failureReason", "Unknown error")
                self.logger.error("Update failed for process group %s: %s", process_group_id, error_msg)
                # Clean up request
                await self.base.delete(f"/versions/update-requests/{request_id}")
                raise NiFiClientError(f"Update failed: {error_msg}")

            await asyncio.sleep(1)

    async def revert_local_changes(self, process_group_id: str) -> Dict[str, Any]:
        """Revert local changes to registry version."""
        payload = {"processGroupRevision": {"version": 0}}

        self.logger.debug("Reverting process group to registry version: %s", process_group_id)

        # Create revert request
        result = await self.base.post(
            f"/versions/revert-requests/process-groups/{process_group_id}", payload
        )

        request_id = result.get("request", {}).get("requestId")
        if not request_id:
            raise NiFiClientError("Failed to create revert request")

        self.logger.info("Created revert request %s for process group: %s", request_id, process_group_id)

        # Poll for completion
        import asyncio

        while True:
            status_result = await self.base.get(f"/versions/revert-requests/{request_id}")
            state = status_result.get("request", {}).get("state", "SUBMITTED")

            if state == "COMPLETED":
                self.logger.info("Revert completed for process group: %s", process_group_id)
                # Clean up request
                await self.base.delete(f"/versions/revert-requests/{request_id}")
                return status_result
            elif state == "FAILED":
                error_msg = status_result.get("request", {}).get("failureReason", "Unknown error")
                self.logger.error("Revert failed for process group %s: %s", process_group_id, error_msg)
                # Clean up request
                await self.base.delete(f"/versions/revert-requests/{request_id}")
                raise NiFiClientError(f"Revert failed: {error_msg}")

            await asyncio.sleep(1)

    async def get_version_control_info(self, process_group_id: str) -> Dict[str, Any]:
        """Get version control information for a process group."""
        self.logger.debug("Getting version control info for process group: %s", process_group_id)
        return await self.base.get(f"/versions/process-groups/{process_group_id}")

    async def get_local_modifications(self, process_group_id: str) -> Dict[str, Any]:
        """Get local modifications for a version controlled process group."""
        self.logger.debug("Getting local modifications for process group: %s", process_group_id)
        return await self.base.get(f"/process-groups/{process_group_id}/local-modifications")