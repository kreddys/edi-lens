"""
NiFi API Client for EDI Lens.

This client provides integration with Apache NiFi for managing
running instances of workflows as process groups.
"""

import aiohttp
import json
from typing import Optional, List, Dict, Any, Union
from urllib.parse import urljoin


class NiFiAPIClient:
    """Client for NiFi REST API integration."""

    def __init__(self, nifi_url: str, auth_token: Optional[str] = None):
        self.nifi_url = nifi_url.rstrip('/')
        self.auth_token = auth_token
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        headers = {'Content-Type': 'application/json'}
        if self.auth_token:
            headers['Authorization'] = f'Bearer {self.auth_token}'
        
        self.session = aiohttp.ClientSession(
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=30)
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    # --- Process Groups ---

    async def create_process_group(
        self,
        parent_group_id: str,
        name: str,
        position: Dict[str, int],
        template_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new process group."""
        process_group_data = {
            "revision": {"version": 0},
            "component": {
                "name": name,
                "position": position,
                "parentGroupId": parent_group_id
            }
        }
        
        if template_id:
            process_group_data["component"]["templateId"] = template_id
        
        async with self.session.post(
            f"{self.nifi_url}/nifi-api/process-groups/{parent_group_id}/process-groups",
            json=process_group_data
        ) as response:
            response.raise_for_status()
            return await response.json()

    async def get_process_group(self, process_group_id: str) -> Dict[str, Any]:
        """Get process group details by ID."""
        async with self.session.get(
            f"{self.nifi_url}/nifi-api/process-groups/{process_group_id}"
        ) as response:
            response.raise_for_status()
            return await response.json()

    async def update_process_group(
        self,
        process_group_id: str,
        name: Optional[str] = None,
        position: Optional[Dict[str, int]] = None,
        version: int = 0
    ) -> Dict[str, Any]:
        """Update process group properties."""
        # First get current state
        current = await self.get_process_group(process_group_id)
        
        update_data = {
            "revision": {"version": version},
            "component": {
                "id": process_group_id
            }
        }
        
        if name:
            update_data["component"]["name"] = name
        if position:
            update_data["component"]["position"] = position
            
        async with self.session.put(
            f"{self.nifi_url}/nifi-api/process-groups/{process_group_id}",
            json=update_data
        ) as response:
            response.raise_for_status()
            return await response.json()

    async def delete_process_group(
        self,
        process_group_id: str,
        version: int = 0
    ) -> bool:
        """Delete a process group."""
        async with self.session.delete(
            f"{self.nifi_url}/nifi-api/process-groups/{process_group_id}",
            params={"version": version}
        ) as response:
            response.raise_for_status()
            return response.status == 200

    async def start_process_group(self, process_group_id: str) -> Dict[str, Any]:
        """Start a process group."""
        async with self.session.put(
            f"{self.nifi_url}/nifi-api/process-groups/{process_group_id}/state",
            json={"state": "RUNNING"}
        ) as response:
            response.raise_for_status()
            return await response.json()

    async def stop_process_group(self, process_group_id: str) -> Dict[str, Any]:
        """Stop a process group."""
        async with self.session.put(
            f"{self.nifi_url}/nifi-api/process-groups/{process_group_id}/state",
            json={"state": "STOPPED"}
        ) as response:
            response.raise_for_status()
            return await response.json()

    # --- Parameter Contexts ---

    async def create_parameter_context(
        self,
        name: str,
        description: str = "",
        parameters: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Create a new parameter context."""
        param_context_data = {
            "revision": {"version": 0},
            "component": {
                "name": name,
                "description": description,
                "parameters": parameters or []
            }
        }
        
        async with self.session.post(
            f"{self.nifi_url}/nifi-api/parameter-contexts",
            json=param_context_data
        ) as response:
            response.raise_for_status()
            return await response.json()

    async def get_parameter_context(self, context_id: str) -> Dict[str, Any]:
        """Get parameter context by ID."""
        async with self.session.get(
            f"{self.nifi_url}/nifi-api/parameter-contexts/{context_id}"
        ) as response:
            response.raise_for_status()
            return await response.json()

    async def update_parameter_context(
        self,
        context_id: str,
        parameters: List[Dict[str, Any]],
        version: int = 0
    ) -> Dict[str, Any]:
        """Update parameter context with new parameters."""
        update_data = {
            "revision": {"version": version},
            "component": {
                "id": context_id,
                "parameters": parameters
            }
        }
        
        async with self.session.put(
            f"{self.nifi_url}/nifi-api/parameter-contexts/{context_id}",
            json=update_data
        ) as response:
            response.raise_for_status()
            return await response.json()

    # --- Templates ---

    async def list_templates(self) -> List[Dict[str, Any]]:
        """List all available templates."""
        async with self.session.get(f"{self.nifi_url}/nifi-api/templates") as response:
            response.raise_for_status()
            data = await response.json()
            return data.get("templates", [])

    async def instantiate_template(
        self,
        parent_group_id: str,
        template_id: str,
        position: Dict[str, int]
    ) -> Dict[str, Any]:
        """Instantiate a template in a process group."""
        template_data = {
            "originX": position["x"],
            "originY": position["y"],
            "templateId": template_id
        }
        
        async with self.session.post(
            f"{self.nifi_url}/nifi-api/process-groups/{parent_group_id}/template-instance",
            json=template_data
        ) as response:
            response.raise_for_status()
            return await response.json()

    # --- Controller Services ---

    async def create_controller_service(
        self,
        parent_group_id: str,
        service_type: str,
        name: str,
        properties: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a controller service."""
        service_data = {
            "revision": {"version": 0},
            "component": {
                "name": name,
                "type": service_type,
                "parentGroupId": parent_group_id
            }
        }
        
        if properties:
            service_data["component"]["properties"] = properties
        
        async with self.session.post(
            f"{self.nifi_url}/nifi-api/controller-services",
            json=service_data
        ) as response:
            response.raise_for_status()
            return await response.json()

    # --- Health and Diagnostics ---

    async def get_system_diagnostics(self) -> Dict[str, Any]:
        """Get system diagnostics."""
        async with self.session.get(f"{self.nifi_url}/nifi-api/system-diagnostics") as response:
            response.raise_for_status()
            return await response.json()

    async def get_flow_status(self) -> Dict[str, Any]:
        """Get overall flow status."""
        async with self.session.get(f"{self.nifi_url}/nifi-api/flow/status") as response:
            response.raise_for_status()
            return await response.json()

    async def health_check(self) -> bool:
        """Check if NiFi is healthy."""
        try:
            async with self.session.get(f"{self.nifi_url}/nifi-api/system-diagnostics") as response:
                return response.status == 200
        except Exception:
            return False