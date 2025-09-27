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
        env_file=ROOT_DIR / ".env.local",
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
    nifi_url: str = Field(default="https://localhost:8443", alias="NIFI_URL")
    nifi_username: Optional[str] = Field(default=None, alias="NIFI_USERNAME")
    nifi_password: Optional[str] = Field(default=None, alias="NIFI_PASSWORD")
    nifi_verify_ssl: bool = Field(default=True, alias="NIFI_VERIFY_SSL")

    # NiFi Registry Configuration
    registry_url: str = Field(default="http://localhost:18080", alias="NIFI_REGISTRY_URL")
    registry_auth_token: Optional[str] = Field(default=None, alias="NIFI_REGISTRY_AUTH_TOKEN")
    registry_verify_ssl: bool = Field(default=True, alias="REGISTRY_VERIFY_SSL")

    # Development flags
    DEBUG: bool = Field(default=False)
    
    # Flow Templates Configuration
    FLOW_TEMPLATES_DIR: str = Field(default="data/flows", description="Directory containing flow templates")
    
    # Component-specific logging levels (used by logging.py)
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
