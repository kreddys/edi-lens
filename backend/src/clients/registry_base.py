"""Base Registry client with core HTTP operations."""

from __future__ import annotations

import json
import ssl
from typing import Any, Dict, List, Optional

import aiohttp

from ..core.logging import get_logger, LoggerMixin

log = get_logger(__name__)


class RegistryClientError(RuntimeError):
    """Raised when Registry API calls fail."""


class RegistryBaseClient(LoggerMixin):
    """Base NiFi Registry API client with core HTTP operations."""

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

        self.logger.info("Initializing Registry base client for %s", self.registry_url)
        self.logger.debug("Authentication: %s", "token provided" if auth_token else "none")
        self.logger.debug("SSL verification: %s", "enabled" if verify_ssl else "disabled")
        self.logger.debug("Timeout: %ss", timeout if timeout else "unlimited")

        if not verify_ssl:
            self.logger.warning("SSL verification is disabled - not recommended for production")

    async def __aenter__(self) -> "RegistryBaseClient":
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session and not self._external_session:
            await self.session.close()

    async def _ensure_session(self):
        """Ensure HTTP session exists."""
        if self.session is None:
            connector = None
            if not self.verify_ssl:
                connector = aiohttp.TCPConnector(ssl=False)

            self.session = aiohttp.ClientSession(
                connector=connector,
                timeout=self._timeout,
            )
            self.logger.debug("Created new HTTP session")

    async def _request(
        self,
        method: str,
        endpoint: str,
        *,
        json_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Make HTTP request to Registry API."""
        await self._ensure_session()

        url = f"{self.registry_url}/nifi-registry-api{endpoint}"

        request_headers = {"Content-Type": "application/json"}
        if self.auth_token:
            request_headers["Authorization"] = f"Bearer {self.auth_token}"
        if headers:
            request_headers.update(headers)

        self.logger.debug("Registry API %s %s", method, endpoint)

        try:
            async with self.session.request(
                method,
                url,
                json=json_data,
                params=params,
                headers=request_headers,
            ) as response:
                response_text = await response.text()

                if response.status >= 400:
                    self.logger.error(
                        "Registry API error: %s %s -> %d: %s",
                        method,
                        endpoint,
                        response.status,
                        response_text[:500] + "..." if len(response_text) > 500 else response_text,
                    )
                    raise RegistryClientError(f"Registry API error: {response.status} - {response_text}")

                if response_text:
                    try:
                        return json.loads(response_text)
                    except json.JSONDecodeError:
                        self.logger.warning("Non-JSON response: %s", response_text[:200])
                        return {"raw_response": response_text}
                else:
                    return {}

        except aiohttp.ClientError as exc:
            self.logger.error("Registry API request failed: %s %s - %s", method, endpoint, exc)
            raise RegistryClientError(f"Registry API request failed: {exc}") from exc

    async def get(self, endpoint: str, *, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """GET request to Registry API."""
        return await self._request("GET", endpoint, params=params)

    async def post(
        self,
        endpoint: str,
        json_data: Optional[Dict[str, Any]] = None,
        *,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """POST request to Registry API."""
        return await self._request("POST", endpoint, json_data=json_data, params=params)

    async def put(
        self,
        endpoint: str,
        json_data: Optional[Dict[str, Any]] = None,
        *,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """PUT request to Registry API."""
        return await self._request("PUT", endpoint, json_data=json_data, params=params)

    async def delete(
        self,
        endpoint: str,
        *,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """DELETE request to Registry API."""
        return await self._request("DELETE", endpoint, params=params)