"""Unified Registry client that combines all specialized clients."""

from __future__ import annotations

from typing import Optional

import aiohttp

from ..core.logging import get_logger, LoggerMixin
from .registry_base import RegistryBaseClient
from .registry_buckets import RegistryBucketClient
from .registry_flows import RegistryFlowClient

log = get_logger(__name__)


class RegistryUnifiedClient(LoggerMixin):
    """Unified Registry client providing access to all Registry operations."""

    def __init__(
        self,
        registry_url: str,
        auth_token: Optional[str] = None,
        *,
        session: Optional[aiohttp.ClientSession] = None,
        verify_ssl: bool = True,
        timeout: Optional[float] = 30,
    ):
        self.base = RegistryBaseClient(
            registry_url=registry_url,
            auth_token=auth_token,
            session=session,
            verify_ssl=verify_ssl,
            timeout=timeout,
        )

        # Initialize specialized clients
        self.buckets = RegistryBucketClient(self.base)
        self.flows = RegistryFlowClient(self.base)

        self.logger.info("Initialized unified Registry client for %s", registry_url)

    async def __aenter__(self) -> "RegistryUnifiedClient":
        await self.base.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.base.__aexit__(exc_type, exc_val, exc_tb)

    # Convenience methods for common operations
    async def get_about_info(self):
        """Get Registry about information."""
        return await self.base.get("/about")

    async def get_config(self):
        """Get Registry configuration."""
        return await self.base.get("/config")

    async def health_check(self) -> bool:
        """Check if Registry is healthy and accessible."""
        try:
            await self.base.get("/about")
            return True
        except Exception:
            return False