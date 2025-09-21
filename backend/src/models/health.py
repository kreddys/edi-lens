"""Pydantic response models for health endpoints."""

from pydantic import BaseModel, ConfigDict


class RootResponse(BaseModel):
    """Response payload for the API root."""

    model_config = ConfigDict(from_attributes=True)

    message: str
    version: str
    status: str


class ApplicationHealthResponse(BaseModel):
    """Application health payload."""

    model_config = ConfigDict(from_attributes=True)

    status: str
    nifi_url: str
    registry_url: str
    debug: bool


class ServiceHealthResponse(BaseModel):
    """Per-service health payload."""

    model_config = ConfigDict(from_attributes=True)

    service: str
    url: str
    healthy: bool
