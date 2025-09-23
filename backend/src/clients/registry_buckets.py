"""Registry client for bucket operations."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..core.logging import get_logger, LoggerMixin
from .registry_base import RegistryBaseClient, RegistryClientError

log = get_logger(__name__)


class RegistryBucketClient(LoggerMixin):
    """Client for Registry bucket operations."""

    def __init__(self, base_client: RegistryBaseClient):
        self.base = base_client
        self.logger.info("Initialized Registry Bucket client")

    async def create_bucket(
        self,
        name: str,
        description: str = "",
        allow_bundle_redeploy: bool = False,
        allow_public_read: bool = False,
    ) -> Dict[str, Any]:
        """Create a new bucket."""
        payload = {
            "name": name,
            "description": description,
            "allowBundleRedeploy": allow_bundle_redeploy,
            "allowPublicRead": allow_public_read,
        }

        self.logger.debug("Creating bucket: %s", name)
        result = await self.base.post("/buckets", payload)

        bucket_id = result.get("identifier")
        self.logger.info("Created bucket '%s' with ID: %s", name, bucket_id)
        return result

    async def get_bucket(self, bucket_id: str) -> Dict[str, Any]:
        """Get bucket details."""
        self.logger.debug("Getting bucket: %s", bucket_id)
        return await self.base.get(f"/buckets/{bucket_id}")

    async def list_buckets(self) -> List[Dict[str, Any]]:
        """List all buckets."""
        self.logger.debug("Listing buckets")
        result = await self.base.get("/buckets")
        # Registry API returns an array directly for buckets
        if isinstance(result, list):
            return result
        # Handle case where it might be wrapped in an object
        return result.get("buckets", [])

    async def update_bucket(
        self,
        bucket_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        allow_bundle_redeploy: Optional[bool] = None,
        allow_public_read: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Update bucket details."""
        # Get current bucket to preserve existing values
        current_bucket = await self.get_bucket(bucket_id)

        payload = {
            "identifier": bucket_id,
            "name": name if name is not None else current_bucket.get("name"),
            "description": description if description is not None else current_bucket.get("description", ""),
            "allowBundleRedeploy": allow_bundle_redeploy
            if allow_bundle_redeploy is not None
            else current_bucket.get("allowBundleRedeploy", False),
            "allowPublicRead": allow_public_read
            if allow_public_read is not None
            else current_bucket.get("allowPublicRead", False),
            "revision": current_bucket.get("revision"),
        }

        self.logger.debug("Updating bucket: %s", bucket_id)
        result = await self.base.put(f"/buckets/{bucket_id}", payload)
        self.logger.info("Updated bucket: %s", bucket_id)
        return result

    async def delete_bucket(self, bucket_id: str) -> None:
        """Delete a bucket."""
        self.logger.debug("Deleting bucket: %s", bucket_id)
        await self.base.delete(f"/buckets/{bucket_id}")
        self.logger.info("Deleted bucket: %s", bucket_id)

    async def get_bucket_permissions(self, bucket_id: str) -> Dict[str, Any]:
        """Get bucket permissions (if security is enabled)."""
        self.logger.debug("Getting bucket permissions: %s", bucket_id)
        try:
            return await self.base.get(f"/buckets/{bucket_id}/permissions")
        except RegistryClientError as e:
            # Permissions might not be available if security is disabled
            if "404" in str(e):
                self.logger.debug("Bucket permissions not available (security may be disabled)")
                return {}
            raise