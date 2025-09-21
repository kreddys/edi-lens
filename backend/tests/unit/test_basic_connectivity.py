"""
Basic connectivity tests for NiFi and Registry clients.

These tests use mocks and don't require actual NiFi/Registry instances.
"""

import pytest
from unittest.mock import AsyncMock, patch

from src.clients.nifi_client import NiFiClient
from src.clients.registry_client import RegistryClient


class TestNiFiClient:
    """Test NiFi client basic functionality."""

    @pytest.mark.asyncio
    async def test_nifi_client_initialization(self):
        """Test NiFi client can be initialized."""
        client = NiFiClient("http://localhost:8080")
        assert client.nifi_url == "http://localhost:8080"
        assert client.username is None
        assert client.password is None
        assert client.verify_ssl is True

    @pytest.mark.asyncio
    async def test_nifi_client_with_auth(self):
        """Test NiFi client with authentication."""
        client = NiFiClient("http://localhost:8080", "user", "pass")
        assert client.username == "user"
        assert client.password == "pass"

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """Test successful health check."""
        client = NiFiClient("http://localhost:8080")

        with patch.object(client, 'get_root_process_group', new_callable=AsyncMock) as mock_summary:
            mock_summary.return_value = {"component": {"id": "root"}}

            async with client:
                result = await client.health_check()
                assert result is True
                mock_summary.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        """Test health check failure."""
        client = NiFiClient("http://localhost:8080")

        with patch.object(client, 'get_root_process_group', new_callable=AsyncMock) as mock_summary:
            mock_summary.side_effect = Exception("Connection failed")

            async with client:
                result = await client.health_check()
                assert result is False


class TestRegistryClient:
    """Test Registry client basic functionality."""

    @pytest.mark.asyncio
    async def test_registry_client_initialization(self):
        """Test Registry client can be initialized."""
        client = RegistryClient("http://localhost:18080")
        assert client.registry_url == "http://localhost:18080"
        assert client.auth_token is None
        assert client.verify_ssl is True

    @pytest.mark.asyncio
    async def test_registry_client_with_token(self):
        """Test Registry client with auth token."""
        client = RegistryClient("http://localhost:18080", "token123")
        assert client.auth_token == "token123"

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """Test successful health check."""
        client = RegistryClient("http://localhost:18080")

        with patch.object(client, 'get_registry_info', new_callable=AsyncMock) as mock_info:
            mock_info.return_value = {"registryId": "test-registry"}

            async with client:
                result = await client.health_check()
                assert result is True
                mock_info.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        """Test health check failure."""
        client = RegistryClient("http://localhost:18080")

        with patch.object(client, 'get_registry_info', new_callable=AsyncMock) as mock_info:
            mock_info.side_effect = Exception("Connection failed")

            async with client:
                result = await client.health_check()
                assert result is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
