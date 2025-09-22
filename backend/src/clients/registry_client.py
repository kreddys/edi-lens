"""NiFi Registry client for basic operations."""

from __future__ import annotations

import logging
import ssl
import time
from typing import Any, Dict, List, Optional

import aiohttp

from ..core.logging import get_logger, LoggerMixin

log = get_logger(__name__)


class RegistryClientError(RuntimeError):
    """Raised when registry API calls fail."""


class RegistryClient(LoggerMixin):
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
        
        self.logger.info("Initializing Registry client for %s", self.registry_url)
        self.logger.debug("Authentication: %s", "token provided" if auth_token else "none")
        self.logger.debug("SSL verification: %s", "enabled" if verify_ssl else "disabled")
        self.logger.debug("Timeout: %ss", timeout if timeout else "unlimited")
        
        if not verify_ssl:
            self.logger.warning("SSL verification is disabled - not recommended for production")

    async def __aenter__(self) -> "RegistryClient":
        self.logger.debug("Starting Registry client session")
        
        if self.session is None:
            self.session = await self._create_session()
            self.logger.debug("Registry client session created")
        else:
            self.logger.debug("Reusing existing Registry client session")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type:
            self.logger.error("Registry client session ended with error: %s", exc_val)
        else:
            self.logger.debug("Registry client session ended normally")
        
        if self.session and self._external_session is None:
            await self.session.close()
            self.logger.debug("Registry client session closed")
            self.session = None

    async def _create_session(self) -> aiohttp.ClientSession:
        headers = {"Accept": "application/json"}

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
            error_msg = "Client session has not been initialised. Use 'async with RegistryClient(...)'."
            self.logger.error("❌ %s", error_msg)
            raise RegistryClientError(error_msg)

        url = f"{self.registry_url}{path}"
        start_time = time.time()
        
        # Log request details
        self.logger.debug("Registry API request: %s %s", method, path)
        if kwargs.get("json"):
            self.logger.debug("Request payload size: %d bytes", len(str(kwargs["json"])))

        try:
            async with self.session.request(method, url, **kwargs) as response:
                execution_time = (time.time() - start_time) * 1000
                
                # Log response details
                self.logger.debug("Registry API response: %d (%.2fms) %s", 
                                response.status, execution_time, response.content_type)
                
                # Check for errors before parsing response
                if response.status >= 400:
                    error_text = await response.text()
                    self.logger.error("Registry API error %d: %s", response.status, error_text)
                
                response.raise_for_status()
                
                # Log successful response
                self.logger.debug("Registry API success: %s %s -> %d", method, path, response.status)
                
                if response.content_type == "application/json":
                    result = await response.json()
                    if isinstance(result, list):
                        self.logger.debug("Response data: %d items", len(result))
                    elif isinstance(result, dict):
                        self.logger.debug("Response data: dict with %d keys", len(result))
                    else:
                        self.logger.debug("Response data: %s", type(result).__name__)
                    return result
                return await response.text()
                
        except aiohttp.ClientError as exc:
            execution_time = (time.time() - start_time) * 1000
            self.logger.error("Registry client request failed after %.2fms: %s %s - %s", 
                            execution_time, method, path, exc)
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

    # Additional Flow Operations
    async def list_flows(self, bucket_id: str) -> List[Dict[str, Any]]:
        """List all flows in a bucket."""
        
        result = await self._request("GET", f"/nifi-registry-api/buckets/{bucket_id}/flows")
        if not isinstance(result, list):
            raise RegistryClientError("Unexpected response listing flows")
        return result

    async def get_flow(self, bucket_id: str, flow_id: str) -> Dict[str, Any]:
        """Get flow metadata."""
        
        result = await self._request("GET", f"/nifi-registry-api/buckets/{bucket_id}/flows/{flow_id}")
        if not isinstance(result, dict):
            raise RegistryClientError("Unexpected response getting flow")
        return result

    async def get_latest_flow_version(self, bucket_id: str, flow_id: str) -> Dict[str, Any]:
        """Get the latest version of a flow."""
        
        result = await self._request("GET", f"/nifi-registry-api/buckets/{bucket_id}/flows/{flow_id}/versions/latest")
        if not isinstance(result, dict):
            raise RegistryClientError("Unexpected response getting latest flow version")
        return result

    async def list_flow_versions(self, bucket_id: str, flow_id: str) -> List[Dict[str, Any]]:
        """List all versions of a flow."""
        
        result = await self._request("GET", f"/nifi-registry-api/buckets/{bucket_id}/flows/{flow_id}/versions")
        if not isinstance(result, list):
            raise RegistryClientError("Unexpected response listing flow versions")
        return result

    async def delete_flow(self, bucket_id: str, flow_id: str) -> Dict[str, Any]:
        """Delete a flow and all its versions."""
        
        result = await self._request("DELETE", f"/nifi-registry-api/buckets/{bucket_id}/flows/{flow_id}")
        return result

    async def update_flow(self, bucket_id: str, flow_id: str, name: str = None, description: str = None) -> Dict[str, Any]:
        """Update flow metadata."""
        
        payload = {}
        if name is not None:
            payload["name"] = name
        if description is not None:
            payload["description"] = description
            
        result = await self._request("PUT", f"/nifi-registry-api/buckets/{bucket_id}/flows/{flow_id}", json=payload)
        if not isinstance(result, dict):
            raise RegistryClientError("Unexpected response updating flow")
        return result
