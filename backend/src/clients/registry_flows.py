"""Registry client for flow operations."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..core.logging import get_logger, LoggerMixin
from .registry_base import RegistryBaseClient, RegistryClientError

log = get_logger(__name__)


class RegistryFlowClient(LoggerMixin):
    """Client for Registry flow operations."""

    def __init__(self, base_client: RegistryBaseClient):
        self.base = base_client
        self.logger.info("Initialized Registry Flow client")

    async def create_flow(
        self,
        bucket_id: str,
        name: str,
        description: str = "",
        flow_type: str = "Flow",
    ) -> Dict[str, Any]:
        """Create a new flow in a bucket."""
        payload = {
            "name": name,
            "description": description,
            "type": flow_type,
        }

        self.logger.debug("Creating flow '%s' in bucket %s", name, bucket_id)
        result = await self.base.post(f"/buckets/{bucket_id}/flows", payload)

        flow_id = result.get("identifier")
        self.logger.info("Created flow '%s' with ID: %s", name, flow_id)
        return result

    async def get_flow(self, bucket_id: str, flow_id: str) -> Dict[str, Any]:
        """Get flow metadata."""
        self.logger.debug("Getting flow %s from bucket %s", flow_id, bucket_id)
        return await self.base.get(f"/buckets/{bucket_id}/flows/{flow_id}")

    async def list_flows(self, bucket_id: str) -> List[Dict[str, Any]]:
        """List all flows in a bucket."""
        self.logger.debug("Listing flows in bucket: %s", bucket_id)
        result = await self.base.get(f"/buckets/{bucket_id}/flows")
        # Registry API returns an array directly for flows
        if isinstance(result, list):
            return result
        # Handle case where it might be wrapped in an object
        return result.get("flows", [])

    async def update_flow(
        self,
        bucket_id: str,
        flow_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update flow metadata."""
        # Get current flow to preserve existing values
        current_flow = await self.get_flow(bucket_id, flow_id)

        payload = {
            "identifier": flow_id,
            "name": name if name is not None else current_flow.get("name"),
            "description": description if description is not None else current_flow.get("description", ""),
            "type": current_flow.get("type", "Flow"),
            "revision": current_flow.get("revision"),
        }

        self.logger.debug("Updating flow %s in bucket %s", flow_id, bucket_id)
        result = await self.base.put(f"/buckets/{bucket_id}/flows/{flow_id}", payload)
        self.logger.info("Updated flow %s in bucket %s", flow_id, bucket_id)
        return result

    async def delete_flow(self, bucket_id: str, flow_id: str) -> None:
        """Delete a flow and all its versions."""
        self.logger.debug("Deleting flow %s from bucket %s", flow_id, bucket_id)
        await self.base.delete(f"/buckets/{bucket_id}/flows/{flow_id}")
        self.logger.info("Deleted flow %s from bucket %s", flow_id, bucket_id)

    async def create_flow_version(
        self,
        bucket_id: str,
        flow_id: str,
        flow_contents: Dict[str, Any],
        version: Optional[int] = None,
        comments: str = "",
    ) -> Dict[str, Any]:
        """Create a new version of a flow."""
        payload = {
            "comments": comments,
            "flowContents": flow_contents,
        }

        if version is not None:
            payload["version"] = version

        self.logger.debug("Creating version for flow %s in bucket %s", flow_id, bucket_id)
        result = await self.base.post(f"/buckets/{bucket_id}/flows/{flow_id}/versions", payload)

        version_num = result.get("snapshotMetadata", {}).get("version")
        self.logger.info("Created version %s for flow %s", version_num, flow_id)
        return result

    async def get_flow_version(
        self, bucket_id: str, flow_id: str, version: int
    ) -> Dict[str, Any]:
        """Get a specific version of a flow."""
        self.logger.debug("Getting version %d of flow %s from bucket %s", version, flow_id, bucket_id)
        return await self.base.get(f"/buckets/{bucket_id}/flows/{flow_id}/versions/{version}")

    async def get_latest_flow_version(self, bucket_id: str, flow_id: str) -> Dict[str, Any]:
        """Get the latest version of a flow."""
        self.logger.debug("Getting latest version of flow %s from bucket %s", flow_id, bucket_id)
        return await self.base.get(f"/buckets/{bucket_id}/flows/{flow_id}/versions/latest")

    async def list_flow_versions(self, bucket_id: str, flow_id: str) -> List[Dict[str, Any]]:
        """List all versions of a flow."""
        self.logger.debug("Listing versions for flow %s in bucket %s", flow_id, bucket_id)
        result = await self.base.get(f"/buckets/{bucket_id}/flows/{flow_id}/versions")
        # Registry API returns an array directly for versions
        if isinstance(result, list):
            return result
        # Handle case where it might be wrapped in an object
        return result.get("versions", [])

    async def delete_flow_version(self, bucket_id: str, flow_id: str, version: int) -> None:
        """Delete a specific version of a flow."""
        self.logger.debug("Deleting version %d of flow %s from bucket %s", version, flow_id, bucket_id)
        await self.base.delete(f"/buckets/{bucket_id}/flows/{flow_id}/versions/{version}")
        self.logger.info("Deleted version %d of flow %s", version, flow_id)

    async def export_flow_version(
        self, bucket_id: str, flow_id: str, version: int
    ) -> Dict[str, Any]:
        """Export a specific version of a flow."""
        self.logger.debug("Exporting version %d of flow %s from bucket %s", version, flow_id, bucket_id)
        return await self.base.get(f"/buckets/{bucket_id}/flows/{flow_id}/versions/{version}/export")

    async def import_flow_version(
        self,
        bucket_id: str,
        flow_id: str,
        flow_snapshot: Dict[str, Any],
        comments: str = "Imported version",
    ) -> Dict[str, Any]:
        """Import a flow version from a snapshot."""
        payload = {
            "comments": comments,
            **flow_snapshot,
        }

        self.logger.debug("Importing version for flow %s in bucket %s", flow_id, bucket_id)
        result = await self.base.post(f"/buckets/{bucket_id}/flows/{flow_id}/versions/import", payload)

        version_num = result.get("snapshotMetadata", {}).get("version")
        self.logger.info("Imported version %s for flow %s", version_num, flow_id)
        return result

    async def compare_flow_versions(
        self,
        bucket_id: str,
        flow_id: str,
        version_a: int,
        version_b: int,
    ) -> Dict[str, Any]:
        """Compare two versions of a flow."""
        self.logger.debug(
            "Comparing versions %d and %d of flow %s in bucket %s",
            version_a,
            version_b,
            flow_id,
            bucket_id,
        )
        return await self.base.get(
            f"/buckets/{bucket_id}/flows/{flow_id}/diff/{version_a}/{version_b}"
        )