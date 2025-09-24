"""Integration bridge service - handles NiFi ↔ Registry integration operations."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from ..clients.nifi_unified import NiFiUnifiedClient
from ..clients.registry_unified import RegistryUnifiedClient
from ..core.logging import get_logger, LoggerMixin

log = get_logger(__name__)


class IntegrationBridgeError(RuntimeError):
    """Raised when integration bridge operations fail."""


class IntegrationBridge(LoggerMixin):
    """Service for handling integration between NiFi and Registry."""

    def __init__(self, nifi_client: NiFiUnifiedClient, registry_client: RegistryUnifiedClient):
        self.nifi = nifi_client
        self.registry = registry_client
        self.logger.info("Initialized Integration Bridge service")

    async def ensure_registry_client_available(self) -> str:
        """Ensure NiFi has a Registry client configured for version control operations."""
        try:
            # Try to find existing registry client by URL
            registries = await self.nifi.version_control.list_registry_clients()
            registry_url = self.registry.base.registry_url
            
            # Look for existing client with matching URL
            for registry in registries:
                component = registry.get("component", {})
                properties = component.get("properties", {})
                if properties.get("url") == registry_url:
                    registry_id = registry.get("id") or component.get("id")
                    if registry_id:
                        self.logger.debug("Found existing registry client: %s", registry_id)
                        return registry_id
            
            # Create new registry client if none found
            self.logger.info("Creating new NiFi Registry client for: %s", registry_url)
            registry_entity = await self.nifi.version_control.create_registry_client(
                name="edi-lens-registry",
                url=registry_url,
                description="Auto-created Registry client for EDI Lens integration"
            )
            
            registry_id = registry_entity.get("id")
            self.logger.info("Created NiFi Registry client: %s", registry_id)
            return registry_id
            
        except Exception as exc:
            self.logger.error("Failed to ensure registry client is available: %s", exc)
            raise IntegrationBridgeError(f"Failed to ensure registry client: {exc}") from exc

    async def upload_flow_to_registry(
        self,
        process_group_id: str,
        bucket_id: str,
        flow_name: str,
        comments: str = "",
        flow_description: str = ""
    ) -> Dict[str, Any]:
        """Upload a NiFi process group to Registry as a versioned flow."""
        try:
            # Get the process group snapshot from NiFi
            process_group_snapshot = await self.nifi.version_control.export_process_group(
                process_group_id
            )

            # Ensure we have a flow in the Registry
            from .registry_flow_management import RegistryFlowManagement
            flow_mgmt = RegistryFlowManagement(self.registry)

            flow_info = await flow_mgmt.get_or_create_flow(
                bucket_id=bucket_id,
                flow_name=flow_name,
                description=flow_description
            )

            flow_id = flow_info.get("flow_id")

            # Create a new version in Registry
            from .registry_version_management import RegistryVersionManagement
            version_mgmt = RegistryVersionManagement(self.registry)

            version_result = await version_mgmt.create_flow_version(
                bucket_id=bucket_id,
                flow_id=flow_id,
                flow_contents=process_group_snapshot,
                comments=comments
            )

            # Link the process group to version control after successful upload
            registry_client_id = await self.ensure_registry_client_available()
            
            await self.nifi.version_control.link_process_group_to_registry(
                process_group_id=process_group_id,
                bucket_id=bucket_id,
                flow_id=flow_id,
                version=version_result.get("version"),
                registry_id=registry_client_id,
            )

            result = {
                "success": True,
                "process_group_id": process_group_id,
                "bucket_id": bucket_id,
                "flow_id": flow_id,
                "flow_name": flow_name,
                "version": version_result.get("version"),
                "comments": comments,
                "created_timestamp": version_result.get("created_timestamp"),
                "version_control_linked": True,
                "upload_summary": {
                    "processor_count": len(process_group_snapshot.get("processors", [])),
                    "connection_count": len(process_group_snapshot.get("connections", [])),
                }
            }

            self.logger.info("Uploaded flow %s (process group %s) to Registry as version %d and linked to version control",
                           flow_name, process_group_id, version_result.get("version"))
            return result

        except Exception as exc:
            self.logger.error("Failed to upload process group %s to Registry: %s", process_group_id, exc)
            raise IntegrationBridgeError(f"Failed to upload flow to Registry: {exc}") from exc

    async def import_flow_from_registry(
        self,
        bucket_id: str,
        flow_id: str,
        version: Optional[int] = None,
        parent_group_id: str = "root",
        flow_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Import a versioned flow from Registry into NiFi."""
        try:
            # Get flow version from Registry
            from .registry_version_management import RegistryVersionManagement
            version_mgmt = RegistryVersionManagement(self.registry)

            if version:
                flow_version = await version_mgmt.get_flow_version(bucket_id, flow_id, version)
            else:
                flow_version = await version_mgmt.get_latest_flow_version(bucket_id, flow_id)

            flow_contents = flow_version.get("flow_contents", {})
            imported_version = flow_version.get("version")

            # Deploy the flow to NiFi
            from .nifi_flow_deployment import NiFiFlowDeployment
            deployment_service = NiFiFlowDeployment(self.nifi)

            deployment_name = flow_name or f"registry-flow-{flow_id}-v{imported_version}"

            deployment_result = await deployment_service.deploy_flow(
                flow_definition=flow_contents,
                flow_name=deployment_name,
                parent_group_id=parent_group_id
            )

            if deployment_result.get("success"):
                # Ensure Registry client is available before linking
                registry_client_id = await self.ensure_registry_client_available()
                
                # Link the process group to Registry for version control
                process_group_id = deployment_result.get("process_group_id")

                await self.nifi.version_control.link_process_group_to_registry(
                    process_group_id=process_group_id,
                    bucket_id=bucket_id,
                    flow_id=flow_id,
                    version=imported_version,
                    registry_id=registry_client_id,
                )

            result = {
                "success": deployment_result.get("success"),
                "bucket_id": bucket_id,
                "flow_id": flow_id,
                "imported_version": imported_version,
                "process_group_id": deployment_result.get("process_group_id"),
                "deployment_summary": deployment_result.get("summary", {}),
                "deployment_failures": deployment_result.get("failures", []),
                "version_control_linked": deployment_result.get("success")
            }

            if deployment_result.get("success"):
                self.logger.info("Imported flow %s version %d from Registry to NiFi process group %s",
                               flow_id, imported_version, process_group_id)
            else:
                self.logger.warning("Flow import partially failed with %d errors",
                                  len(deployment_result.get("failures", [])))

            return result

        except Exception as exc:
            self.logger.error("Failed to import flow %s from Registry: %s", flow_id, exc)
            raise IntegrationBridgeError(f"Failed to import flow from Registry: {exc}") from exc

    async def sync_flow_with_registry(
        self,
        process_group_id: str,
        action: str = "pull"
    ) -> Dict[str, Any]:
        """Sync a NiFi process group with its Registry version (pull/push)."""
        try:
            # Get current version control information
            version_info = await self.nifi.version_control.get_version_control_info(
                process_group_id
            )

            if not version_info:
                raise IntegrationBridgeError("Process group is not under version control")

            bucket_id = version_info.get("bucketId")
            flow_id = version_info.get("flowId")
            current_version = version_info.get("version")

            if action == "pull":
                # Pull latest changes from Registry
                from .registry_version_management import RegistryVersionManagement
                version_mgmt = RegistryVersionManagement(self.registry)

                latest_version = await version_mgmt.get_latest_flow_version(bucket_id, flow_id)
                latest_version_number = latest_version.get("version")

                if latest_version_number > current_version:
                    # Update process group to latest version
                    await self.nifi.version_control.update_process_group_version(
                        process_group_id=process_group_id,
                        version=latest_version_number
                    )

                    result = {
                        "success": True,
                        "action": "pull",
                        "process_group_id": process_group_id,
                        "previous_version": current_version,
                        "new_version": latest_version_number,
                        "message": f"Updated to version {latest_version_number}"
                    }
                else:
                    result = {
                        "success": True,
                        "action": "pull",
                        "process_group_id": process_group_id,
                        "current_version": current_version,
                        "message": "Already at latest version"
                    }

            elif action == "push":
                # Push local changes to Registry
                process_group_snapshot = await self.nifi.version_control.export_process_group(
                    process_group_id
                )

                from .registry_version_management import RegistryVersionManagement
                version_mgmt = RegistryVersionManagement(self.registry)

                new_version = await version_mgmt.create_flow_version(
                    bucket_id=bucket_id,
                    flow_id=flow_id,
                    flow_contents=process_group_snapshot,
                    comments="Synced from NiFi"
                )

                new_version_number = new_version.get("version")

                # Update process group to track new version
                await self.nifi.version_control.update_process_group_version(
                    process_group_id=process_group_id,
                    version=new_version_number
                )

                result = {
                    "success": True,
                    "action": "push",
                    "process_group_id": process_group_id,
                    "previous_version": current_version,
                    "new_version": new_version_number,
                    "message": f"Created version {new_version_number}"
                }

            else:
                raise IntegrationBridgeError(f"Invalid sync action: {action}")

            self.logger.info("Synced process group %s with Registry (%s): %s",
                           process_group_id, action, result.get("message"))
            return result

        except Exception as exc:
            self.logger.error("Failed to sync process group %s with Registry: %s", process_group_id, exc)
            raise IntegrationBridgeError(f"Failed to sync with Registry: {exc}") from exc

    async def compare_with_registry(
        self,
        process_group_id: str
    ) -> Dict[str, Any]:
        """Compare a NiFi process group with its Registry version."""
        try:
            # Get current version control information
            version_info = await self.nifi.version_control.get_version_control_info(
                process_group_id
            )

            if not version_info:
                raise IntegrationBridgeError("Process group is not under version control")

            bucket_id = version_info.get("bucketId")
            flow_id = version_info.get("flowId")
            current_version = version_info.get("version")

            # Get current process group snapshot
            current_snapshot = await self.nifi.version_control.export_process_group(
                process_group_id
            )

            # Get Registry version
            from .registry_version_management import RegistryVersionManagement
            version_mgmt = RegistryVersionManagement(self.registry)

            registry_version = await version_mgmt.get_flow_version(bucket_id, flow_id, current_version)
            registry_contents = registry_version.get("flow_contents", {})

            # Get latest version info
            latest_version = await version_mgmt.get_latest_flow_version(bucket_id, flow_id)
            latest_version_number = latest_version.get("version")

            # Basic comparison
            differences = {
                "processor_count_local": len(current_snapshot.get("processors", [])),
                "processor_count_registry": len(registry_contents.get("processors", [])),
                "connection_count_local": len(current_snapshot.get("connections", [])),
                "connection_count_registry": len(registry_contents.get("connections", [])),
                "contents_match": current_snapshot == registry_contents
            }

            result = {
                "process_group_id": process_group_id,
                "bucket_id": bucket_id,
                "flow_id": flow_id,
                "current_version": current_version,
                "latest_version": latest_version_number,
                "is_latest": current_version == latest_version_number,
                "has_local_changes": not differences["contents_match"],
                "differences": differences,
                "registry_version_metadata": {
                    "comments": registry_version.get("comments", ""),
                    "created_timestamp": registry_version.get("created_timestamp"),
                    "author": registry_version.get("author")
                }
            }

            self.logger.debug("Compared process group %s with Registry version %d",
                            process_group_id, current_version)
            return result

        except Exception as exc:
            self.logger.error("Failed to compare process group %s with Registry: %s", process_group_id, exc)
            raise IntegrationBridgeError(f"Failed to compare with Registry: {exc}") from exc

    async def disconnect_from_registry(
        self,
        process_group_id: str
    ) -> Dict[str, Any]:
        """Disconnect a process group from Registry version control."""
        try:
            await self.nifi.version_control.stop_version_control(process_group_id)

            result = {
                "success": True,
                "process_group_id": process_group_id,
                "message": "Process group disconnected from Registry version control"
            }

            self.logger.info("Disconnected process group %s from Registry version control", process_group_id)
            return result

        except Exception as exc:
            self.logger.error("Failed to disconnect process group %s from Registry: %s", process_group_id, exc)
            raise IntegrationBridgeError(f"Failed to disconnect from Registry: {exc}") from exc