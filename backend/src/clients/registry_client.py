"""NiFi Registry client for basic operations."""

from __future__ import annotations

import logging
import ssl
from typing import Any, Dict, List, Optional

import aiohttp

log = logging.getLogger(__name__)


class RegistryClientError(RuntimeError):
    """Raised when registry API calls fail."""


class RegistryClient:
    """Simple NiFi Registry client."""

    def __init__(
        self,
        registry_url: str,
        auth_token: Optional[str] = None,
        *,
        session: Optional[aiohttp.ClientSession] = None,
        verify_ssl: bool = True,
        timeout: Optional[float] = 30,
    ):
        self.registry_url = registry_url.rstrip("/")
        self.auth_token = auth_token
        self._external_session = session
        self.verify_ssl = verify_ssl
        self._timeout = aiohttp.ClientTimeout(total=timeout) if timeout else None
        self.session: Optional[aiohttp.ClientSession] = session

    async def __aenter__(self) -> "RegistryClient":
        if self.session is None:
            self.session = await self._create_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self.session and self._external_session is None:
            await self.session.close()
            self.session = None

    async def _create_session(self) -> aiohttp.ClientSession:
        headers = {"Content-Type": "application/json"}

        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"

        connector = None
        if not self.verify_ssl:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            connector = aiohttp.TCPConnector(ssl=ssl_context)

        return aiohttp.ClientSession(
            headers=headers,
            connector=connector,
            timeout=self._timeout,
        )

    async def _request(self, method: str, path: str, **kwargs) -> Any:
        if self.session is None:
            raise RegistryClientError(
                "Client session has not been initialised. Use 'async with RegistryClient(...)'."
            )

        url = f"{self.registry_url}{path}"

        try:
            async with self.session.request(method, url, **kwargs) as response:
                response.raise_for_status()
                if response.content_type == "application/json":
                    return await response.json()
                return await response.text()
        except aiohttp.ClientError as exc:
            raise RegistryClientError(f"Request to NiFi Registry failed: {exc}") from exc

    async def get_registry_info(self) -> Dict[str, Any]:
        """Get registry information."""

        result = await self._request("GET", "/nifi-registry-api/config")
        if not isinstance(result, dict):
            raise RegistryClientError("Unexpected response format for registry info")
        return result

    async def list_buckets(self) -> List[Dict[str, Any]]:
        """List all buckets."""

        result = await self._request("GET", "/nifi-registry-api/buckets")
        if not isinstance(result, list):
            raise RegistryClientError("Unexpected response format listing buckets")
        return result

    async def create_bucket(self, name: str, description: str = "") -> Dict[str, Any]:
        """Create a new bucket."""

        payload = {
            "name": name,
            "description": description,
            "allowBundleRedeploy": False,
            "allowPublicRead": False,
        }

        result = await self._request(
            "POST",
            "/nifi-registry-api/buckets",
            json=payload,
        )
        if not isinstance(result, dict):
            raise RegistryClientError("Unexpected response creating bucket")
        return result

    async def create_flow(self, bucket_id: str, flow_name: str, description: str = "") -> Dict[str, Any]:
        """Create a new flow in bucket."""

        payload = {
            "name": flow_name,
            "description": description,
            "type": "Flow",
            "bucketIdentifier": bucket_id,
        }

        result = await self._request(
            "POST",
            f"/nifi-registry-api/buckets/{bucket_id}/flows",
            json=payload,
        )
        if not isinstance(result, dict):
            raise RegistryClientError("Unexpected response creating flow")
        return result

    async def create_flow_version(
        self,
        bucket_id: str,
        flow_id: str,
        flow_contents: Dict[str, Any],
        *,
        version: int = 1,
        comments: str | None = "Initial version",
    ) -> Dict[str, Any]:
        """Create a new version of a flow."""

        payload = {
            "bucket": {"identifier": bucket_id},
            "snapshotMetadata": {
                "flowIdentifier": flow_id,
                "version": version,
                "comments": comments or "",
            },
            "flowContents": flow_contents,
        }

        result = await self._request(
            "POST",
            f"/nifi-registry-api/buckets/{bucket_id}/flows/{flow_id}/versions",
            json=payload,
        )
        if not isinstance(result, dict):
            raise RegistryClientError("Unexpected response creating flow version")
        return result

    async def get_flow_version(self, bucket_id: str, flow_id: str, version: int = 1) -> Dict[str, Any]:
        """Get a specific version of a flow."""

        result = await self._request(
            "GET",
            f"/nifi-registry-api/buckets/{bucket_id}/flows/{flow_id}/versions/{version}",
        )
        if not isinstance(result, dict):
            raise RegistryClientError("Unexpected response fetching flow version")
        return result

    async def health_check(self) -> bool:
        """Simple health check."""

        try:
            await self.get_registry_info()
            return True
        except RegistryClientError as exc:
            log.error("Registry health check failed: %s", exc)
        except Exception as exc:  # pragma: no cover - defensive fallback
            log.exception("Unexpected error during registry health check: %s", exc)
        return False
