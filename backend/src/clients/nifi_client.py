"""NiFi API client with minimal ergonomics and sane defaults."""

from __future__ import annotations

import logging
import ssl
from typing import Any, Dict, Optional

import aiohttp

log = logging.getLogger(__name__)


class NiFiClientError(RuntimeError):
    """Raised when NiFi API calls fail."""


class NiFiClient:
    """Simple NiFi API client."""

    def __init__(
        self,
        nifi_url: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        *,
        session: Optional[aiohttp.ClientSession] = None,
        verify_ssl: bool = True,
        timeout: Optional[float] = 30,
    ):
        self.nifi_url = nifi_url.rstrip("/")
        self.username = username
        self.password = password
        self._external_session = session
        self.verify_ssl = verify_ssl
        self._timeout = aiohttp.ClientTimeout(total=timeout) if timeout else None
        self.session: Optional[aiohttp.ClientSession] = session

    async def __aenter__(self) -> "NiFiClient":
        """Async context manager entry."""

        if self.session is None:
            self.session = await self._create_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""

        if self.session and self._external_session is None:
            await self.session.close()
            self.session = None

    async def _create_session(self) -> aiohttp.ClientSession:
        headers = {"Content-Type": "application/json"}
        auth = None
        if self.username and self.password:
            auth = aiohttp.BasicAuth(self.username, self.password)

        connector = None
        if not self.verify_ssl:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            connector = aiohttp.TCPConnector(ssl=ssl_context)

        return aiohttp.ClientSession(
            headers=headers,
            auth=auth,
            connector=connector,
            timeout=self._timeout,
        )

    async def _request(self, method: str, path: str, **kwargs) -> Any:
        if self.session is None:
            raise NiFiClientError("Client session has not been initialised. Use 'async with NiFiClient(...)'.")

        url = f"{self.nifi_url}{path}"

        try:
            async with self.session.request(method, url, **kwargs) as response:
                response.raise_for_status()
                if response.content_type == "application/json":
                    return await response.json()
                return await response.text()
        except aiohttp.ClientError as exc:
            raise NiFiClientError(f"Request to NiFi failed: {exc}") from exc

    async def get_system_summary(self) -> Dict[str, Any]:
        """Get NiFi system summary - basic connectivity test."""

        result = await self._request("GET", "/nifi-api/system-diagnostics")
        if not isinstance(result, dict):
            raise NiFiClientError("Unexpected response format for system diagnostics")
        return result

    async def get_root_process_group(self) -> Dict[str, Any]:
        """Get root process group."""

        result = await self._request("GET", "/nifi-api/process-groups/root")
        if not isinstance(result, dict):
            raise NiFiClientError("Unexpected response format for root process group")
        return result

    async def get_process_group_flow(self, pg_id: str = "root") -> Dict[str, Any]:
        """Get process group flow contents."""

        result = await self._request("GET", f"/nifi-api/process-groups/{pg_id}/flow")
        if not isinstance(result, dict):
            raise NiFiClientError("Unexpected response format for process group flow")
        return result

    async def create_parameter_context(
        self,
        name: str,
        *,
        description: str = "",
        parameters: Optional[list[dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Create a parameter context."""

        payload = {
            "component": {
                "name": name,
                "description": description,
                "parameters": parameters or [],
            },
            "revision": {"version": 0},
        }

        result = await self._request(
            "POST",
            "/nifi-api/parameter-contexts",
            json=payload,
        )
        if not isinstance(result, dict):
            raise NiFiClientError("Unexpected response creating parameter context")
        return result

    async def import_from_registry(
        self,
        parent_group_id: str,
        bucket_id: str,
        flow_id: str,
        *,
        version: int = 1,
        registry_id: str = "default",
    ) -> Dict[str, Any]:
        """Import a process group from the NiFi registry."""

        payload = {
            "revision": {"version": 0},
            "component": {
                "versionControlInformation": {
                    "bucketId": bucket_id,
                    "flowId": flow_id,
                    "version": version,
                    "registryId": registry_id,
                }
            },
        }

        result = await self._request(
            "POST",
            f"/nifi-api/process-groups/{parent_group_id}/process-groups",
            json=payload,
        )
        if not isinstance(result, dict):
            raise NiFiClientError("Unexpected response importing process group from registry")
        return result

    async def health_check(self) -> bool:
        """Simple health check."""

        try:
            await self.get_system_summary()
            return True
        except NiFiClientError as exc:
            log.error("NiFi health check failed: %s", exc)
        except Exception as exc:  # pragma: no cover - defensive fallback
            log.exception("Unexpected error during NiFi health check: %s", exc)
        return False
