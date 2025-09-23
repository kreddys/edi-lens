"""NiFi parameter management service - handles parameter contexts and parameters."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from ..clients.nifi_unified import NiFiUnifiedClient
from ..core.logging import get_logger, LoggerMixin

log = get_logger(__name__)


class NiFiParameterManagementError(RuntimeError):
    """Raised when NiFi parameter management operations fail."""


class NiFiParameterManagement(LoggerMixin):
    """Service for managing parameter contexts and parameters in NiFi."""

    def __init__(self, nifi_client: NiFiUnifiedClient):
        self.nifi = nifi_client
        self.logger.info("Initialized NiFi Parameter Management service")

    async def create_parameter_context(
        self,
        name: str,
        description: str = "",
        parameters: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Create a new parameter context with optional parameters."""
        parameters = parameters or {}

        try:
            # Convert parameters to NiFi format
            param_list = [
                {
                    "parameter": {
                        "name": param_name,
                        "value": str(param_value),
                        "sensitive": False,
                    }
                }
                for param_name, param_value in parameters.items()
            ]

            # Create parameter context
            param_context = await self.nifi.parameter_contexts.create_parameter_context(
                name=name,
                description=description,
                parameters=param_list,
            )

            parameter_context_id = param_context.get("id")

            result = {
                "success": True,
                "parameter_context_id": parameter_context_id,
                "name": name,
                "parameter_count": len(parameters),
                "parameters": list(parameters.keys())
            }

            self.logger.info("Created parameter context: %s (%s)", name, parameter_context_id)
            return result

        except Exception as exc:
            self.logger.error("Failed to create parameter context %s: %s", name, exc)
            raise NiFiParameterManagementError(f"Failed to create parameter context: {exc}") from exc

    async def update_parameter_context(
        self,
        parameter_context_id: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update parameters in an existing parameter context."""
        try:
            # Get current parameter context
            current_context = await self.nifi.parameter_contexts.get_parameter_context(parameter_context_id)
            current_revision = current_context.get("revision", {}).get("version", 0)

            # Convert parameters to NiFi format
            param_list = [
                {
                    "parameter": {
                        "name": param_name,
                        "value": str(param_value),
                        "sensitive": False,
                    }
                }
                for param_name, param_value in parameters.items()
            ]

            # Update parameter context
            updated_context = await self.nifi.parameter_contexts.update_parameter_context(
                parameter_context_id=parameter_context_id,
                revision=current_revision,
                parameters=param_list,
            )

            result = {
                "success": True,
                "parameter_context_id": parameter_context_id,
                "updated_parameter_count": len(parameters),
                "parameters": list(parameters.keys()),
                "revision": updated_context.get("revision", {}).get("version", 0)
            }

            self.logger.info("Updated parameter context: %s with %d parameters", parameter_context_id, len(parameters))
            return result

        except Exception as exc:
            self.logger.error("Failed to update parameter context %s: %s", parameter_context_id, exc)
            raise NiFiParameterManagementError(f"Failed to update parameter context: {exc}") from exc

    async def delete_parameter_context(self, parameter_context_id: str) -> Dict[str, Any]:
        """Delete a parameter context."""
        try:
            await self.nifi.parameter_contexts.delete_parameter_context(parameter_context_id)

            result = {
                "success": True,
                "parameter_context_id": parameter_context_id,
                "message": "Parameter context deleted successfully"
            }

            self.logger.info("Deleted parameter context: %s", parameter_context_id)
            return result

        except Exception as exc:
            self.logger.error("Failed to delete parameter context %s: %s", parameter_context_id, exc)
            raise NiFiParameterManagementError(f"Failed to delete parameter context: {exc}") from exc

    async def get_parameter_context(self, parameter_context_id: str) -> Dict[str, Any]:
        """Get parameter context details and all its parameters."""
        try:
            param_context = await self.nifi.parameter_contexts.get_parameter_context(parameter_context_id)

            component = param_context.get("component", {})
            parameters = {}

            # Extract parameters from response
            for param_item in component.get("parameters", []):
                param = param_item.get("parameter", {})
                param_name = param.get("name")
                param_value = param.get("value")
                param_sensitive = param.get("sensitive", False)

                if param_name:
                    parameters[param_name] = {
                        "value": param_value if not param_sensitive else "[SENSITIVE]",
                        "sensitive": param_sensitive
                    }

            result = {
                "parameter_context_id": parameter_context_id,
                "name": component.get("name"),
                "description": component.get("description", ""),
                "parameter_count": len(parameters),
                "parameters": parameters,
                "revision": param_context.get("revision", {}).get("version", 0)
            }

            self.logger.debug("Retrieved parameter context: %s", parameter_context_id)
            return result

        except Exception as exc:
            self.logger.error("Failed to get parameter context %s: %s", parameter_context_id, exc)
            raise NiFiParameterManagementError(f"Failed to get parameter context: {exc}") from exc

    async def list_parameter_contexts(self) -> List[Dict[str, Any]]:
        """List all parameter contexts in NiFi."""
        try:
            contexts_response = await self.nifi.parameter_contexts.list_parameter_contexts()
            contexts = contexts_response.get("parameterContexts", [])

            result = []
            for context in contexts:
                component = context.get("component", {})
                result.append({
                    "parameter_context_id": context.get("id"),
                    "name": component.get("name"),
                    "description": component.get("description", ""),
                    "parameter_count": len(component.get("parameters", [])),
                    "revision": context.get("revision", {}).get("version", 0)
                })

            self.logger.debug("Listed %d parameter contexts", len(result))
            return result

        except Exception as exc:
            self.logger.error("Failed to list parameter contexts: %s", exc)
            raise NiFiParameterManagementError(f"Failed to list parameter contexts: {exc}") from exc

    async def assign_parameter_context_to_process_group(
        self,
        process_group_id: str,
        parameter_context_id: str
    ) -> Dict[str, Any]:
        """Assign a parameter context to a process group."""
        try:
            await self.nifi.process_groups.set_parameter_context(
                process_group_id=process_group_id,
                parameter_context_id=parameter_context_id,
            )

            result = {
                "success": True,
                "process_group_id": process_group_id,
                "parameter_context_id": parameter_context_id,
                "message": "Parameter context assigned to process group"
            }

            self.logger.info("Assigned parameter context %s to process group %s",
                           parameter_context_id, process_group_id)
            return result

        except Exception as exc:
            self.logger.error("Failed to assign parameter context %s to process group %s: %s",
                            parameter_context_id, process_group_id, exc)
            raise NiFiParameterManagementError(f"Failed to assign parameter context: {exc}") from exc

    async def get_process_group_parameter_context(self, process_group_id: str) -> Optional[Dict[str, Any]]:
        """Get the parameter context assigned to a process group."""
        try:
            process_group = await self.nifi.process_groups.get_process_group(process_group_id)
            param_context_ref = process_group.get("component", {}).get("parameterContext")

            if not param_context_ref:
                return None

            parameter_context_id = param_context_ref.get("id")
            if not parameter_context_id:
                return None

            # Get full parameter context details
            return await self.get_parameter_context(parameter_context_id)

        except Exception as exc:
            self.logger.error("Failed to get parameter context for process group %s: %s", process_group_id, exc)
            raise NiFiParameterManagementError(f"Failed to get process group parameter context: {exc}") from exc

    async def create_temporary_parameter_context(
        self,
        base_name: str,
        parameters: Dict[str, Any]
    ) -> str:
        """Create a temporary parameter context with a unique name."""
        timestamp = int(time.time())
        temp_name = f"temp-{base_name}-{timestamp}"

        result = await self.create_parameter_context(
            name=temp_name,
            description=f"Temporary parameter context for {base_name}",
            parameters=parameters
        )

        return result["parameter_context_id"]