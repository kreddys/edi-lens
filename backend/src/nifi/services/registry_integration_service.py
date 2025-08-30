"""
NiFi Registry Integration Service.

This service handles the proper integration between NiFi and NiFi Registry,
including registry client registration and version control operations.
"""

import logging
from typing import Dict, Any, Optional
from uuid import UUID

from src.core.config import settings
from src.nifi.clients.nifi_client import NiFiAPIClient
from src.nifi.clients.registry_client import NiFiRegistryClient

log = logging.getLogger(__name__)


class RegistryIntegrationService:
    """Service for NiFi-Registry integration setup and operations."""
    
    async def setup_registry_integration(self) -> Dict[str, Any]:
        """
        Set up NiFi Registry integration by registering the Registry client with NiFi.
        
        Returns:
            Registry client information from NiFi
        """
        try:
            async with NiFiAPIClient(
                settings.NIFI_URL,
                username=settings.NIFI_USERNAME,
                password=settings.NIFI_PASSWORD
            ) as nifi_client:
                
                # Check if registry client already exists
                existing_clients = await self._list_registry_clients(nifi_client)
                registry_client = None
                
                for client in existing_clients:
                    component = client.get("component", {})
                    # Check various possible fields where the URL might be stored
                    if (component.get("uri") == settings.NIFI_REGISTRY_URL or
                        component.get("properties", {}).get("url") == settings.NIFI_REGISTRY_URL or
                        component.get("properties", {}).get("URL") == settings.NIFI_REGISTRY_URL or
                        "EDI Lens Registry" in component.get("name", "")):
                        registry_client = client
                        break
                
                if registry_client:
                    log.info(f"Registry client already exists: {registry_client['component']['name']}")
                    return registry_client
                
                # Create new registry client
                registry_client = await self._create_registry_client(nifi_client)
                log.info(f"Created registry client: {registry_client['component']['name']}")
                return registry_client
                
        except Exception as e:
            log.error(f"Failed to setup registry integration: {str(e)}")
            raise
    
    async def deploy_from_registry(
        self,
        nifi_client: NiFiAPIClient,
        parent_group_id: str,
        bucket_id: str,
        flow_id: str,
        flow_version: int,
        process_group_name: str,
        position: Dict[str, int] = None
    ) -> Dict[str, Any]:
        """
        Deploy a process group from Registry using NiFi's version control.
        
        Args:
            nifi_client: NiFi API client
            parent_group_id: Parent process group ID
            bucket_id: Registry bucket ID
            flow_id: Registry flow ID
            flow_version: Flow version to deploy
            process_group_name: Name for the process group
            position: Position for the process group
            
        Returns:
            Created process group information
        """
        try:
            # 1. Get registry client ID
            registry_clients = await self._list_registry_clients(nifi_client)
            log.info(f"Registry clients structure: {registry_clients}")
            
            registry_client = None
            for client in registry_clients:
                log.info(f"Client structure: {client}")
                # Try different possible field names for URI and name matching
                uri = None
                name = None
                if isinstance(client, dict):
                    component = client.get("component", {})
                    name = component.get("name", "")
                    
                    # Check URI in various locations
                    if "uri" in component:
                        uri = component["uri"]
                    elif "uri" in client:
                        uri = client["uri"]
                    elif "url" in component:
                        uri = component["url"]
                    elif component.get("properties", {}).get("url"):
                        uri = component["properties"]["url"]
                    elif component.get("properties", {}).get("URL"):
                        uri = component["properties"]["URL"]
                        
                # Match by URI or by name (for cases where URI might be different)
                if (uri == settings.NIFI_REGISTRY_URL or 
                    "EDI Lens Registry" in name):
                    registry_client = client
                    log.info(f"Found matching registry client: {name} with URI: {uri}")
                    break
            
            if not registry_client:
                raise ValueError("Registry client not found. Run setup_registry_integration() first.")
            
            registry_client_id = registry_client["component"]["id"]
            
            # 2. Import process group from Registry using the correct NiFi API
            # Use the version control import endpoint instead of creating a process group directly
            import_data = {
                "revision": {"version": 0},
                "component": {
                    "versionControlInformation": {
                        "registryId": registry_client_id,
                        "bucketId": bucket_id,
                        "flowId": flow_id,
                        "version": flow_version
                    },
                    "position": position or {"x": 100, "y": 100}
                }
            }
            
            # 3. Import process group from Registry using the correct endpoint
            response = await nifi_client.session.post(
                f"{nifi_client.nifi_url}/process-groups/{parent_group_id}/process-groups",
                json=import_data
            )
            response.raise_for_status()
            process_group = await response.json()
            
            log.info(f"Deployed process group {process_group['component']['id']} from Registry")
            return process_group
            
        except Exception as e:
            log.error(f"Failed to deploy from Registry: {str(e)}")
            raise
    
    async def change_flow_version(
        self,
        nifi_client: NiFiAPIClient,
        process_group_id: str,
        new_version: int
    ) -> Dict[str, Any]:
        """
        Change the version of a version-controlled process group.
        
        Args:
            nifi_client: NiFi API client
            process_group_id: Process group ID
            new_version: New version to deploy
            
        Returns:
            Updated process group information
        """
        try:
            # Get current process group info
            pg_info = await nifi_client.get_process_group(process_group_id)
            version_control_info = pg_info["component"].get("versionControlInformation")
            
            if not version_control_info:
                raise ValueError(f"Process group {process_group_id} is not version controlled")
            
            # Update version control information
            update_data = {
                "processGroupRevision": pg_info["revision"],
                "versionControlInformation": {
                    **version_control_info,
                    "version": new_version
                }
            }
            
            response = await nifi_client.session.put(
                f"{nifi_client.nifi_url}/versions/process-groups/{process_group_id}",
                json=update_data
            )
            response.raise_for_status()
            result = await response.json()
            
            log.info(f"Changed process group {process_group_id} to version {new_version}")
            return result
            
        except Exception as e:
            log.error(f"Failed to change flow version: {str(e)}")
            raise
    
    async def _list_registry_clients(self, nifi_client: NiFiAPIClient) -> list:
        """List all registry clients in NiFi."""
        response = await nifi_client.session.get(f"{nifi_client.nifi_url}/controller/registry-clients")
        response.raise_for_status()
        data = await response.json()
        return data.get("registries", [])
    
    async def _create_registry_client(self, nifi_client: NiFiAPIClient) -> Dict[str, Any]:
        """Create a new registry client in NiFi."""
        registry_data = {
            "revision": {"version": 0},
            "component": {
                "name": "EDI Lens Registry",
                "type": "org.apache.nifi.registry.flow.NifiRegistryFlowRegistryClient",
                "properties": {
                    "url": settings.NIFI_REGISTRY_URL
                },
                "description": "EDI Lens NiFi Registry for workflow templates"
            }
        }
        
        response = await nifi_client.session.post(
            f"{nifi_client.nifi_url}/controller/registry-clients",
            json=registry_data
        )
        response.raise_for_status()
        return await response.json()