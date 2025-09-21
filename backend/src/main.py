"""
Minimal FastAPI application for NiFi workflow management.

This is the starting point - basic health checks and connectivity tests.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import settings
from .clients.nifi_client import NiFiClient
from .clients.registry_client import RegistryClient

app = FastAPI(
    title="EDI Lens NiFi Backend",
    description="Minimal NiFi workflow management backend",
    version="0.1.0"
)

# CORS middleware for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "EDI Lens NiFi Backend - Minimal Architecture",
        "version": "0.1.0",
        "status": "healthy"
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "nifi_url": settings.NIFI_URL,
        "registry_url": settings.NIFI_REGISTRY_URL,
        "debug": settings.DEBUG
    }


@app.get("/health/nifi")
async def health_nifi():
    """NiFi connectivity check."""
    async with NiFiClient(settings.NIFI_URL, settings.NIFI_USERNAME, settings.NIFI_PASSWORD) as client:
        is_healthy = await client.health_check()
        return {
            "service": "nifi",
            "url": settings.NIFI_URL,
            "healthy": is_healthy
        }


@app.get("/health/registry")
async def health_registry():
    """Registry connectivity check."""
    async with RegistryClient(settings.NIFI_REGISTRY_URL, settings.NIFI_REGISTRY_AUTH_TOKEN) as client:
        is_healthy = await client.health_check()
        return {
            "service": "registry",
            "url": settings.NIFI_REGISTRY_URL,
            "healthy": is_healthy
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)