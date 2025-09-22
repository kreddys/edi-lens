"""Reusable FastAPI dependencies."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from fastapi import Depends

from ..clients.nifi_client import NiFiClient
from ..clients.registry_client import RegistryClient
from ..core.config import Settings, get_settings
from ..services.flow_service import FlowService


async def get_nifi_client(
    settings: Settings = Depends(get_settings),
) -> AsyncGenerator[NiFiClient, None]:
    """Provide a NiFi client configured from application settings."""

    async with NiFiClient(
        settings.NIFI_URL,
        settings.NIFI_USERNAME,
        settings.NIFI_PASSWORD,
        verify_ssl=settings.VERIFY_SSL,
    ) as client:
        yield client


async def get_registry_client(
    settings: Settings = Depends(get_settings),
) -> AsyncGenerator[RegistryClient, None]:
    """Provide a NiFi Registry client configured from application settings."""

    async with RegistryClient(
        settings.NIFI_REGISTRY_URL,
        settings.NIFI_REGISTRY_AUTH_TOKEN,
        verify_ssl=settings.VERIFY_SSL,
    ) as client:
        yield client


async def get_flow_service(
    nifi_client: NiFiClient = Depends(get_nifi_client),
    registry_client: RegistryClient = Depends(get_registry_client),
) -> FlowService:
    """Provide a configured FlowService instance."""
    return FlowService(nifi_client=nifi_client, registry_client=registry_client)
