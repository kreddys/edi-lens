"""NiFi version control service for Registry integration."""

from __future__ import annotations

from typing import Any, Dict, Optional

from ..clients.nifi_unified import NiFiUnifiedClient
from ..clients.registry_unified import RegistryUnifiedClient
from ..core.logging import get_logger, LoggerMixin

log = get_logger(__name__)


class NiFiVersionControlError(RuntimeError):
    """Raised when NiFi version control operations fail."""


class NiFiVersionControlService(LoggerMixin):
    """Service for managing NiFi version control with Registry."""

    def __init__(self, nifi_client: NiFiUnifiedClient, registry_client: RegistryUnifiedClient):
        self.nifi = nifi_client
        self.registry = registry_client
        self.logger.info("Initialized NiFi Version Control Service")

    async def upload_to_registry_with_version_control(
        self,
        process_group_id: str,
        bucket_id: str,
        flow_name: str,
        description: str = "",
        comments: str = "Initial version from NiFi deployment",
    ) -> Dict[str, Any]:
        """
        Upload deployed flow to Registry and establish version control link.
        """
        try:
            self.logger.info(
                "Starting Registry upload and version control for process group: %s", process_group_id
            )

            # Step 1: Ensure Registry client exists in NiFi
            registry_id = await self._ensure_registry_client()

            # Step 2: Create flow in Registry (this will be done by version control)
            # Step 3: Place process group under version control
            vc_result = await self.nifi.version_control.start_version_control(
                process_group_id=process_group_id,
                registry_id=registry_id,
                bucket_id=bucket_id,
                flow_name=flow_name,
                flow_description=description,
                comments=comments,
            )

            # Extract flow information from version control response
            vc_info = vc_result.get("versionControlInformation", {})
            flow_id = vc_info.get("flowId")
            version = vc_info.get("version", 1)

            self.logger.info(
                "Successfully uploaded flow '%s' (ID: %s, version: %d) and established version control",
                flow_name,
                flow_id,
                version,
            )

            return {
                "success": True,
                "flow_id": flow_id,
                "version": version,
                "registry_id": registry_id,
                "bucket_id": bucket_id,
                "process_group_id": process_group_id,
                "version_control_info": vc_info,
            }

        except Exception as exc:
            self.logger.error("Failed to upload flow to Registry and establish version control: %s", exc)
            return {
                "success": False,
                "error": {
                    "error_type": "VERSION_CONTROL_FAILED",
                    "user_message": f"Failed to upload to Registry: {exc}",
                    "action_required": "Check Registry connectivity and permissions",
                    "details": {"message": str(exc)},
                },
            }

    async def update_from_registry(self, process_group_id: str) -> Dict[str, Any]:
        """Update process group from latest version in Registry."""
        try:
            self.logger.info("Updating process group %s from Registry", process_group_id)

            result = await self.nifi.version_control.update_from_registry(process_group_id)

            self.logger.info("Successfully updated process group %s from Registry", process_group_id)
            return {
                "success": True,
                "process_group_id": process_group_id,
                "update_info": result,
            }

        except Exception as exc:
            self.logger.error("Failed to update process group %s from Registry: %s", process_group_id, exc)
            return {
                "success": False,
                "error": {
                    "error_type": "UPDATE_FROM_REGISTRY_FAILED",
                    "user_message": f"Failed to update from Registry: {exc}",
                    "action_required": "Check Registry connectivity and version control status",
                    "details": {"message": str(exc)},
                },
            }

    async def commit_local_changes(
        self, process_group_id: str, comments: str = "Updated flow"
    ) -> Dict[str, Any]:
        """Commit local changes to Registry."""
        try:
            self.logger.info("Committing local changes for process group: %s", process_group_id)

            result = await self.nifi.version_control.commit_local_changes(process_group_id, comments)

            self.logger.info("Successfully committed changes for process group: %s", process_group_id)
            return {
                "success": True,
                "process_group_id": process_group_id,
                "commit_info": result,
            }

        except Exception as exc:
            self.logger.error("Failed to commit changes for process group %s: %s", process_group_id, exc)
            return {
                "success": False,
                "error": {
                    "error_type": "COMMIT_FAILED",
                    "user_message": f"Failed to commit changes: {exc}",
                    "action_required": "Check Registry connectivity and version control status",
                    "details": {"message": str(exc)},
                },
            }

    async def revert_local_changes(self, process_group_id: str) -> Dict[str, Any]:
        """Revert local changes to Registry version."""
        try:
            self.logger.info("Reverting local changes for process group: %s", process_group_id)

            result = await self.nifi.version_control.revert_local_changes(process_group_id)

            self.logger.info("Successfully reverted changes for process group: %s", process_group_id)
            return {
                "success": True,
                "process_group_id": process_group_id,
                "revert_info": result,
            }

        except Exception as exc:
            self.logger.error("Failed to revert changes for process group %s: %s", process_group_id, exc)
            return {
                "success": False,
                "error": {
                    "error_type": "REVERT_FAILED",
                    "user_message": f"Failed to revert changes: {exc}",
                    "action_required": "Check Registry connectivity and version control status",
                    "details": {"message": str(exc)},
                },
            }

    async def stop_version_control(self, process_group_id: str) -> Dict[str, Any]:
        """Remove process group from version control."""
        try:
            self.logger.info("Stopping version control for process group: %s", process_group_id)

            result = await self.nifi.version_control.stop_version_control(process_group_id)

            self.logger.info("Successfully stopped version control for process group: %s", process_group_id)
            return {
                "success": True,
                "process_group_id": process_group_id,
                "stop_info": result,
            }

        except Exception as exc:
            self.logger.error("Failed to stop version control for process group %s: %s", process_group_id, exc)
            return {
                "success": False,
                "error": {
                    "error_type": "STOP_VERSION_CONTROL_FAILED",
                    "user_message": f"Failed to stop version control: {exc}",
                    "action_required": "Check NiFi connectivity and process group status",
                    "details": {"message": str(exc)},
                },
            }

    async def get_version_control_info(self, process_group_id: str) -> Dict[str, Any]:
        """Get version control information for a process group."""
        try:
            result = await self.nifi.version_control.get_version_control_info(process_group_id)
            return {
                "success": True,
                "version_control_info": result,
            }
        except Exception as exc:
            return {
                "success": False,
                "error": {
                    "error_type": "VERSION_CONTROL_INFO_FAILED",
                    "user_message": f"Failed to get version control info: {exc}",
                    "action_required": "Check process group version control status",
                    "details": {"message": str(exc)},
                },
            }

    async def get_local_modifications(self, process_group_id: str) -> Dict[str, Any]:
        """Get local modifications for a version controlled process group."""
        try:
            result = await self.nifi.version_control.get_local_modifications(process_group_id)
            return {
                "success": True,
                "local_modifications": result,
            }
        except Exception as exc:
            return {
                "success": False,
                "error": {
                    "error_type": "LOCAL_MODIFICATIONS_FAILED",
                    "user_message": f"Failed to get local modifications: {exc}",
                    "action_required": "Check process group version control status",
                    "details": {"message": str(exc)},
                },
            }

    async def _ensure_registry_client(self) -> str:
        """Ensure Registry client exists in NiFi and return its ID."""
        try:
            # Check if Registry client already exists
            registries = await self.nifi.version_control.list_registry_clients()

            for registry in registries:
                registry_url = registry.get("component", {}).get("properties", {}).get("url", "")
                # Check if this registry matches our Registry URL
                if (
                    self.registry.base.registry_url in registry_url
                    or registry_url in self.registry.base.registry_url
                ):
                    registry_id = registry.get("id")
                    self.logger.info("Found existing Registry client: %s", registry_id)
                    return registry_id

            # Create new Registry client if none exists
            self.logger.info("Creating new Registry client for %s", self.registry.base.registry_url)

            registry_result = await self.nifi.version_control.create_registry_client(
                name="EDI Lens Registry",
                url=self.registry.base.registry_url,
                description="Registry client for EDI Lens flows",
            )

            registry_id = registry_result.get("id")
            self.logger.info("Created Registry client: %s", registry_id)

            return registry_id

        except Exception as exc:
            raise NiFiVersionControlError(f"Failed to ensure Registry client: {exc}") from exc