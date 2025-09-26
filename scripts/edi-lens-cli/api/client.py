"""
EDI Lens API Client - Handles all communication with the backend API.
"""

import json
from typing import Dict, Any, List, Optional
import httpx
from pathlib import Path


class APIError(Exception):
    """Raised when API calls fail."""
    pass


class EDILensAPIClient:
    """Client for communicating with the EDI Lens backend API."""
    
    def __init__(self, base_url: str = "http://localhost:8000", timeout: int = 30):
        """Initialize the API client."""
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)
        
    async def __aenter__(self):
        """Async context manager entry."""
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.client.aclose()
        
    async def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make an HTTP request to the API."""
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = await self.client.request(method, url, **kwargs)
            response.raise_for_status()
            
            if response.headers.get("content-type", "").startswith("application/json"):
                return response.json()
            else:
                return {"data": response.text}
                
        except httpx.HTTPStatusError as e:
            # Try to extract error details from response
            try:
                error_data = e.response.json()
                if isinstance(error_data, dict) and "detail" in error_data:
                    raise APIError(f"API Error: {error_data['detail']}")
                else:
                    raise APIError(f"API Error {e.response.status_code}: {error_data}")
            except (json.JSONDecodeError, ValueError):
                raise APIError(f"API Error {e.response.status_code}: {e.response.text}")
                
        except httpx.RequestError as e:
            raise APIError(f"Connection error: {e}")
    
    # Health endpoints
    async def get_system_health(self) -> Dict[str, Any]:
        """Get overall system health."""
        return await self._request("GET", "/health")
        
    async def get_nifi_health(self) -> Dict[str, Any]:
        """Get NiFi health status."""
        return await self._request("GET", "/health/nifi")
        
    async def get_registry_health(self) -> Dict[str, Any]:
        """Get Registry health status."""
        return await self._request("GET", "/health/registry")
    
    # Flow management endpoints
    async def deploy_flow(self, flow_definition: Dict[str, Any], flow_name: str, 
                         bucket_id: str, parameters: Dict[str, Any] = None,
                         flow_description: str = "", parent_group_id: str = "root") -> Dict[str, Any]:
        """Deploy a new flow to NiFi and register in Registry."""
        payload = {
            "flow_definition": flow_definition,
            "flow_name": flow_name,
            "bucket_id": bucket_id,
            "parameters": parameters or {},
            "flow_description": flow_description,
            "parent_group_id": parent_group_id
        }
        return await self._request("POST", "/api/flows/deploy-and-store", json=payload)
    
    async def get_flow_status(self, process_group_id: str) -> Dict[str, Any]:
        """Get status of a deployed flow."""
        return await self._request("GET", f"/api/flows/{process_group_id}/status")
    
    async def start_flow(self, process_group_id: str) -> Dict[str, Any]:
        """Start a flow."""
        return await self._request("POST", f"/api/flows/{process_group_id}/start")
    
    async def stop_flow(self, process_group_id: str) -> Dict[str, Any]:
        """Stop a flow."""
        return await self._request("POST", f"/api/flows/{process_group_id}/stop")
    
    async def delete_flow(self, process_group_id: str, remove_from_registry: bool = False) -> Dict[str, Any]:
        """Delete a flow."""
        params = {"remove_from_registry": remove_from_registry}
        return await self._request("DELETE", f"/api/flows/{process_group_id}", params=params)
    
    # Registry endpoints
    async def list_buckets(self) -> List[Dict[str, Any]]:
        """List all Registry buckets."""
        return await self._request("GET", "/api/flows/registry/buckets")
    
    async def list_flows_in_bucket(self, bucket_id: str) -> List[Dict[str, Any]]:
        """List flows in a specific bucket."""
        return await self._request("GET", f"/api/flows/registry/buckets/{bucket_id}/flows")
    
    async def get_flow_from_registry(self, bucket_id: str, flow_id: str, 
                                   version: Optional[int] = None) -> Dict[str, Any]:
        """Get flow definition from Registry."""
        params = {"version": version} if version else {}
        return await self._request("GET", f"/api/flows/registry/buckets/{bucket_id}/flows/{flow_id}", params=params)
    
    # Version control endpoints
    async def commit_changes(self, process_group_id: str, comments: str = "Updated flow") -> Dict[str, Any]:
        """Commit local changes to Registry."""
        params = {"comments": comments}
        return await self._request("POST", f"/api/flows/{process_group_id}/version-control/commit", params=params)
    
    async def update_from_registry(self, process_group_id: str) -> Dict[str, Any]:
        """Update flow from latest version in Registry."""
        return await self._request("POST", f"/api/flows/{process_group_id}/version-control/update")
    
    async def revert_changes(self, process_group_id: str) -> Dict[str, Any]:
        """Revert local changes to Registry version."""
        return await self._request("POST", f"/api/flows/{process_group_id}/version-control/revert")
    
    async def get_local_modifications(self, process_group_id: str) -> Dict[str, Any]:
        """Get local modifications for a version controlled flow."""
        return await self._request("GET", f"/api/flows/{process_group_id}/version-control/modifications")
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()