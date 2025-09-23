"""Dependency injection for flow services."""

from __future__ import annotations

from typing import AsyncGenerator

from src.clients.nifi_unified import NiFiUnifiedClient
from src.clients.registry_unified import RegistryUnifiedClient
from src.core.config import get_settings
from src.services.flow_service import FlowService

# Global instances (will be replaced with proper DI container in production)
_nifi_client: NiFiUnifiedClient | None = None
_registry_client: RegistryUnifiedClient | None = None
_flow_service: FlowService | None = None


async def get_nifi_client() -> AsyncGenerator[NiFiUnifiedClient, None]:
    """Get NiFi unified client instance."""
    global _nifi_client

    if _nifi_client is None:
        settings = get_settings()
        _nifi_client = NiFiUnifiedClient(
            nifi_url=settings.nifi_url,
            username=settings.nifi_username,
            password=settings.nifi_password,
            verify_ssl=settings.nifi_verify_ssl,
        )

    async with _nifi_client as client:
        yield client


async def get_registry_client() -> AsyncGenerator[RegistryUnifiedClient, None]:
    """Get Registry unified client instance."""
    global _registry_client

    if _registry_client is None:
        settings = get_settings()
        _registry_client = RegistryUnifiedClient(
            registry_url=settings.registry_url,
            auth_token=settings.registry_auth_token,
            verify_ssl=settings.registry_verify_ssl,
        )

    async with _registry_client as client:
        yield client


async def get_flow_service() -> FlowService:
    """Get flow service instance."""
    global _flow_service

    if _flow_service is None:
        settings = get_settings()

        # Create client instances
        nifi_client = NiFiUnifiedClient(
            nifi_url=settings.nifi_url,
            username=settings.nifi_username,
            password=settings.nifi_password,
            verify_ssl=settings.nifi_verify_ssl,
        )

        registry_client = RegistryUnifiedClient(
            registry_url=settings.registry_url,
            auth_token=settings.registry_auth_token,
            verify_ssl=settings.registry_verify_ssl,
        )

        _flow_service = FlowService(nifi_client, registry_client)

    return _flow_service


async def get_nifi_deployment_service():
    """Get NiFi deployment service instance."""
    service = await get_flow_service()
    return service.nifi_deployment


async def get_nifi_version_control_service():
    """Get NiFi version control service instance."""
    service = await get_flow_service()
    return service.nifi_version_control


async def get_registry_flow_service():
    """Get Registry flow service instance."""
    service = await get_flow_service()
    return service.registry_flows


# Cleanup function for application shutdown
async def cleanup_clients():
    """Cleanup client instances."""
    global _nifi_client, _registry_client, _flow_service

    if _nifi_client:
        await _nifi_client.__aexit__(None, None, None)
        _nifi_client = None

    if _registry_client:
        await _registry_client.__aexit__(None, None, None)
        _registry_client = None

    _flow_service = None