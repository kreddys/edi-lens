"""Health and root endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ...clients.nifi_client import NiFiClient
from ...clients.registry_client import RegistryClient
from ...core.config import Settings, get_settings
from ...models.health import ApplicationHealthResponse, RootResponse, ServiceHealthResponse
from ..dependencies import get_nifi_client, get_registry_client

router = APIRouter(tags=["health"])


@router.get("/", response_model=RootResponse, tags=["system"])
async def root(settings: Settings = Depends(get_settings)) -> RootResponse:
    """Root endpoint."""

    return RootResponse(
        message="EDI Lens NiFi Backend - Minimal Architecture",
        version=settings.APP_VERSION,
        status="healthy",
    )


@router.get("/health", response_model=ApplicationHealthResponse)
async def health(settings: Settings = Depends(get_settings)) -> ApplicationHealthResponse:
    """Health check endpoint."""

    return ApplicationHealthResponse(
        status="healthy",
        nifi_url=settings.NIFI_URL,
        registry_url=settings.NIFI_REGISTRY_URL,
        debug=settings.DEBUG,
    )


@router.get("/health/nifi", response_model=ServiceHealthResponse)
async def health_nifi(
    nifi_client: NiFiClient = Depends(get_nifi_client),
    settings: Settings = Depends(get_settings),
) -> ServiceHealthResponse:
    """NiFi connectivity check."""

    is_healthy = await nifi_client.health_check()
    return ServiceHealthResponse(
        service="nifi",
        url=settings.NIFI_URL,
        healthy=is_healthy,
    )


@router.get("/health/registry", response_model=ServiceHealthResponse)
async def health_registry(
    registry_client: RegistryClient = Depends(get_registry_client),
    settings: Settings = Depends(get_settings),
) -> ServiceHealthResponse:
    """Registry connectivity check."""

    is_healthy = await registry_client.health_check()
    return ServiceHealthResponse(
        service="registry",
        url=settings.NIFI_REGISTRY_URL,
        healthy=is_healthy,
    )
