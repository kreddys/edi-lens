"""
Minimal NiFi API client for basic operations.

Focused on essential functionality without complex authentication.
"""

import logging
from typing import Dict, Any, Optional
import aiohttp

log = logging.getLogger(__name__)


class NiFiClient:
    """Simple NiFi API client."""

    def __init__(self, nifi_url: str, username: Optional[str] = None, password: Optional[str] = None):
        self.nifi_url = nifi_url.rstrip('/')
        self.username = username
        self.password = password
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """Async context manager entry."""
        headers = {'Content-Type': 'application/json'}

        # Add basic auth if username/password provided
        auth = None
        if self.username and self.password:
            auth = aiohttp.BasicAuth(self.username, self.password)

        # Disable SSL verification for development with self-signed certs
        import ssl
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        connector = aiohttp.TCPConnector(ssl=ssl_context)

        self.session = aiohttp.ClientSession(
            headers=headers,
            auth=auth,
            connector=connector,
            timeout=aiohttp.ClientTimeout(total=30)
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()

    async def get_system_summary(self) -> Dict[str, Any]:
        """Get NiFi system summary - basic connectivity test."""
        async with self.session.get(f"{self.nifi_url}/nifi-api/system-diagnostics") as response:
            response.raise_for_status()
            return await response.json()

    async def get_root_process_group(self) -> Dict[str, Any]:
        """Get root process group."""
        async with self.session.get(f"{self.nifi_url}/nifi-api/process-groups/root") as response:
            response.raise_for_status()
            return await response.json()

    async def get_process_group_flow(self, pg_id: str = "root") -> Dict[str, Any]:
        """Get process group flow contents."""
        async with self.session.get(f"{self.nifi_url}/nifi-api/process-groups/{pg_id}/flow") as response:
            response.raise_for_status()
            return await response.json()

    async def create_parameter_context(self, name: str, description: str = "",
                                       parameters: Optional[list] = None) -> Dict[str, Any]:
        """Create a parameter context."""
        payload = {
            "component": {
                "name": name,
                "description": description,
                "parameters": parameters or []
            },
            "revision": {"version": 0}
        }

        async with self.session.post(
            f"{self.nifi_url}/nifi-api/parameter-contexts",
            json=payload
        ) as response:
            response.raise_for_status()
            return await response.json()

    async def import_from_registry(self, parent_group_id: str, bucket_id: str,
                                   flow_id: str, version: int = 1) -> Dict[str, Any]:
        """Import a process group from registry."""
        payload = {
            "revision": {"version": 0},
            "component": {
                "versionControlInformation": {
                    "bucketId": bucket_id,
                    "flowId": flow_id,
                    "version": version,
                    "registryId": "default"  # We'll need to configure this
                }
            }
        }

        async with self.session.post(
            f"{self.nifi_url}/nifi-api/process-groups/{parent_group_id}/process-groups",
            json=payload
        ) as response:
            response.raise_for_status()
            return await response.json()

    async def health_check(self) -> bool:
        """Simple health check."""
        try:
            await self.get_system_summary()
            return True
        except Exception as e:
            log.error(f"NiFi health check failed: {e}")
            return False