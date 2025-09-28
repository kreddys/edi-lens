"""NiFi client for parameter context operations."""

from __future__ import annotations

import asyncio
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
        revision: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Update parameter context with new parameters using the proper update request mechanism."""
        # Get current parameter context to merge with existing parameters
        current_context = await self.get_parameter_context(context_id)
        if revision is None:
            revision = current_context.get("revision", {}).get("version", 0)

        # Get existing parameters
        existing_params = current_context.get("component", {}).get("parameters", [])
        param_map = {
            param.get("parameter", {}).get("name"): param.get("parameter", {})
            for param in existing_params
        }

        # Update with new parameters
        for name, value in parameters.items():
            if name in param_map:
                # Update existing parameter
                param_map[name]["value"] = str(value)
            else:
                # Add new parameter
                param_map[name] = {
                    "name": name,
                    "value": str(value),
                    "sensitive": False,
                    "description": f"Parameter {name}"
                }

        # Convert back to parameter list format - ONLY send essential fields
        param_list = [
            {
                "parameter": {
                    "name": param_info["name"],
                    "value": param_info["value"],
                    "sensitive": param_info.get("sensitive", False),
                    "description": param_info.get("description", "")
                }
            }
            for param_info in param_map.values()
        ]

        # Create the parameter context entity for the update request
        parameter_context_entity = {
            "revision": {"version": revision},
            "component": {
                "id": context_id,
                "name": current_context.get("component", {}).get("name", ""),
                "description": current_context.get("component", {}).get("description", ""),
                "parameters": param_list,
            },
        }

        # Submit update request
        self.logger.debug("Submitting parameter context update request for %s", context_id)
        update_request_response = await self.base.post(
            f"/parameter-contexts/{context_id}/update-requests", 
            json_data=parameter_context_entity
        )
        
        request_id = update_request_response.get("request", {}).get("requestId")
        if not request_id:
            raise ValueError("Update request did not return a request ID")

        # Poll for completion
        max_attempts = 30  # Wait up to 30 seconds
        attempt = 0
        
        while attempt < max_attempts:
            status_response = await self.base.get(f"/parameter-contexts/{context_id}/update-requests/{request_id}")
            request_info = status_response.get("request", {})
            
            if request_info.get("complete"):
                # Clean up the update request
                await self.base.delete(f"/parameter-contexts/{context_id}/update-requests/{request_id}")
                
                if request_info.get("failureReason"):
                    raise RuntimeError(f"Parameter context update failed: {request_info.get('failureReason')}")
                
                self.logger.info("Parameter context update completed successfully for %s", context_id)
                return status_response
                
            attempt += 1
            await asyncio.sleep(1)  # Wait 1 second between polls

        # If we get here, the update didn't complete in time
        raise TimeoutError(f"Parameter context update timed out after {max_attempts} seconds")

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
