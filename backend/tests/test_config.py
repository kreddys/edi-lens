"""Test configuration helpers for local vs docker test environments."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from src.core.config import Settings
from src.clients.nifi_unified import NiFiUnifiedClient
from src.clients.registry_unified import RegistryUnifiedClient
from src.services.workflow_orchestrator import WorkflowOrchestrator


TESTS_ROOT = Path(__file__).resolve().parent
DEFAULT_ENV_FILES = {
    "local": TESTS_ROOT / "env" / "test.local.env",
    "docker": TESTS_ROOT / "env" / "test.docker.env",
}


def _resolve_env_file() -> Optional[Path]:
    """Resolve the environment file path for tests."""

    env_file = os.getenv("TEST_ENV_FILE")
    if env_file:
        return Path(env_file).expanduser().resolve()

    test_mode = os.getenv("TEST_MODE", "local").lower()
    default_file = DEFAULT_ENV_FILES.get(test_mode)
    if default_file and default_file.exists():
        return default_file

    return None


def get_test_settings() -> Settings:
    """Load test settings exclusively from environment configuration."""

    env_file = _resolve_env_file()
    kwargs = {}
    if env_file is not None:
        if not env_file.exists():
            raise FileNotFoundError(f"Test environment file not found: {env_file}")
        kwargs["_env_file"] = env_file
        kwargs["_env_file_encoding"] = "utf-8"

    return Settings(**kwargs)


def get_test_nifi_client() -> NiFiUnifiedClient:
    """Get a NiFi client configured for testing."""
    settings = get_test_settings()
    return NiFiUnifiedClient(
        nifi_url=settings.nifi_url,
        username=settings.nifi_username,
        password=settings.nifi_password,
        verify_ssl=settings.nifi_verify_ssl,
        host_header=settings.nifi_host_header,
    )


def get_test_registry_client() -> RegistryUnifiedClient:
    """Get a Registry client configured for testing."""
    settings = get_test_settings()
    return RegistryUnifiedClient(
        registry_url=settings.registry_url,
        auth_token=settings.registry_auth_token,
        verify_ssl=settings.registry_verify_ssl,
    )


def get_test_orchestrator() -> WorkflowOrchestrator:
    """Get a workflow orchestrator configured for testing."""
    nifi_client = get_test_nifi_client()
    registry_client = get_test_registry_client()
    return WorkflowOrchestrator(nifi_client, registry_client)
