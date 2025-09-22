"""Test configuration helpers for local vs docker test environments."""

import os
from src.core.config import Settings


def get_test_settings() -> Settings:
    """Get test settings based on TEST_MODE environment variable."""
    test_mode = os.getenv("TEST_MODE", "docker")
    
    if test_mode == "local":
        # Local testing - connect to Docker services via localhost
        settings = Settings(
            # Use localhost URLs to connect to Docker services
            NIFI_URL="https://localhost:8443",
            NIFI_USERNAME="admin", 
            NIFI_PASSWORD="adminadmin123",  # Match docker-compose password
            NIFI_REGISTRY_URL="http://localhost:18080",
            NIFI_REGISTRY_AUTH_TOKEN="",  # Registry often doesn't need auth token
            VERIFY_SSL=False,  # Disable SSL verification for local testing
            DEBUG=True,
        )
    else:
        # Docker testing - use host.docker.internal URLs 
        # Note: This may have JWT audience validation issues for NiFi
        settings = Settings(
            # Use host.docker.internal for Docker networking
            NIFI_URL="https://host.docker.internal:8443",
            NIFI_USERNAME="admin",
            NIFI_PASSWORD="adminadmin123",  # Match docker-compose password
            NIFI_REGISTRY_URL="http://host.docker.internal:18080", 
            NIFI_REGISTRY_AUTH_TOKEN="",
            VERIFY_SSL=False,  # Disable SSL verification for testing
            DEBUG=True,
        )
    
    return settings