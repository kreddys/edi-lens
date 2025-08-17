"""
NiFi Registry Client for EDI Lens.

This client provides integration with Apache NiFi Registry for managing
workflow templates as versioned flows.
"""

import aiohttp
import json
from typing import Optional, List, Dict, Any, Union
from urllib.parse import urljoin


class NiFiRegistryClient:
    """Client for NiFi Registry API integration."""

    def __init__(self, registry_url: str, auth_token: Optional[str] = None):
        self.registry_url = registry_url.rstrip('/')
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

    # --- Bucket Management ---

    async def list_buckets(self) -> List[Dict[str, Any]]:
        """List all available buckets."""
        async with self.session.get(f"{self.registry_url}/nifi-registry-api/buckets") as response:
            response.raise_for_status()
            return await response.json()

    async def create_bucket(self, name: str, description: str = "") -> Dict[str, Any]:
        """Create a new bucket for storing flows."""
        bucket_data = {
            "name": name,
            "description": description,
            "allowBundleRedeploy": False,
            "allowPublicRead": False
        }
        
        async with self.session.post(
            f"{self.registry_url}/nifi-registry-api/buckets",
            json=bucket_data
        ) as response:
            response.raise_for_status()
            return await response.json()

    async def get_bucket(self, bucket_id: str) -> Dict[str, Any]:
        """Get bucket details by ID."""
        async with self.session.get(
            f"{self.registry_url}/nifi-registry-api/buckets/{bucket_id}"
        ) as response:
            response.raise_for_status()
            return await response.json()

    async def delete_bucket(self, bucket_id: str) -> bool:
        """Delete a bucket by ID."""
        async with self.session.delete(
            f"{self.registry_url}/nifi-registry-api/buckets/{bucket_id}"
        ) as response:
            response.raise_for_status()
            return response.status == 200

    # --- Flow Management ---

    async def create_flow(
        self,
        bucket_id: str,
        flow_name: str,
        flow_description: str = "",
        flow_type: str = "Flow"
    ) -> Dict[str, Any]:
        """Create a new flow in the registry."""
        flow_data = {
            "name": flow_name,
            "description": flow_description,
            "type": flow_type,
            "bucketIdentifier": bucket_id
        }
        
        async with self.session.post(
            f"{self.registry_url}/nifi-registry-api/buckets/{bucket_id}/flows",
            json=flow_data
        ) as response:
            response.raise_for_status()
            return await response.json()

    async def create_flow_version(
        self,
        bucket_id: str,
        flow_id: str,
        version_data: Dict[str, Any],
        comments: str = ""
    ) -> Dict[str, Any]:
        """Create a new version of an existing flow."""
        # According to NiFi Registry API, we need to send a VersionedFlowSnapshot object
        # which includes bucket info, snapshot metadata, and flow contents
        flow_contents = version_data.get("flowContents", {})
        
        # Ensure the flow contents have the required version field
        if "version" not in flow_contents:
            flow_contents["version"] = 1
            
        # Ensure required fields are present
        if "identifier" not in flow_contents:
            flow_contents["identifier"] = flow_id
            
        version_payload = {
            "bucket": {
                "identifier": bucket_id
            },
            "snapshotMetadata": {
                "flowIdentifier": flow_id,
                "comments": comments,
                "version": 1  # This is the version of the snapshot itself
            },
            "flowContents": flow_contents,
            "parameterContexts": version_data.get("parameterContexts", {}),
            "externalControllerServices": version_data.get("externalControllerServices", {})
        }
        
        # Debug logging
        print(f"Sending version payload to NiFi Registry: {version_payload}")
        
        async with self.session.post(
            f"{self.registry_url}/nifi-registry-api/buckets/{bucket_id}/flows/{flow_id}/versions",
            json=version_payload
        ) as response:
            # Log the request and response for debugging
            if response.status >= 400:
                try:
                    error_text = await response.text()
                    print(f"NiFi Registry API Error: {response.status} - {error_text}")
                except:
                    pass
            response.raise_for_status()
            return await response.json()

    async def get_flow(self, bucket_id: str, flow_id: str) -> Dict[str, Any]:
        """Get flow details by ID."""
        async with self.session.get(
            f"{self.registry_url}/nifi-registry-api/buckets/{bucket_id}/flows/{flow_id}"
        ) as response:
            response.raise_for_status()
            return await response.json()

    async def list_flows(self, bucket_id: str) -> List[Dict[str, Any]]:
        """List all flows in a bucket."""
        async with self.session.get(
            f"{self.registry_url}/nifi-registry-api/buckets/{bucket_id}/flows"
        ) as response:
            response.raise_for_status()
            return await response.json()

    async def delete_flow(self, bucket_id: str, flow_id: str) -> bool:
        """Delete a flow by ID."""
        async with self.session.delete(
            f"{self.registry_url}/nifi-registry-api/buckets/{bucket_id}/flows/{flow_id}"
        ) as response:
            response.raise_for_status()
            return response.status == 200

    # --- Flow Version Management ---

    async def get_flow_version(
        self,
        bucket_id: str,
        flow_id: str,
        version: Optional[Union[int, str]] = None
    ) -> Dict[str, Any]:
        """Get a specific version of a flow."""
        url = f"{self.registry_url}/nifi-registry-api/buckets/{bucket_id}/flows/{flow_id}"
        if version:
            url += f"/versions/{version}"
        
        async with self.session.get(url) as response:
            response.raise_for_status()
            return await response.json()

    async def list_flow_versions(self, bucket_id: str, flow_id: str) -> List[Dict[str, Any]]:
        """List all versions of a flow."""
        async with self.session.get(
            f"{self.registry_url}/nifi-registry-api/buckets/{bucket_id}/flows/{flow_id}/versions"
        ) as response:
            response.raise_for_status()
            return await response.json()

    # --- Extension Bundles (for custom processors) ---

    async def upload_extension_bundle(
        self,
        bucket_id: str,
        file_path: str,
        bundle_name: str,
        bundle_description: str = ""
    ) -> Dict[str, Any]:
        """Upload a custom processor bundle (NAR file)."""
        # This would typically involve multipart form upload
        # Implementation details would depend on the specific API
        raise NotImplementedError("Extension bundle upload not yet implemented")

    # --- Health and Diagnostics ---

    async def get_registry_info(self) -> Dict[str, Any]:
        """Get registry information and version."""
        async with self.session.get(f"{self.registry_url}/nifi-registry-api/config") as response:
            response.raise_for_status()
            return await response.json()

    async def health_check(self) -> Dict[str, Any]:
        """Check if the registry is healthy."""
        async with self.session.get(f"{self.registry_url}/nifi-registry-api/health") as response:
            response.raise_for_status()
            return await response.json()