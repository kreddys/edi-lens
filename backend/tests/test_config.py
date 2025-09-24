"""Test configuration helpers for local vs docker test environments."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from src.core.config import Settings
from src.clients.nifi_unified import NiFiUnifiedClient
from src.clients.registry_unified import RegistryUnifiedClient
from src.services.workflow_orchestrator import WorkflowOrchestrator


def get_test_settings() -> Settings:
    """Load test settings from .env.local for local testing."""
    import os
    from pathlib import Path
    
    # Use .env.local for local testing (has localhost URLs)
    project_root = Path(__file__).resolve().parents[2]
    env_local_file = project_root / ".env.local"
    
    if env_local_file.exists():
        # Load environment variables manually from .env.local
        original_env = os.environ.copy()
        try:
            # Load the .env.local file
            with open(env_local_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        os.environ[key.strip()] = value.strip()
            
            # Create settings with the loaded environment
            settings = Settings()
            return settings
        finally:
            # Restore original environment (optional, for cleanliness)
            pass
    else:
        # Fallback to main .env file if .env.local doesn't exist
        return Settings()


def get_test_nifi_client() -> NiFiUnifiedClient:
    """Get a NiFi client configured for testing."""
    settings = get_test_settings()
    return NiFiUnifiedClient(
        nifi_url=settings.nifi_url,
        username=settings.nifi_username,
        password=settings.nifi_password,
        verify_ssl=settings.nifi_verify_ssl,
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
