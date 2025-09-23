"""NiFi flow management service - handles flow lifecycle operations."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..clients.nifi_unified import NiFiUnifiedClient
from ..core.logging import get_logger, LoggerMixin

log = get_logger(__name__)


class NiFiFlowManagementError(RuntimeError):
    """Raised when NiFi flow management operations fail."""


class NiFiFlowManagement(LoggerMixin):
    """Service for managing flow lifecycle in NiFi (start/stop/delete/status)."""

    def __init__(self, nifi_client: NiFiUnifiedClient):
        self.nifi = nifi_client
        self.logger.info("Initialized NiFi Flow Management service")

    async def start_flow(self, process_group_id: str) -> Dict[str, Any]:
        """Start all processors in a process group."""
        try:
            # Get all processors in the process group
            processors = await self._get_processors_in_group(process_group_id)

            started_count = 0
            failed_processors = []

            for processor in processors:
                processor_id = processor.get("id")
                processor_name = processor.get("component", {}).get("name", "Unknown")

                try:
                    # Start the processor
                    await self.nifi.processors.start_processor(processor_id)
                    started_count += 1
                    self.logger.debug("Started processor: %s", processor_name)
                except Exception as exc:
                    failed_processors.append({
                        "processor_id": processor_id,
                        "processor_name": processor_name,
                        "error": str(exc)
                    })
                    self.logger.warning("Failed to start processor %s: %s", processor_name, exc)

            success = len(failed_processors) == 0

            result = {
                "success": success,
                "process_group_id": process_group_id,
                "total_processors": len(processors),
                "started_processors": started_count,
                "failed_processors": failed_processors,
                "status": "running" if success else "partially_running"
            }

            if success:
                self.logger.info("Successfully started all processors in process group: %s", process_group_id)
            else:
                self.logger.warning("Partially started process group %s: %d/%d processors started",
                                  process_group_id, started_count, len(processors))

            return result

        except Exception as exc:
            self.logger.error("Failed to start flow in process group %s: %s", process_group_id, exc)
            raise NiFiFlowManagementError(f"Failed to start flow: {exc}") from exc

    async def stop_flow(self, process_group_id: str) -> Dict[str, Any]:
        """Stop all processors in a process group."""
        try:
            # Get all processors in the process group
            processors = await self._get_processors_in_group(process_group_id)

            stopped_count = 0
            failed_processors = []

            for processor in processors:
                processor_id = processor.get("id")
                processor_name = processor.get("component", {}).get("name", "Unknown")

                try:
                    # Stop the processor
                    await self.nifi.processors.stop_processor(processor_id)
                    stopped_count += 1
                    self.logger.debug("Stopped processor: %s", processor_name)
                except Exception as exc:
                    failed_processors.append({
                        "processor_id": processor_id,
                        "processor_name": processor_name,
                        "error": str(exc)
                    })
                    self.logger.warning("Failed to stop processor %s: %s", processor_name, exc)

            success = len(failed_processors) == 0

            result = {
                "success": success,
                "process_group_id": process_group_id,
                "total_processors": len(processors),
                "stopped_processors": stopped_count,
                "failed_processors": failed_processors,
                "status": "stopped" if success else "partially_stopped"
            }

            if success:
                self.logger.info("Successfully stopped all processors in process group: %s", process_group_id)
            else:
                self.logger.warning("Partially stopped process group %s: %d/%d processors stopped",
                                  process_group_id, stopped_count, len(processors))

            return result

        except Exception as exc:
            self.logger.error("Failed to stop flow in process group %s: %s", process_group_id, exc)
            raise NiFiFlowManagementError(f"Failed to stop flow: {exc}") from exc

    async def delete_flow(self, process_group_id: str, force: bool = False) -> Dict[str, Any]:
        """Delete a process group and all its components."""
        try:
            # First, stop all processors if not forced
            if not force:
                await self.stop_flow(process_group_id)

            # Delete the process group
            await self.nifi.process_groups.delete_process_group(process_group_id)

            result = {
                "success": True,
                "process_group_id": process_group_id,
                "message": "Process group deleted successfully"
            }

            self.logger.info("Successfully deleted process group: %s", process_group_id)
            return result

        except Exception as exc:
            self.logger.error("Failed to delete process group %s: %s", process_group_id, exc)
            raise NiFiFlowManagementError(f"Failed to delete flow: {exc}") from exc

    async def get_flow_status(self, process_group_id: str) -> Dict[str, Any]:
        """Get detailed status of a flow and its components."""
        try:
            # Get process group details
            process_group = await self.nifi.process_groups.get_process_group(process_group_id)

            # Get all processors in the process group
            processors = await self._get_processors_in_group(process_group_id)

            # Analyze processor states
            processor_states = {}
            running_count = 0
            stopped_count = 0
            invalid_count = 0

            for processor in processors:
                component = processor.get("component", {})
                processor_name = component.get("name", "Unknown")
                state = component.get("state", "UNKNOWN")
                validation_status = component.get("validationStatus", "UNKNOWN")

                processor_states[processor_name] = {
                    "state": state,
                    "validation_status": validation_status,
                    "processor_id": processor.get("id")
                }

                if state == "RUNNING":
                    running_count += 1
                elif state == "STOPPED":
                    stopped_count += 1

                if validation_status == "INVALID":
                    invalid_count += 1

            # Determine overall flow status
            total_processors = len(processors)
            if total_processors == 0:
                overall_status = "empty"
            elif running_count == total_processors:
                overall_status = "running"
            elif stopped_count == total_processors:
                overall_status = "stopped"
            elif running_count > 0:
                overall_status = "partially_running"
            else:
                overall_status = "unknown"

            result = {
                "process_group_id": process_group_id,
                "process_group_name": process_group.get("component", {}).get("name", "Unknown"),
                "overall_status": overall_status,
                "total_processors": total_processors,
                "running_processors": running_count,
                "stopped_processors": stopped_count,
                "invalid_processors": invalid_count,
                "processor_details": processor_states,
                "timestamp": process_group.get("component", {}).get("versionedComponentId")
            }

            self.logger.debug("Retrieved status for process group: %s", process_group_id)
            return result

        except Exception as exc:
            self.logger.error("Failed to get status for process group %s: %s", process_group_id, exc)
            raise NiFiFlowManagementError(f"Failed to get flow status: {exc}") from exc

    async def list_flows(self, parent_group_id: str = "root") -> List[Dict[str, Any]]:
        """List all flows (process groups) under a parent group."""
        try:
            # Get process groups under the parent
            process_groups_response = await self.nifi.process_groups.get_process_groups(parent_group_id)
            process_groups = process_groups_response.get("processGroups", [])

            flows = []
            for pg in process_groups:
                component = pg.get("component", {})
                flows.append({
                    "process_group_id": pg.get("id"),
                    "name": component.get("name"),
                    "state": component.get("state"),
                    "position": component.get("position"),
                    "created": pg.get("status", {}).get("aggregateSnapshot", {}).get("timestamp"),
                    "processor_count": pg.get("status", {}).get("aggregateSnapshot", {}).get("activeThreadCount", 0)
                })

            self.logger.debug("Listed %d flows under parent group: %s", len(flows), parent_group_id)
            return flows

        except Exception as exc:
            self.logger.error("Failed to list flows under parent group %s: %s", parent_group_id, exc)
            raise NiFiFlowManagementError(f"Failed to list flows: {exc}") from exc

    async def _get_processors_in_group(self, process_group_id: str) -> List[Dict[str, Any]]:
        """Get all processors in a process group."""
        try:
            processors_response = await self.nifi.process_groups.get_processors(process_group_id)
            return processors_response.get("processors", [])
        except Exception as exc:
            self.logger.error("Failed to get processors for process group %s: %s", process_group_id, exc)
            raise NiFiFlowManagementError(f"Failed to get processors: {exc}") from exc