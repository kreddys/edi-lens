"""Registry bucket management service - handles bucket operations."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..clients.registry_unified import RegistryUnifiedClient
from ..core.logging import get_logger, LoggerMixin

log = get_logger(__name__)


class RegistryBucketManagementError(RuntimeError):
    """Raised when Registry bucket management operations fail."""


class RegistryBucketManagement(LoggerMixin):
    """Service for managing buckets in NiFi Registry."""

    def __init__(self, registry_client: RegistryUnifiedClient):
        self.registry = registry_client
        self.logger.info("Initialized Registry Bucket Management service")

    async def create_bucket(
        self,
        name: str,
        description: str = "",
        allow_public_read: bool = False
    ) -> Dict[str, Any]:
        """Create a new bucket in the Registry."""
        try:
            bucket = await self.registry.buckets.create_bucket(
                name=name,
                description=description,
                allow_public_read=allow_public_read
            )

            bucket_id = bucket.get("identifier")

            result = {
                "success": True,
                "bucket_id": bucket_id,
                "name": name,
                "description": description,
                "allow_public_read": allow_public_read,
                "created_timestamp": bucket.get("createdTimestamp")
            }

            self.logger.info("Created bucket: %s (%s)", name, bucket_id)
            return result

        except Exception as exc:
            self.logger.error("Failed to create bucket %s: %s", name, exc)
            raise RegistryBucketManagementError(f"Failed to create bucket: {exc}") from exc

    async def get_bucket(self, bucket_id: str) -> Dict[str, Any]:
        """Get bucket details by ID."""
        try:
            bucket = await self.registry.buckets.get_bucket(bucket_id)

            result = {
                "bucket_id": bucket.get("identifier"),
                "name": bucket.get("name"),
                "description": bucket.get("description", ""),
                "allow_public_read": bucket.get("allowPublicRead", False),
                "created_timestamp": bucket.get("createdTimestamp"),
                "modified_timestamp": bucket.get("modifiedTimestamp"),
                "permissions": bucket.get("permissions", {}),
                "revision": bucket.get("revision", {})
            }

            self.logger.debug("Retrieved bucket: %s", bucket_id)
            return result

        except Exception as exc:
            self.logger.error("Failed to get bucket %s: %s", bucket_id, exc)
            raise RegistryBucketManagementError(f"Failed to get bucket: {exc}") from exc

    async def update_bucket(
        self,
        bucket_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        allow_public_read: Optional[bool] = None
    ) -> Dict[str, Any]:
        """Update bucket properties."""
        try:
            # Get current bucket details for revision
            current_bucket = await self.registry.buckets.get_bucket(bucket_id)
            revision = current_bucket.get("revision", {})

            # Prepare update data
            update_data = {
                "identifier": bucket_id,
                "name": name or current_bucket.get("name"),
                "description": description or current_bucket.get("description", ""),
                "allowPublicRead": allow_public_read if allow_public_read is not None else current_bucket.get("allowPublicRead", False),
                "revision": revision
            }

            updated_bucket = await self.registry.buckets.update_bucket(bucket_id, update_data)

            result = {
                "success": True,
                "bucket_id": bucket_id,
                "name": updated_bucket.get("name"),
                "description": updated_bucket.get("description", ""),
                "allow_public_read": updated_bucket.get("allowPublicRead", False),
                "modified_timestamp": updated_bucket.get("modifiedTimestamp")
            }

            self.logger.info("Updated bucket: %s", bucket_id)
            return result

        except Exception as exc:
            self.logger.error("Failed to update bucket %s: %s", bucket_id, exc)
            raise RegistryBucketManagementError(f"Failed to update bucket: {exc}") from exc

    async def delete_bucket(self, bucket_id: str) -> Dict[str, Any]:
        """Delete a bucket from the Registry."""
        try:
            # Get current bucket for revision
            current_bucket = await self.registry.buckets.get_bucket(bucket_id)
            revision = current_bucket.get("revision", {})

            await self.registry.buckets.delete_bucket(bucket_id, revision)

            result = {
                "success": True,
                "bucket_id": bucket_id,
                "message": "Bucket deleted successfully"
            }

            self.logger.info("Deleted bucket: %s", bucket_id)
            return result

        except Exception as exc:
            self.logger.error("Failed to delete bucket %s: %s", bucket_id, exc)
            raise RegistryBucketManagementError(f"Failed to delete bucket: {exc}") from exc

    async def list_buckets(self) -> List[Dict[str, Any]]:
        """List all buckets in the Registry."""
        try:
            buckets = await self.registry.buckets.list_buckets()

            result = []
            for bucket in buckets:
                result.append({
                    "bucket_id": bucket.get("identifier"),
                    "name": bucket.get("name"),
                    "description": bucket.get("description", ""),
                    "allow_public_read": bucket.get("allowPublicRead", False),
                    "created_timestamp": bucket.get("createdTimestamp"),
                    "modified_timestamp": bucket.get("modifiedTimestamp"),
                    "permissions": bucket.get("permissions", {})
                })

            self.logger.debug("Listed %d buckets", len(result))
            return result

        except Exception as exc:
            self.logger.error("Failed to list buckets: %s", exc)
            raise RegistryBucketManagementError(f"Failed to list buckets: {exc}") from exc

    async def get_bucket_by_name(self, bucket_name: str) -> Optional[Dict[str, Any]]:
        """Find a bucket by name."""
        try:
            buckets = await self.list_buckets()

            for bucket in buckets:
                if bucket.get("name") == bucket_name:
                    return bucket

            return None

        except Exception as exc:
            self.logger.error("Failed to find bucket by name %s: %s", bucket_name, exc)
            raise RegistryBucketManagementError(f"Failed to find bucket by name: {exc}") from exc

    async def get_or_create_bucket(
        self,
        bucket_name: str,
        description: str = "",
        allow_public_read: bool = False
    ) -> Dict[str, Any]:
        """Get an existing bucket by name or create it if it doesn't exist."""
        try:
            # Try to find existing bucket
            existing_bucket = await self.get_bucket_by_name(bucket_name)

            if existing_bucket:
                self.logger.debug("Found existing bucket: %s", bucket_name)
                return existing_bucket

            # Create new bucket if not found
            self.logger.info("Creating new bucket: %s", bucket_name)
            return await self.create_bucket(
                name=bucket_name,
                description=description,
                allow_public_read=allow_public_read
            )

        except Exception as exc:
            self.logger.error("Failed to get or create bucket %s: %s", bucket_name, exc)
            raise RegistryBucketManagementError(f"Failed to get or create bucket: {exc}") from exc

    async def check_bucket_exists(self, bucket_name: str) -> bool:
        """Check if a bucket exists by name."""
        try:
            bucket = await self.get_bucket_by_name(bucket_name)
            return bucket is not None

        except Exception as exc:
            self.logger.error("Failed to check if bucket exists %s: %s", bucket_name, exc)
            raise RegistryBucketManagementError(f"Failed to check bucket existence: {exc}") from exc