"""
Minimal NiFi Registry client for basic operations.

Focused on essential template and flow management.
"""

import logging
from typing import Dict, Any, Optional, List
import aiohttp

log = logging.getLogger(__name__)


class RegistryClient:
    """Simple NiFi Registry client."""

    def __init__(self, registry_url: str, auth_token: Optional[str] = None):
        self.registry_url = registry_url.rstrip('/')
        self.auth_token = auth_token
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """Async context manager entry."""
        headers = {'Content-Type': 'application/json'}

        # For minimal setup, start without authentication
        if self.auth_token:
            headers['Authorization'] = f'Bearer {self.auth_token}'

        self.session = aiohttp.ClientSession(
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=30)
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()

    async def get_registry_info(self) -> Dict[str, Any]:
        """Get registry information."""
        async with self.session.get(f"{self.registry_url}/nifi-registry-api/config") as response:
            response.raise_for_status()
            return await response.json()

    async def list_buckets(self) -> List[Dict[str, Any]]:
        """List all buckets."""
        async with self.session.get(f"{self.registry_url}/nifi-registry-api/buckets") as response:
            response.raise_for_status()
            return await response.json()

    async def create_bucket(self, name: str, description: str = "") -> Dict[str, Any]:
        """Create a new bucket."""
        payload = {
            "name": name,
            "description": description,
            "allowBundleRedeploy": False,
            "allowPublicRead": False
        }

        async with self.session.post(
            f"{self.registry_url}/nifi-registry-api/buckets",
            json=payload
        ) as response:
            response.raise_for_status()
            return await response.json()

    async def create_flow(self, bucket_id: str, flow_name: str, description: str = "") -> Dict[str, Any]:
        """Create a new flow in bucket."""
        payload = {
            "name": flow_name,
            "description": description,
            "type": "Flow",
            "bucketIdentifier": bucket_id
        }

        async with self.session.post(
            f"{self.registry_url}/nifi-registry-api/buckets/{bucket_id}/flows",
            json=payload
        ) as response:
            response.raise_for_status()
            return await response.json()

    async def create_flow_version(self, bucket_id: str, flow_id: str,
                                  flow_contents: Dict[str, Any], comments: str = "Initial version") -> Dict[str, Any]:
        """Create a new version of a flow."""
        payload = {
            "bucket": {"identifier": bucket_id},
            "snapshotMetadata": {
                "flowIdentifier": flow_id,
                "version": 1,  # Start with version 1
                "comments": comments
            },
            "flowContents": flow_contents
        }

        async with self.session.post(
            f"{self.registry_url}/nifi-registry-api/buckets/{bucket_id}/flows/{flow_id}/versions",
            json=payload
        ) as response:
            response.raise_for_status()
            return await response.json()

    async def get_flow_version(self, bucket_id: str, flow_id: str, version: int = 1) -> Dict[str, Any]:
        """Get a specific version of a flow."""
        async with self.session.get(
            f"{self.registry_url}/nifi-registry-api/buckets/{bucket_id}/flows/{flow_id}/versions/{version}"
        ) as response:
            response.raise_for_status()
            return await response.json()

    async def health_check(self) -> bool:
        """Simple health check."""
        try:
            await self.get_registry_info()
            return True
        except Exception as e:
            log.error(f"Registry health check failed: {e}")
            return False