"""NiFi client for parameter context operations."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..core.logging import get_logger, LoggerMixin
from .nifi_base import NiFiBaseClient

log = get_logger(__name__)


class NiFiParameterContextClient(LoggerMixin):
    """Client for NiFi parameter context operations."""

    def __init__(self, base_client: NiFiBaseClient):
        self.base = base_client
        self.logger.info("Initialized NiFi Parameter Context client")

    async def create_parameter_context(
        self,
        name: str,
        description: str = "",
        parameters: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Create a new parameter context."""
        if parameters is None:
            parameters = []

        payload = {
            "revision": {"version": 0},
            "component": {
                "name": name,
                "description": description,
                "parameters": parameters,
            },
        }

        self.logger.debug("Creating parameter context: %s", name)
        result = await self.base.post("/parameter-contexts", payload)

        context_id = result.get("id")
        self.logger.info("Created parameter context '%s' with ID: %s", name, context_id)
        return result

    async def get_parameter_context(self, context_id: str) -> Dict[str, Any]:
        """Get parameter context details."""
        self.logger.debug("Getting parameter context: %s", context_id)
        return await self.base.get(f"/parameter-contexts/{context_id}")

    async def update_parameter_context(
        self,
        context_id: str,
        parameters: Dict[str, str],
        revision: int = 0,
    ) -> Dict[str, Any]:
        """Update parameter context with new parameter values."""
        # Convert parameters dict to NiFi parameter format
        param_list = [
            {
                "parameter": {
                    "name": name,
                    "value": value,
                    "sensitive": False,
                }
            }
            for name, value in parameters.items()
        ]

        payload = {
            "revision": {"version": revision},
            "component": {
                "id": context_id,
                "parameters": param_list,
            },
        }

        self.logger.debug("Updating parameter context: %s", context_id)
        result = await self.base.put(f"/parameter-contexts/{context_id}", payload)
        self.logger.info("Updated parameter context: %s", context_id)
        return result

    async def delete_parameter_context(
        self,
        context_id: str,
        revision: Optional[int] = None,
        client_id: Optional[str] = None,
    ) -> None:
        """Delete a parameter context."""

        if revision is None or client_id is None:
            current_context = await self.get_parameter_context(context_id)
            current_revision = current_context.get("revision", {})
            if revision is None:
                revision = current_revision.get("version", 0)
            if client_id is None:
                client_id = current_revision.get("clientId")

        params = {"version": revision}
        if client_id:
            params["clientId"] = client_id

        self.logger.debug(
            "Deleting parameter context: %s (revision: %s, clientId: %s)",
            context_id,
            revision,
            client_id,
        )
        await self.base.delete(f"/parameter-contexts/{context_id}", params=params)
        self.logger.info("Deleted parameter context: %s", context_id)

    async def list_parameter_contexts(self) -> List[Dict[str, Any]]:
        """List all parameter contexts."""
        self.logger.debug("Listing parameter contexts")
        result = await self.base.get("/flow/parameter-contexts")
        return result.get("parameterContexts", [])

    async def get_parameter_context_parameters(self, context_id: str) -> Dict[str, str]:
        """Get parameters from a parameter context as a simple dict."""
        context = await self.get_parameter_context(context_id)
        parameters = {}

        for param_item in context.get("component", {}).get("parameters", []):
            param = param_item.get("parameter", {})
            name = param.get("name")
            value = param.get("value")
            if name and value is not None:
                parameters[name] = value

        self.logger.debug("Retrieved %d parameters from context %s", len(parameters), context_id)
        return parameters

    async def add_parameter_to_context(
        self,
        context_id: str,
        parameter_name: str,
        parameter_value: str,
        sensitive: bool = False,
    ) -> Dict[str, Any]:
        """Add a single parameter to an existing parameter context."""
        # Get current context
        current_context = await self.get_parameter_context(context_id)
        current_params = current_context.get("component", {}).get("parameters", [])
        revision = current_context.get("revision", {}).get("version", 0)

        # Add new parameter
        new_param = {
            "parameter": {
                "name": parameter_name,
                "value": parameter_value,
                "sensitive": sensitive,
            }
        }

        # Check if parameter already exists and update it
        param_exists = False
        for i, param_item in enumerate(current_params):
            if param_item.get("parameter", {}).get("name") == parameter_name:
                current_params[i] = new_param
                param_exists = True
                break

        if not param_exists:
            current_params.append(new_param)

        payload = {
            "revision": {"version": revision},
            "component": {
                "id": context_id,
                "parameters": current_params,
            },
        }

        self.logger.debug("Adding parameter '%s' to context %s", parameter_name, context_id)
        result = await self.base.put(f"/parameter-contexts/{context_id}", payload)
        self.logger.info("Added parameter '%s' to context %s", parameter_name, context_id)
        return result
