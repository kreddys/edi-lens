"""Registry flow service for basic Registry operations."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..clients.registry_unified import RegistryUnifiedClient
from ..core.logging import get_logger, LoggerMixin

log = get_logger(__name__)


class RegistryFlowError(RuntimeError):
    """Raised when Registry flow operations fail."""


class RegistryFlowService(LoggerMixin):
    """Service for managing flows in Registry."""

    def __init__(self, registry_client: RegistryUnifiedClient):
        self.registry = registry_client
        self.logger.info("Initialized Registry Flow Service")

    # Bucket Operations
    async def list_buckets(self) -> List[Dict[str, Any]]:
        """List all available buckets."""
        try:
            buckets = await self.registry.buckets.list_buckets()
            self.logger.debug("Retrieved %d buckets", len(buckets))
            return buckets
        except Exception as exc:
            self.logger.error("Failed to list buckets: %s", exc)
            raise RegistryFlowError(f"Failed to list buckets: {exc}") from exc

    async def create_bucket(
        self,
        name: str,
        description: str = "",
        allow_bundle_redeploy: bool = False,
        allow_public_read: bool = False,
    ) -> Dict[str, Any]:
        """Create a new bucket."""
        try:
            result = await self.registry.buckets.create_bucket(
                name=name,
                description=description,
                allow_bundle_redeploy=allow_bundle_redeploy,
                allow_public_read=allow_public_read,
            )
            self.logger.info("Created bucket: %s", name)
            return result
        except Exception as exc:
            self.logger.error("Failed to create bucket '%s': %s", name, exc)
            raise RegistryFlowError(f"Failed to create bucket: {exc}") from exc

    async def get_bucket(self, bucket_id: str) -> Dict[str, Any]:
        """Get bucket details."""
        try:
            return await self.registry.buckets.get_bucket(bucket_id)
        except Exception as exc:
            self.logger.error("Failed to get bucket %s: %s", bucket_id, exc)
            raise RegistryFlowError(f"Failed to get bucket: {exc}") from exc

    async def delete_bucket(self, bucket_id: str) -> None:
        """Delete a bucket."""
        try:
            await self.registry.buckets.delete_bucket(bucket_id)
            self.logger.info("Deleted bucket: %s", bucket_id)
        except Exception as exc:
            self.logger.error("Failed to delete bucket %s: %s", bucket_id, exc)
            raise RegistryFlowError(f"Failed to delete bucket: {exc}") from exc

    # Flow Operations
    async def list_flows(self, bucket_id: str) -> List[Dict[str, Any]]:
        """List flows in a bucket."""
        try:
            flows = await self.registry.flows.list_flows(bucket_id)
            self.logger.debug("Retrieved %d flows from bucket %s", len(flows), bucket_id)
            return flows
        except Exception as exc:
            self.logger.error("Failed to list flows in bucket %s: %s", bucket_id, exc)
            raise RegistryFlowError(f"Failed to list flows: {exc}") from exc

    async def create_flow(
        self,
        bucket_id: str,
        name: str,
        description: str = "",
        flow_type: str = "Flow",
    ) -> Dict[str, Any]:
        """Create a new flow in Registry."""
        try:
            result = await self.registry.flows.create_flow(
                bucket_id=bucket_id,
                name=name,
                description=description,
                flow_type=flow_type,
            )
            self.logger.info("Created flow '%s' in bucket %s", name, bucket_id)
            return result
        except Exception as exc:
            self.logger.error("Failed to create flow '%s' in bucket %s: %s", name, bucket_id, exc)
            raise RegistryFlowError(f"Failed to create flow: {exc}") from exc

    async def get_flow(self, bucket_id: str, flow_id: str) -> Dict[str, Any]:
        """Get flow metadata."""
        try:
            return await self.registry.flows.get_flow(bucket_id, flow_id)
        except Exception as exc:
            self.logger.error("Failed to get flow %s from bucket %s: %s", flow_id, bucket_id, exc)
            raise RegistryFlowError(f"Failed to get flow: {exc}") from exc

    async def update_flow(
        self,
        bucket_id: str,
        flow_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update flow metadata."""
        try:
            result = await self.registry.flows.update_flow(
                bucket_id=bucket_id,
                flow_id=flow_id,
                name=name,
                description=description,
            )
            self.logger.info("Updated flow %s in bucket %s", flow_id, bucket_id)
            return result
        except Exception as exc:
            self.logger.error("Failed to update flow %s in bucket %s: %s", flow_id, bucket_id, exc)
            raise RegistryFlowError(f"Failed to update flow: {exc}") from exc

    async def delete_flow(self, bucket_id: str, flow_id: str) -> None:
        """Delete a flow and all its versions."""
        try:
            await self.registry.flows.delete_flow(bucket_id, flow_id)
            self.logger.info("Deleted flow %s from bucket %s", flow_id, bucket_id)
        except Exception as exc:
            self.logger.error("Failed to delete flow %s from bucket %s: %s", flow_id, bucket_id, exc)
            raise RegistryFlowError(f"Failed to delete flow: {exc}") from exc

    # Flow Version Operations
    async def create_flow_version(
        self,
        bucket_id: str,
        flow_id: str,
        flow_contents: Dict[str, Any],
        version: Optional[int] = None,
        comments: str = "",
    ) -> Dict[str, Any]:
        """Create a new version of a flow."""
        try:
            result = await self.registry.flows.create_flow_version(
                bucket_id=bucket_id,
                flow_id=flow_id,
                flow_contents=flow_contents,
                version=version,
                comments=comments,
            )
            version_num = result.get("snapshotMetadata", {}).get("version")
            self.logger.info("Created version %s for flow %s", version_num, flow_id)
            return result
        except Exception as exc:
            self.logger.error("Failed to create version for flow %s: %s", flow_id, exc)
            raise RegistryFlowError(f"Failed to create flow version: {exc}") from exc

    async def get_flow_version(
        self, bucket_id: str, flow_id: str, version: int
    ) -> Dict[str, Any]:
        """Get a specific version of a flow."""
        try:
            return await self.registry.flows.get_flow_version(bucket_id, flow_id, version)
        except Exception as exc:
            self.logger.error("Failed to get version %d of flow %s: %s", version, flow_id, exc)
            raise RegistryFlowError(f"Failed to get flow version: {exc}") from exc

    async def get_latest_flow_version(self, bucket_id: str, flow_id: str) -> Dict[str, Any]:
        """Get the latest version of a flow."""
        try:
            return await self.registry.flows.get_latest_flow_version(bucket_id, flow_id)
        except Exception as exc:
            self.logger.error("Failed to get latest version of flow %s: %s", flow_id, exc)
            raise RegistryFlowError(f"Failed to get latest flow version: {exc}") from exc

    async def list_flow_versions(self, bucket_id: str, flow_id: str) -> List[Dict[str, Any]]:
        """List all versions of a flow."""
        try:
            versions = await self.registry.flows.list_flow_versions(bucket_id, flow_id)
            self.logger.debug("Retrieved %d versions for flow %s", len(versions), flow_id)
            return versions
        except Exception as exc:
            self.logger.error("Failed to list versions for flow %s: %s", flow_id, exc)
            raise RegistryFlowError(f"Failed to list flow versions: {exc}") from exc

    async def delete_flow_version(self, bucket_id: str, flow_id: str, version: int) -> None:
        """Delete a specific version of a flow."""
        try:
            await self.registry.flows.delete_flow_version(bucket_id, flow_id, version)
            self.logger.info("Deleted version %d of flow %s", version, flow_id)
        except Exception as exc:
            self.logger.error("Failed to delete version %d of flow %s: %s", version, flow_id, exc)
            raise RegistryFlowError(f"Failed to delete flow version: {exc}") from exc

    async def export_flow_version(
        self, bucket_id: str, flow_id: str, version: int
    ) -> Dict[str, Any]:
        """Export a specific version of a flow."""
        try:
            return await self.registry.flows.export_flow_version(bucket_id, flow_id, version)
        except Exception as exc:
            self.logger.error("Failed to export version %d of flow %s: %s", version, flow_id, exc)
            raise RegistryFlowError(f"Failed to export flow version: {exc}") from exc

    async def import_flow_version(
        self,
        bucket_id: str,
        flow_id: str,
        flow_snapshot: Dict[str, Any],
        comments: str = "Imported version",
    ) -> Dict[str, Any]:
        """Import a flow version from a snapshot."""
        try:
            result = await self.registry.flows.import_flow_version(
                bucket_id=bucket_id,
                flow_id=flow_id,
                flow_snapshot=flow_snapshot,
                comments=comments,
            )
            version_num = result.get("snapshotMetadata", {}).get("version")
            self.logger.info("Imported version %s for flow %s", version_num, flow_id)
            return result
        except Exception as exc:
            self.logger.error("Failed to import version for flow %s: %s", flow_id, exc)
            raise RegistryFlowError(f"Failed to import flow version: {exc}") from exc

    async def compare_flow_versions(
        self,
        bucket_id: str,
        flow_id: str,
        version_a: int,
        version_b: int,
    ) -> Dict[str, Any]:
        """Compare two versions of a flow."""
        try:
            return await self.registry.flows.compare_flow_versions(
                bucket_id, flow_id, version_a, version_b
            )
        except Exception as exc:
            self.logger.error(
                "Failed to compare versions %d and %d of flow %s: %s",
                version_a,
                version_b,
                flow_id,
                exc,
            )
            raise RegistryFlowError(f"Failed to compare flow versions: {exc}") from exc