"""Unified NiFi client that combines all specialized clients."""

from __future__ import annotations

from typing import Optional

import aiohttp

from ..core.logging import get_logger, LoggerMixin
from .nifi_base import NiFiBaseClient
from .nifi_connections import NiFiConnectionClient
from .nifi_parameter_contexts import NiFiParameterContextClient
from .nifi_process_groups import NiFiProcessGroupClient
from .nifi_processors import NiFiProcessorClient
from .nifi_version_control import NiFiVersionControlClient

log = get_logger(__name__)


class NiFiUnifiedClient(LoggerMixin):
    """Unified NiFi client providing access to all NiFi operations."""

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
        self.base = NiFiBaseClient(
            nifi_url=nifi_url,
            username=username,
            password=password,
            session=session,
            verify_ssl=verify_ssl,
            timeout=timeout,
        )

        # Initialize specialized clients
        self.process_groups = NiFiProcessGroupClient(self.base)
        self.processors = NiFiProcessorClient(self.base)
        self.connections = NiFiConnectionClient(self.base)
        self.parameter_contexts = NiFiParameterContextClient(self.base)
        self.version_control = NiFiVersionControlClient(self.base)

        self.logger.info("Initialized unified NiFi client for %s", nifi_url)

    async def __aenter__(self) -> "NiFiUnifiedClient":
        await self.base.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.base.__aexit__(exc_type, exc_val, exc_tb)

    # Convenience methods for common operations
    async def get_root_process_group(self):
        """Get the root process group."""
        return await self.base.get("/flow/process-groups/root")

    async def get_system_diagnostics(self):
        """Get system diagnostics."""
        return await self.base.get("/system-diagnostics")

    async def get_about_info(self):
        """Get NiFi about information."""
        return await self.base.get("/flow/about")

    async def health_check(self) -> bool:
        """Check if NiFi is healthy and accessible."""
        try:
            await self.base.get("/flow/about")
            return True
        except Exception:
            return False