"""Configuration for minimal NiFi backend."""

import os
from typing import Optional


class Settings:
    """Application settings."""

    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/edi_lens"
    )

    # NiFi Configuration (simple HTTP)
    NIFI_URL: str = os.getenv("NIFI_URL", "http://localhost:8080")
    NIFI_USERNAME: Optional[str] = os.getenv("NIFI_USERNAME") or None
    NIFI_PASSWORD: Optional[str] = os.getenv("NIFI_PASSWORD") or None

    # NiFi Registry Configuration (simple HTTP)
    NIFI_REGISTRY_URL: str = os.getenv("NIFI_REGISTRY_URL", "http://localhost:18080")
    NIFI_REGISTRY_AUTH_TOKEN: Optional[str] = os.getenv("NIFI_REGISTRY_AUTH_TOKEN") or None

    # Development settings
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"


settings = Settings()