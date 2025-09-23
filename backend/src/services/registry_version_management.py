"""Registry version management service - handles flow versioning operations."""

from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional

from ..clients.registry_unified import RegistryUnifiedClient
from ..core.logging import get_logger, LoggerMixin

log = get_logger(__name__)


class RegistryVersionManagementError(RuntimeError):
    """Raised when Registry version management operations fail."""


class RegistryVersionManagement(LoggerMixin):
    """Service for managing flow versions in NiFi Registry."""

    def __init__(self, registry_client: RegistryUnifiedClient):
        self.registry = registry_client
        self.logger.info("Initialized Registry Version Management service")

    async def create_flow_version(
        self,
        bucket_id: str,
        flow_id: str,
        flow_contents: Dict[str, Any],
        version: Optional[int] = None,
        comments: str = ""
    ) -> Dict[str, Any]:
        """Create a new version of a flow."""
        try:
            target_version = version
            if target_version is None:
                flow_metadata = await self.registry.flows.get_flow(bucket_id, flow_id)
                existing_versions = flow_metadata.get("versionCount", 0)
                target_version = int(existing_versions) + 1
            else:
                flow_metadata = await self.registry.flows.get_flow(bucket_id, flow_id)

            # Extract parameter context information if present in the snapshot
            parameter_contexts_map: Dict[str, Any] = {}
            flow_snapshot = copy.deepcopy(flow_contents)
            flow_snapshot.pop("parameterContext", None)
            snapshot_context_map = flow_snapshot.pop("_parameterContexts", None)
            if isinstance(snapshot_context_map, dict):
                parameter_contexts_map = snapshot_context_map

            version = await self.registry.flows.create_flow_version(
                bucket_id=bucket_id,
                flow_id=flow_id,
                flow_contents=flow_snapshot,
                version=target_version,
                comments=comments,
                parameter_contexts=parameter_contexts_map,
                flow_metadata=flow_metadata,
            )

            version_number = version.get("version") or version.get("snapshotMetadata", {}).get("version")

            result = {
                "success": True,
                "bucket_id": bucket_id,
                "flow_id": flow_id,
                "version": version_number,
                "comments": comments,
                "created_timestamp": version.get("timestamp"),
                "author": version.get("author"),
                "snapshot_metadata": version.get("snapshotMetadata", {}),
                "flow_contents": version.get("flowContents", {})
            }

            self.logger.info("Created flow version %d for flow %s in bucket %s",
                           version_number, flow_id, bucket_id)
            return result

        except Exception as exc:
            self.logger.error("Failed to create version for flow %s in bucket %s: %s",
                            flow_id, bucket_id, exc)
            raise RegistryVersionManagementError(f"Failed to create flow version: {exc}") from exc

    async def get_flow_version(
        self,
        bucket_id: str,
        flow_id: str,
        version: int
    ) -> Dict[str, Any]:
        """Get a specific version of a flow."""
        try:
            flow_version = await self.registry.flows.get_flow_version(bucket_id, flow_id, version)

            result = {
                "bucket_id": bucket_id,
                "flow_id": flow_id,
                "version": flow_version.get("version"),
                "comments": flow_version.get("comments", ""),
                "created_timestamp": flow_version.get("timestamp"),
                "author": flow_version.get("author"),
                "snapshot_metadata": flow_version.get("snapshotMetadata", {}),
                "flow_contents": flow_version.get("flowContents", {})
            }

            self.logger.debug("Retrieved flow version %d for flow %s in bucket %s",
                            version, flow_id, bucket_id)
            return result

        except Exception as exc:
            self.logger.error("Failed to get version %d for flow %s in bucket %s: %s",
                            version, flow_id, bucket_id, exc)
            raise RegistryVersionManagementError(f"Failed to get flow version: {exc}") from exc

    async def get_latest_flow_version(
        self,
        bucket_id: str,
        flow_id: str
    ) -> Dict[str, Any]:
        """Get the latest version of a flow."""
        try:
            latest_version = await self.registry.flows.get_latest_flow_version(bucket_id, flow_id)

            result = {
                "bucket_id": bucket_id,
                "flow_id": flow_id,
                "version": latest_version.get("version"),
                "comments": latest_version.get("comments", ""),
                "created_timestamp": latest_version.get("timestamp"),
                "author": latest_version.get("author"),
                "snapshot_metadata": latest_version.get("snapshotMetadata", {}),
                "flow_contents": latest_version.get("flowContents", {})
            }

            self.logger.debug("Retrieved latest version %d for flow %s in bucket %s",
                            result["version"], flow_id, bucket_id)
            return result

        except Exception as exc:
            self.logger.error("Failed to get latest version for flow %s in bucket %s: %s",
                            flow_id, bucket_id, exc)
            raise RegistryVersionManagementError(f"Failed to get latest flow version: {exc}") from exc

    async def list_flow_versions(
        self,
        bucket_id: str,
        flow_id: str
    ) -> List[Dict[str, Any]]:
        """List all versions of a flow."""
        try:
            versions = await self.registry.flows.list_flow_versions(bucket_id, flow_id)

            result = []
            for version in versions:
                result.append({
                    "bucket_id": bucket_id,
                    "flow_id": flow_id,
                    "version": version.get("version"),
                    "comments": version.get("comments", ""),
                    "created_timestamp": version.get("timestamp"),
                    "author": version.get("author"),
                    "snapshot_metadata": version.get("snapshotMetadata", {})
                })

            self.logger.debug("Listed %d versions for flow %s in bucket %s",
                            len(result), flow_id, bucket_id)
            return result

        except Exception as exc:
            self.logger.error("Failed to list versions for flow %s in bucket %s: %s",
                            flow_id, bucket_id, exc)
            raise RegistryVersionManagementError(f"Failed to list flow versions: {exc}") from exc

    async def delete_flow_version(
        self,
        bucket_id: str,
        flow_id: str,
        version: int
    ) -> Dict[str, Any]:
        """Delete a specific version of a flow."""
        try:
            await self.registry.flows.delete_flow_version(bucket_id, flow_id, version)

            result = {
                "success": True,
                "bucket_id": bucket_id,
                "flow_id": flow_id,
                "version": version,
                "message": f"Flow version {version} deleted successfully"
            }

            self.logger.info("Deleted flow version %d for flow %s in bucket %s",
                           version, flow_id, bucket_id)
            return result

        except Exception as exc:
            self.logger.error("Failed to delete version %d for flow %s in bucket %s: %s",
                            version, flow_id, bucket_id, exc)
            raise RegistryVersionManagementError(f"Failed to delete flow version: {exc}") from exc

    async def get_version_diff(
        self,
        bucket_id: str,
        flow_id: str,
        version_a: int,
        version_b: int
    ) -> Dict[str, Any]:
        """Compare two versions of a flow and return differences."""
        try:
            # Get both versions
            version_a_data = await self.get_flow_version(bucket_id, flow_id, version_a)
            version_b_data = await self.get_flow_version(bucket_id, flow_id, version_b)

            # Extract flow contents
            contents_a = version_a_data.get("flow_contents", {})
            contents_b = version_b_data.get("flow_contents", {})

            # Basic comparison (this could be enhanced with more detailed diff logic)
            result = {
                "bucket_id": bucket_id,
                "flow_id": flow_id,
                "version_a": version_a,
                "version_b": version_b,
                "version_a_metadata": {
                    "version": version_a_data.get("version"),
                    "timestamp": version_a_data.get("created_timestamp"),
                    "author": version_a_data.get("author"),
                    "comments": version_a_data.get("comments", "")
                },
                "version_b_metadata": {
                    "version": version_b_data.get("version"),
                    "timestamp": version_b_data.get("created_timestamp"),
                    "author": version_b_data.get("author"),
                    "comments": version_b_data.get("comments", "")
                },
                "processor_count_a": len(contents_a.get("processors", [])),
                "processor_count_b": len(contents_b.get("processors", [])),
                "connection_count_a": len(contents_a.get("connections", [])),
                "connection_count_b": len(contents_b.get("connections", [])),
                "contents_identical": contents_a == contents_b
            }

            self.logger.debug("Compared versions %d and %d for flow %s in bucket %s",
                            version_a, version_b, flow_id, bucket_id)
            return result

        except Exception as exc:
            self.logger.error("Failed to compare versions %d and %d for flow %s in bucket %s: %s",
                            version_a, version_b, flow_id, bucket_id, exc)
            raise RegistryVersionManagementError(f"Failed to compare flow versions: {exc}") from exc

    async def export_flow_version(
        self,
        bucket_id: str,
        flow_id: str,
        version: int
    ) -> Dict[str, Any]:
        """Export a specific flow version for external use."""
        try:
            flow_version = await self.get_flow_version(bucket_id, flow_id, version)

            # Create export package
            export_data = {
                "metadata": {
                    "bucket_id": bucket_id,
                    "flow_id": flow_id,
                    "version": version,
                    "comments": flow_version.get("comments", ""),
                    "created_timestamp": flow_version.get("created_timestamp"),
                    "author": flow_version.get("author"),
                    "exported_timestamp": flow_version.get("created_timestamp")  # Could use current time
                },
                "flow_contents": flow_version.get("flow_contents", {}),
                "snapshot_metadata": flow_version.get("snapshot_metadata", {})
            }

            result = {
                "success": True,
                "export_data": export_data,
                "message": f"Flow version {version} exported successfully"
            }

            self.logger.info("Exported flow version %d for flow %s in bucket %s",
                           version, flow_id, bucket_id)
            return result

        except Exception as exc:
            self.logger.error("Failed to export version %d for flow %s in bucket %s: %s",
                            version, flow_id, bucket_id, exc)
            raise RegistryVersionManagementError(f"Failed to export flow version: {exc}") from exc

    async def get_flow_version_metadata_only(
        self,
        bucket_id: str,
        flow_id: str,
        version: int
    ) -> Dict[str, Any]:
        """Get only the metadata for a flow version (without full contents)."""
        try:
            versions = await self.list_flow_versions(bucket_id, flow_id)

            for version_info in versions:
                if version_info.get("version") == version:
                    return version_info

            raise RegistryVersionManagementError(f"Version {version} not found")

        except Exception as exc:
            self.logger.error("Failed to get metadata for version %d of flow %s in bucket %s: %s",
                            version, flow_id, bucket_id, exc)
            raise RegistryVersionManagementError(f"Failed to get flow version metadata: {exc}") from exc