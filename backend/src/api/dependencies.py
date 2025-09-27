"""Dependency injection for flow services."""

from __future__ import annotations

from typing import AsyncGenerator

from src.clients.nifi_unified import NiFiUnifiedClient
from src.clients.registry_unified import RegistryUnifiedClient
from src.core.config import get_settings
from src.services.workflow_orchestrator import WorkflowOrchestrator
from src.services.flow_template_service import FlowTemplateService

# Global instances (will be replaced with proper DI container in production)
_nifi_client: NiFiUnifiedClient | None = None
_registry_client: RegistryUnifiedClient | None = None
_workflow_orchestrator: WorkflowOrchestrator | None = None


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
        # Initialize the session once
        await _nifi_client.__aenter__()

    yield _nifi_client


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
        # Initialize the session once
        await _registry_client.__aenter__()

    yield _registry_client


async def get_workflow_orchestrator() -> WorkflowOrchestrator:
    """Get workflow orchestrator instance."""
    global _workflow_orchestrator, _nifi_client, _registry_client

    if _workflow_orchestrator is None:
        # Use the same client instances as the individual dependencies
        # This ensures consistent session management
        if _nifi_client is None:
            async for client in get_nifi_client():
                _nifi_client = client
                break

        if _registry_client is None:
            async for client in get_registry_client():
                _registry_client = client
                break

        _workflow_orchestrator = WorkflowOrchestrator(_nifi_client, _registry_client)

    return _workflow_orchestrator


# Backward compatibility alias
async def get_flow_service() -> WorkflowOrchestrator:
    """Get workflow orchestrator instance (backward compatibility)."""
    return await get_workflow_orchestrator()


def get_flow_template_service() -> FlowTemplateService:
    """Get flow template service instance."""
    return FlowTemplateService()


# Cleanup function for application shutdown
async def cleanup_clients():
    """Cleanup client instances."""
    global _nifi_client, _registry_client, _workflow_orchestrator

    if _nifi_client:
        await _nifi_client.__aexit__(None, None, None)
        _nifi_client = None

    if _registry_client:
        await _registry_client.__aexit__(None, None, None)
        _registry_client = None

    _workflow_orchestrator = None