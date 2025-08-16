"""
Simple connectivity test to verify test setup.
"""

import pytest
import asyncio
from src.core.config import settings

pytestmark = pytest.mark.integration


class TestSimpleConnectivity:
    """Simple connectivity tests."""

    @pytest.mark.asyncio
    async def test_config_has_nifi_urls(self):
        """Test that NiFi URLs are configured correctly."""
        assert hasattr(settings, 'NIFI_URL')
        assert hasattr(settings, 'NIFI_REGISTRY_URL')
        assert settings.NIFI_URL.startswith('http')
        assert settings.NIFI_REGISTRY_URL.startswith('http')
        assert 'nifi' in settings.NIFI_URL.lower()
        assert 'registry' in settings.NIFI_REGISTRY_URL.lower()

    @pytest.mark.asyncio 
    async def test_database_connectivity(self):
        """Test database connectivity."""
        from src.core.database import get_db
        
        async for session in get_db():
            # Simple query to test connection
            from sqlalchemy import text
            result = await session.execute(text("SELECT 1"))
            assert result.scalar() == 1
            break  # Exit after first iteration

    @pytest.mark.asyncio
    async def test_keycloak_connectivity(self):
        """Test Keycloak connectivity using httpx."""
        import httpx
        
        # Test Keycloak root endpoint (health endpoint might not exist)
        keycloak_url = f"{settings.KEYCLOAK_URL}/realms/edi-lens"
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(keycloak_url, timeout=5.0)
                # Realm endpoint should return 200
                assert response.status_code == 200
            except httpx.RequestError:
                pytest.skip("Keycloak not accessible for connectivity test")