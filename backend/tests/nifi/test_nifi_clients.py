"""
Unit tests for NiFi integration clients.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.nifi.clients.registry_client import NiFiRegistryClient
from src.nifi.clients.nifi_client import NiFiAPIClient

pytestmark = pytest.mark.unit


class TestNiFiRegistryClient:
    """Test NiFi Registry Client."""

    @pytest.fixture
    def registry_client(self):
        """Create a registry client fixture."""
        return NiFiRegistryClient("http://localhost:18080", "test-token")

    @pytest.mark.asyncio
    async def test_registry_client_initialization(self):
        """Test registry client initialization."""
        client = NiFiRegistryClient("http://localhost:18080", "test-token")
        assert client.registry_url == "http://localhost:18080"
        assert client.auth_token == "test-token"

    @pytest.mark.asyncio
    async def test_registry_client_context_manager(self):
        """Test registry client context manager."""
        client = NiFiRegistryClient("http://localhost:18080", "test-token")
        
        async with client as ctx:
            assert ctx is client
            assert client.session is not None

    @patch('aiohttp.ClientSession')
    @pytest.mark.asyncio
    async def test_list_buckets(self, mock_session_class):
        """Test listing buckets."""
        # Setup mock session
        mock_response = AsyncMock()
        mock_response.json.return_value = [
            {"identifier": "bucket1", "name": "Bucket 1"},
            {"identifier": "bucket2", "name": "Bucket 2"}
        ]
        mock_response.raise_for_status.return_value = None
        
        mock_session = AsyncMock()
        mock_session.get.return_value.__aenter__.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        # Test
        async with NiFiRegistryClient("http://localhost:18080") as client:
            buckets = await client.list_buckets()
            assert len(buckets) == 2
            assert buckets[0]["name"] == "Bucket 1"


class TestNiFiAPIClient:
    """Test NiFi API Client."""

    @pytest.mark.asyncio
    async def test_nifi_client_initialization(self):
        """Test NiFi API client initialization."""
        client = NiFiAPIClient("http://localhost:8080", "test-token")
        assert client.nifi_url == "http://localhost:8080"
        assert client.auth_token == "test-token"

    @pytest.mark.asyncio
    async def test_nifi_client_context_manager(self):
        """Test NiFi API client context manager."""
        client = NiFiAPIClient("http://localhost:8080", "test-token")
        
        async with client as ctx:
            assert ctx is client
            assert client.session is not None

    @patch('aiohttp.ClientSession')
    @pytest.mark.asyncio
    async def test_health_check(self, mock_session_class):
        """Test health check."""
        # Setup mock session
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.raise_for_status.return_value = None
        
        mock_session = AsyncMock()
        mock_session.get.return_value.__aenter__.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        # Test
        async with NiFiAPIClient("http://localhost:8080") as client:
            is_healthy = await client.health_check()
            assert is_healthy is True