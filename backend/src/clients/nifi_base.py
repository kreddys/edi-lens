"""Base NiFi client with core HTTP operations."""

from __future__ import annotations

import json
import ssl
from typing import Any, Dict, List, Optional

import aiohttp
from yarl import URL

from ..core.logging import get_logger, LoggerMixin

log = get_logger(__name__)


class NiFiClientError(RuntimeError):
    """Raised when NiFi API calls fail."""


class NiFiBaseClient(LoggerMixin):
    """Base NiFi API client with core HTTP operations."""

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
        self.auth_token: Optional[str] = None

        self.logger.info("Initializing NiFi base client for %s", self.nifi_url)
        self.logger.debug("Authentication: %s", "enabled" if username else "disabled")
        self.logger.debug("SSL verification: %s", "enabled" if verify_ssl else "disabled")
        self.logger.debug("Timeout: %ss", timeout if timeout else "unlimited")

        if not verify_ssl:
            self.logger.warning("SSL verification is disabled - not recommended for production")

    async def __aenter__(self) -> "NiFiBaseClient":
        await self._ensure_session()
        if self.username and self.password:
            await self._authenticate()
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

    async def _authenticate(self) -> str:
        """Authenticate with NiFi and get token."""
        if not self.username or not self.password:
            raise NiFiClientError("Username and password required for authentication")

        await self._ensure_session()

        auth_url = f"{self.nifi_url}/nifi-api/access/token"

        self.logger.debug("Authenticating with NiFi...")

        try:
            async with self.session.post(
                auth_url,
                data=f"username={self.username}&password={self.password}",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            ) as response:
                if response.status == 201:
                    self.auth_token = await response.text()
                    self.logger.info("Successfully authenticated with NiFi")
                    if self.session is not None:
                        self.session.cookie_jar.clear()
                    return self.auth_token
                else:
                    error_text = await response.text()
                    self.logger.error("Authentication failed: %s", error_text)
                    raise NiFiClientError(f"Authentication failed: {response.status} - {error_text}")

        except aiohttp.ClientError as exc:
            self.logger.error("Authentication request failed: %s", exc)
            raise NiFiClientError(f"Authentication request failed: {exc}") from exc

    async def _request(
        self,
        method: str,
        endpoint: str,
        *,
        json_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Make HTTP request to NiFi API."""
        await self._ensure_session()

        url = f"{self.nifi_url}/nifi-api{endpoint}"

        request_headers = {"Content-Type": "application/json"}
        if self.auth_token:
            request_headers["Authorization"] = f"Bearer {self.auth_token}"
        if headers:
            request_headers.update(headers)

        # Add CSRF request token header when NiFi has issued a token cookie.
        if self.session and method.upper() in {"POST", "PUT", "DELETE", "PATCH"}:
            cookies = self.session.cookie_jar.filter_cookies(URL(url))
            csrf_cookie = cookies.get("__Secure-Request-Token")
            if csrf_cookie and "Request-Token" not in request_headers:
                request_headers["Request-Token"] = csrf_cookie.value

        self.logger.debug("NiFi API %s %s", method, endpoint)

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
                        "NiFi API error: %s %s -> %d: %s",
                        method,
                        endpoint,
                        response.status,
                        response_text[:500] + "..." if len(response_text) > 500 else response_text,
                    )
                    raise NiFiClientError(f"NiFi API error: {response.status} - {response_text}")

                if response_text:
                    try:
                        return json.loads(response_text)
                    except json.JSONDecodeError:
                        self.logger.warning("Non-JSON response: %s", response_text[:200])
                        return {"raw_response": response_text}
                else:
                    return {}

        except aiohttp.ClientError as exc:
            self.logger.error("NiFi API request failed: %s %s - %s", method, endpoint, exc)
            raise NiFiClientError(f"NiFi API request failed: {exc}") from exc

    async def get(self, endpoint: str, *, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """GET request to NiFi API."""
        return await self._request("GET", endpoint, params=params)

    async def post(
        self,
        endpoint: str,
        json_data: Optional[Dict[str, Any]] = None,
        *,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """POST request to NiFi API."""
        return await self._request("POST", endpoint, json_data=json_data, params=params)

    async def put(
        self,
        endpoint: str,
        json_data: Optional[Dict[str, Any]] = None,
        *,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """PUT request to NiFi API."""
        return await self._request("PUT", endpoint, json_data=json_data, params=params)

    async def delete(
        self,
        endpoint: str,
        *,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """DELETE request to NiFi API."""
        return await self._request("DELETE", endpoint, params=params)
