"""Test configuration helpers for local vs docker test environments."""

import os
from src.core.config import Settings
from src.clients.nifi_unified import NiFiUnifiedClient
from src.clients.registry_unified import RegistryUnifiedClient
from src.services.workflow_orchestrator import WorkflowOrchestrator


def get_test_settings() -> Settings:
    """Get test settings based on TEST_MODE environment variable."""
    test_mode = os.getenv("TEST_MODE", "local")

    if test_mode == "local":
        # Local testing - connect to Docker services via localhost
        settings = Settings(
            # Use localhost URLs to connect to Docker services
            nifi_url="https://localhost:8443",
            nifi_username="admin",
            nifi_password="adminadmin123",  # Match docker-compose password
            registry_url="http://localhost:18080",
            registry_auth_token="",  # Registry often doesn't need auth token
            nifi_verify_ssl=False,  # Disable SSL verification for local testing
            registry_verify_ssl=False,
            DEBUG=True,
        )
    else:
        # Docker testing - use host.docker.internal URLs
        settings = Settings(
            # Use host.docker.internal for Docker networking
            nifi_url="https://host.docker.internal:8443",
            nifi_username="admin",
            nifi_password="adminadmin123",  # Match docker-compose password
            registry_url="http://host.docker.internal:18080",
            registry_auth_token="",
            nifi_verify_ssl=False,  # Disable SSL verification for testing
            registry_verify_ssl=False,
            DEBUG=True,
        )

    return settings


def get_test_nifi_client() -> NiFiUnifiedClient:
    """Get a NiFi client configured for testing."""
    settings = get_test_settings()
    return NiFiUnifiedClient(
        nifi_url=settings.nifi_url,
        username=settings.nifi_username,
        password=settings.nifi_password,
        verify_ssl=False,  # Always disable SSL verification for testing
    )


def get_test_registry_client() -> RegistryUnifiedClient:
    """Get a Registry client configured for testing."""
    settings = get_test_settings()
    return RegistryUnifiedClient(
        registry_url=settings.registry_url,
        auth_token=settings.registry_auth_token,
        verify_ssl=False,  # Always disable SSL verification for testing
    )


def get_test_orchestrator() -> WorkflowOrchestrator:
    """Get a workflow orchestrator configured for testing."""
    nifi_client = get_test_nifi_client()
    registry_client = get_test_registry_client()
    return WorkflowOrchestrator(nifi_client, registry_client)