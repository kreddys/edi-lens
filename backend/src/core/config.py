"""Application configuration powered by Pydantic settings."""

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Centralised application settings with environment overrides."""

    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/edi_lens",
        description="Async SQLAlchemy connection string",
    )

    # Application metadata
    APP_VERSION: str = Field(default="0.1.0")

    # NiFi Configuration
    NIFI_URL: str = Field(default="https://localhost:8443")
    NIFI_USERNAME: Optional[str] = Field(default=None)
    NIFI_PASSWORD: Optional[str] = Field(default=None)

    # NiFi Registry Configuration
    NIFI_REGISTRY_URL: str = Field(default="http://localhost:18080")
    NIFI_REGISTRY_AUTH_TOKEN: Optional[str] = Field(default=None)

    # HTTP client behaviour
    VERIFY_SSL: bool = Field(
        default=True,
        description="Control client-side TLS verification for NiFi services",
    )

    # Development flags
    DEBUG: bool = Field(default=False)
    
    # Logging configuration
    LOG_LEVEL: str = Field(default="INFO", description="Application log level")
    LOG_FORMAT: str = Field(default="detailed", description="Log format: simple, detailed, json")
    LOG_TO_FILE: bool = Field(default=True, description="Enable file logging")
    LOG_FILE_MAX_SIZE: int = Field(default=10485760, description="Max log file size in bytes")
    LOG_FILE_BACKUP_COUNT: int = Field(default=5, description="Number of log file backups")

    # Component-specific logging levels
    LOG_LEVEL_CONSOLE: Optional[str] = Field(default=None, description="Console log level override")
    LOG_LEVEL_FILE: Optional[str] = Field(default=None, description="File log level override")
    LOG_LEVEL_CLIENTS: Optional[str] = Field(default=None, description="Client logging level")
    LOG_LEVEL_SERVICES: Optional[str] = Field(default=None, description="Service logging level")
    LOG_LEVEL_API: Optional[str] = Field(default=None, description="API logging level")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings instance."""

    return Settings()


settings = get_settings()
