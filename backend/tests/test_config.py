"""Utilities for constructing real clients in the test environment."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from src.core.config import Settings
from src.clients.nifi_unified import NiFiUnifiedClient
from src.clients.registry_unified import RegistryUnifiedClient
from src.services.workflow_orchestrator import WorkflowOrchestrator


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@lru_cache(maxsize=1)
def get_test_settings() -> Settings:
    """Load settings for tests, preferring `.env.local` when available."""

    env_file = PROJECT_ROOT / ".env.local"
    if env_file.exists():
        return Settings(_env_file=env_file, _env_file_encoding="utf-8")
    return Settings()


def get_test_nifi_client() -> NiFiUnifiedClient:
    """Instantiate a NiFi client configured from the test settings."""

    settings = get_test_settings()
    return NiFiUnifiedClient(
        nifi_url=settings.nifi_url,
        username=settings.nifi_username,
        password=settings.nifi_password,
        verify_ssl=settings.nifi_verify_ssl,
    )


def get_test_registry_client() -> RegistryUnifiedClient:
    """Instantiate a Registry client configured from the test settings."""

    settings = get_test_settings()
    return RegistryUnifiedClient(
        registry_url=settings.registry_url,
        auth_token=settings.registry_auth_token,
        verify_ssl=settings.registry_verify_ssl,
    )


def get_test_orchestrator() -> WorkflowOrchestrator:
    """Convenience helper for creating an orchestrator backed by real clients."""

    nifi_client = get_test_nifi_client()
    registry_client = get_test_registry_client()
    return WorkflowOrchestrator(nifi_client, registry_client)
