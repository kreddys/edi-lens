"""Registry flow management service - handles flow operations in Registry."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..clients.registry_unified import RegistryUnifiedClient
from ..core.logging import get_logger, LoggerMixin

log = get_logger(__name__)


class RegistryFlowManagementError(RuntimeError):
    """Raised when Registry flow management operations fail."""


class RegistryFlowManagement(LoggerMixin):
    """Service for managing flows in NiFi Registry."""

    def __init__(self, registry_client: RegistryUnifiedClient):
        self.registry = registry_client
        self.logger.info("Initialized Registry Flow Management service")

    async def create_flow(
        self,
        bucket_id: str,
        flow_name: str,
        description: str = "",
        flow_type: str = "Flow"
    ) -> Dict[str, Any]:
        """Create a new flow in a bucket."""
        try:
            flow = await self.registry.flows.create_flow(
                bucket_id=bucket_id,
                name=flow_name,
                description=description,
                type=flow_type
            )

            flow_id = flow.get("identifier")

            result = {
                "success": True,
                "flow_id": flow_id,
                "bucket_id": bucket_id,
                "name": flow_name,
                "description": description,
                "type": flow_type,
                "created_timestamp": flow.get("createdTimestamp"),
                "version_count": flow.get("versionCount", 0)
            }

            self.logger.info("Created flow: %s (%s) in bucket %s", flow_name, flow_id, bucket_id)
            return result

        except Exception as exc:
            self.logger.error("Failed to create flow %s in bucket %s: %s", flow_name, bucket_id, exc)
            raise RegistryFlowManagementError(f"Failed to create flow: {exc}") from exc

    async def get_flow(self, bucket_id: str, flow_id: str) -> Dict[str, Any]:
        """Get flow details by bucket and flow ID."""
        try:
            flow = await self.registry.flows.get_flow(bucket_id, flow_id)

            result = {
                "flow_id": flow.get("identifier"),
                "bucket_id": flow.get("bucketIdentifier"),
                "name": flow.get("name"),
                "description": flow.get("description", ""),
                "type": flow.get("type"),
                "created_timestamp": flow.get("createdTimestamp"),
                "modified_timestamp": flow.get("modifiedTimestamp"),
                "version_count": flow.get("versionCount", 0),
                "permissions": flow.get("permissions", {}),
                "revision": flow.get("revision", {})
            }

            self.logger.debug("Retrieved flow: %s from bucket %s", flow_id, bucket_id)
            return result

        except Exception as exc:
            self.logger.error("Failed to get flow %s from bucket %s: %s", flow_id, bucket_id, exc)
            raise RegistryFlowManagementError(f"Failed to get flow: {exc}") from exc

    async def update_flow(
        self,
        bucket_id: str,
        flow_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update flow metadata."""
        try:
            # Get current flow details for revision
            current_flow = await self.registry.flows.get_flow(bucket_id, flow_id)
            revision = current_flow.get("revision", {})

            # Prepare update data
            update_data = {
                "identifier": flow_id,
                "name": name or current_flow.get("name"),
                "description": description or current_flow.get("description", ""),
                "bucketIdentifier": bucket_id,
                "type": current_flow.get("type"),
                "revision": revision
            }

            updated_flow = await self.registry.flows.update_flow(bucket_id, flow_id, update_data)

            result = {
                "success": True,
                "flow_id": flow_id,
                "bucket_id": bucket_id,
                "name": updated_flow.get("name"),
                "description": updated_flow.get("description", ""),
                "modified_timestamp": updated_flow.get("modifiedTimestamp")
            }

            self.logger.info("Updated flow: %s in bucket %s", flow_id, bucket_id)
            return result

        except Exception as exc:
            self.logger.error("Failed to update flow %s in bucket %s: %s", flow_id, bucket_id, exc)
            raise RegistryFlowManagementError(f"Failed to update flow: {exc}") from exc

    async def delete_flow(self, bucket_id: str, flow_id: str) -> Dict[str, Any]:
        """Delete a flow from the Registry."""
        try:
            # Get current flow for revision
            current_flow = await self.registry.flows.get_flow(bucket_id, flow_id)
            revision = current_flow.get("revision", {})

            await self.registry.flows.delete_flow(bucket_id, flow_id, revision)

            result = {
                "success": True,
                "flow_id": flow_id,
                "bucket_id": bucket_id,
                "message": "Flow deleted successfully"
            }

            self.logger.info("Deleted flow: %s from bucket %s", flow_id, bucket_id)
            return result

        except Exception as exc:
            self.logger.error("Failed to delete flow %s from bucket %s: %s", flow_id, bucket_id, exc)
            raise RegistryFlowManagementError(f"Failed to delete flow: {exc}") from exc

    async def list_flows_in_bucket(self, bucket_id: str) -> List[Dict[str, Any]]:
        """List all flows in a specific bucket."""
        try:
            flows = await self.registry.flows.list_flows_in_bucket(bucket_id)

            result = []
            for flow in flows:
                result.append({
                    "flow_id": flow.get("identifier"),
                    "bucket_id": flow.get("bucketIdentifier"),
                    "name": flow.get("name"),
                    "description": flow.get("description", ""),
                    "type": flow.get("type"),
                    "created_timestamp": flow.get("createdTimestamp"),
                    "modified_timestamp": flow.get("modifiedTimestamp"),
                    "version_count": flow.get("versionCount", 0)
                })

            self.logger.debug("Listed %d flows in bucket %s", len(result), bucket_id)
            return result

        except Exception as exc:
            self.logger.error("Failed to list flows in bucket %s: %s", bucket_id, exc)
            raise RegistryFlowManagementError(f"Failed to list flows in bucket: {exc}") from exc

    async def list_all_flows(self) -> List[Dict[str, Any]]:
        """List all flows across all buckets."""
        try:
            flows = await self.registry.flows.list_flows()

            result = []
            for flow in flows:
                result.append({
                    "flow_id": flow.get("identifier"),
                    "bucket_id": flow.get("bucketIdentifier"),
                    "name": flow.get("name"),
                    "description": flow.get("description", ""),
                    "type": flow.get("type"),
                    "created_timestamp": flow.get("createdTimestamp"),
                    "modified_timestamp": flow.get("modifiedTimestamp"),
                    "version_count": flow.get("versionCount", 0)
                })

            self.logger.debug("Listed %d flows across all buckets", len(result))
            return result

        except Exception as exc:
            self.logger.error("Failed to list all flows: %s", exc)
            raise RegistryFlowManagementError(f"Failed to list all flows: {exc}") from exc

    async def find_flow_by_name(self, bucket_id: str, flow_name: str) -> Optional[Dict[str, Any]]:
        """Find a flow by name within a bucket."""
        try:
            flows = await self.list_flows_in_bucket(bucket_id)

            for flow in flows:
                if flow.get("name") == flow_name:
                    return flow

            return None

        except Exception as exc:
            self.logger.error("Failed to find flow by name %s in bucket %s: %s", flow_name, bucket_id, exc)
            raise RegistryFlowManagementError(f"Failed to find flow by name: {exc}") from exc

    async def get_or_create_flow(
        self,
        bucket_id: str,
        flow_name: str,
        description: str = "",
        flow_type: str = "Flow"
    ) -> Dict[str, Any]:
        """Get an existing flow by name or create it if it doesn't exist."""
        try:
            # Try to find existing flow
            existing_flow = await self.find_flow_by_name(bucket_id, flow_name)

            if existing_flow:
                self.logger.debug("Found existing flow: %s in bucket %s", flow_name, bucket_id)
                return existing_flow

            # Create new flow if not found
            self.logger.info("Creating new flow: %s in bucket %s", flow_name, bucket_id)
            return await self.create_flow(
                bucket_id=bucket_id,
                flow_name=flow_name,
                description=description,
                flow_type=flow_type
            )

        except Exception as exc:
            self.logger.error("Failed to get or create flow %s in bucket %s: %s", flow_name, bucket_id, exc)
            raise RegistryFlowManagementError(f"Failed to get or create flow: {exc}") from exc

    async def check_flow_exists(self, bucket_id: str, flow_name: str) -> bool:
        """Check if a flow exists by name in a bucket."""
        try:
            flow = await self.find_flow_by_name(bucket_id, flow_name)
            return flow is not None

        except Exception as exc:
            self.logger.error("Failed to check if flow exists %s in bucket %s: %s", flow_name, bucket_id, exc)
            raise RegistryFlowManagementError(f"Failed to check flow existence: {exc}") from exc