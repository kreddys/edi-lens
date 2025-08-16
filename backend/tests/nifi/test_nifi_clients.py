"""
Unit tests for NiFi integration clients.
"""

import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from aiohttp import ClientResponse, ClientSession

from src.nifi.clients.registry_client import NiFiRegistryClient
from src.nifi.clients.nifi_client import NiFiAPIClient

pytestmark = pytest.mark.unit


class TestNiFiRegistryClient:
    """Test NiFi Registry Client."""

    @pytest.fixture
    def mock_response(self):
        """Create a mock aiohttp response."""
        response = MagicMock(spec=ClientResponse)
        response.status = 200
        response.raise_for_status = MagicMock()
        return response

    @pytest.mark.asyncio
    async def test_registry_client_initialization(self):
        """Test registry client initialization."""
        client = NiFiRegistryClient("http://localhost:18080", "test-token")
        assert client.registry_url == "http://localhost:18080"
        assert client.auth_token == "test-token"
        assert client.session is None

    @pytest.mark.asyncio
    async def test_registry_client_initialization_no_auth(self):
        """Test registry client initialization without auth token."""
        client = NiFiRegistryClient("http://localhost:18080")
        assert client.registry_url == "http://localhost:18080"
        assert client.auth_token is None

    @pytest.mark.asyncio
    async def test_registry_client_url_normalization(self):
        """Test URL normalization removes trailing slash."""
        client = NiFiRegistryClient("http://localhost:18080/")
        assert client.registry_url == "http://localhost:18080"

    @pytest.mark.asyncio
    async def test_registry_client_context_manager(self):
        """Test registry client context manager."""
        client = NiFiRegistryClient("http://localhost:18080", "test-token")
        
        async with client as ctx:
            assert ctx is client
            assert client.session is not None
            assert isinstance(client.session, ClientSession)

    @pytest.mark.asyncio
    async def test_list_buckets_success(self):
        """Test successful bucket listing."""
        expected_buckets = [
            {"identifier": "bucket1", "name": "Test Bucket 1"},
            {"identifier": "bucket2", "name": "Test Bucket 2"}
        ]
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.json.return_value = expected_buckets
            mock_response.raise_for_status.return_value = None
            mock_get.return_value.__aenter__.return_value = mock_response
            
            client = NiFiRegistryClient("http://localhost:18080")
            async with client:
                result = await client.list_buckets()
                
                assert result == expected_buckets
                mock_get.assert_called_once_with("http://localhost:18080/nifi-registry-api/buckets")

    @pytest.mark.asyncio
    async def test_create_bucket_success(self):
        """Test successful bucket creation."""
        expected_bucket = {"identifier": "new-bucket", "name": "New Bucket"}
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.json.return_value = expected_bucket
            mock_response.raise_for_status.return_value = None
            mock_post.return_value.__aenter__.return_value = mock_response
            
            client = NiFiRegistryClient("http://localhost:18080")
            async with client:
                result = await client.create_bucket("New Bucket", "Test bucket")
                
                assert result == expected_bucket
                mock_post.assert_called_once()
                args, kwargs = mock_post.call_args
                assert args[0] == "http://localhost:18080/nifi-registry-api/buckets"
                assert "json" in kwargs

    @pytest.mark.asyncio
    async def test_get_bucket_success(self):
        """Test successful bucket retrieval."""
        expected_bucket = {"identifier": "bucket1", "name": "Test Bucket"}
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.json.return_value = expected_bucket
            mock_response.raise_for_status.return_value = None
            mock_get.return_value.__aenter__.return_value = mock_response
            
            client = NiFiRegistryClient("http://localhost:18080")
            async with client:
                result = await client.get_bucket("bucket1")
                
                assert result == expected_bucket
                mock_get.assert_called_once_with("http://localhost:18080/nifi-registry-api/buckets/bucket1")

    @pytest.mark.asyncio
    async def test_delete_bucket_success(self):
        """Test successful bucket deletion."""
        with patch('aiohttp.ClientSession.delete') as mock_delete:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.raise_for_status.return_value = None
            mock_delete.return_value.__aenter__.return_value = mock_response
            
            client = NiFiRegistryClient("http://localhost:18080")
            async with client:
                result = await client.delete_bucket("bucket1")
                
                assert result is True
                mock_delete.assert_called_once_with("http://localhost:18080/nifi-registry-api/buckets/bucket1")

    @pytest.mark.asyncio
    async def test_create_flow_success(self):
        """Test successful flow creation."""
        expected_flow = {"identifier": "flow1", "name": "Test Flow"}
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.json.return_value = expected_flow
            mock_response.raise_for_status.return_value = None
            mock_post.return_value.__aenter__.return_value = mock_response
            
            client = NiFiRegistryClient("http://localhost:18080")
            async with client:
                result = await client.create_flow("bucket1", "Test Flow", "Test flow description")
                
                assert result == expected_flow
                mock_post.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_flows_success(self):
        """Test successful flow listing."""
        expected_flows = [
            {"identifier": "flow1", "name": "Flow 1"},
            {"identifier": "flow2", "name": "Flow 2"}
        ]
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.json.return_value = expected_flows
            mock_response.raise_for_status.return_value = None
            mock_get.return_value.__aenter__.return_value = mock_response
            
            client = NiFiRegistryClient("http://localhost:18080")
            async with client:
                result = await client.list_flows("bucket1")
                
                assert result == expected_flows
                mock_get.assert_called_once_with("http://localhost:18080/nifi-registry-api/buckets/bucket1/flows")

    @pytest.mark.asyncio
    async def test_get_registry_info_success(self):
        """Test successful registry info retrieval."""
        expected_info = {"buildInfo": {"version": "1.23.2"}}
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.json.return_value = expected_info
            mock_response.raise_for_status.return_value = None
            mock_get.return_value.__aenter__.return_value = mock_response
            
            client = NiFiRegistryClient("http://localhost:18080")
            async with client:
                result = await client.get_registry_info()
                
                assert result == expected_info
                mock_get.assert_called_once_with("http://localhost:18080/nifi-registry-api/config")

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """Test successful health check."""
        expected_health = {"status": "UP"}
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.json.return_value = expected_health
            mock_response.raise_for_status.return_value = None
            mock_get.return_value.__aenter__.return_value = mock_response
            
            client = NiFiRegistryClient("http://localhost:18080")
            async with client:
                result = await client.health_check()
                
                assert result == expected_health
                mock_get.assert_called_once_with("http://localhost:18080/nifi-registry-api/health")


class TestNiFiAPIClient:
    """Test NiFi API Client."""

    @pytest.mark.asyncio
    async def test_nifi_client_initialization(self):
        """Test NiFi API client initialization."""
        client = NiFiAPIClient("http://localhost:8080", "test-token")
        assert client.nifi_url == "http://localhost:8080"
        assert client.auth_token == "test-token"
        assert client.session is None

    @pytest.mark.asyncio
    async def test_nifi_client_initialization_no_auth(self):
        """Test NiFi API client initialization without auth token."""
        client = NiFiAPIClient("http://localhost:8080")
        assert client.nifi_url == "http://localhost:8080"
        assert client.auth_token is None

    @pytest.mark.asyncio
    async def test_nifi_client_url_normalization(self):
        """Test URL normalization removes trailing slash."""
        client = NiFiAPIClient("http://localhost:8080/")
        assert client.nifi_url == "http://localhost:8080"

    @pytest.mark.asyncio
    async def test_nifi_client_context_manager(self):
        """Test NiFi API client context manager."""
        client = NiFiAPIClient("http://localhost:8080", "test-token")
        
        async with client as ctx:
            assert ctx is client
            assert client.session is not None
            assert isinstance(client.session, ClientSession)

    @pytest.mark.asyncio
    async def test_create_process_group_success(self):
        """Test successful process group creation."""
        expected_pg = {
            "component": {
                "id": "pg-123",
                "name": "Test Process Group"
            }
        }
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.json.return_value = expected_pg
            mock_response.raise_for_status.return_value = None
            mock_post.return_value.__aenter__.return_value = mock_response
            
            client = NiFiAPIClient("http://localhost:8080")
            async with client:
                result = await client.create_process_group(
                    "root", 
                    "Test Process Group", 
                    {"x": 100, "y": 100}
                )
                
                assert result == expected_pg
                mock_post.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_process_group_success(self):
        """Test successful process group retrieval."""
        expected_pg = {
            "component": {
                "id": "root",
                "name": "NiFi Flow"
            }
        }
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.json.return_value = expected_pg
            mock_response.raise_for_status.return_value = None
            mock_get.return_value.__aenter__.return_value = mock_response
            
            client = NiFiAPIClient("http://localhost:8080")
            async with client:
                result = await client.get_process_group("root")
                
                assert result == expected_pg
                mock_get.assert_called_once_with("http://localhost:8080/nifi-api/process-groups/root")

    @pytest.mark.asyncio
    async def test_delete_process_group_success(self):
        """Test successful process group deletion."""
        with patch('aiohttp.ClientSession.delete') as mock_delete:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.raise_for_status.return_value = None
            mock_delete.return_value.__aenter__.return_value = mock_response
            
            client = NiFiAPIClient("http://localhost:8080")
            async with client:
                result = await client.delete_process_group("pg-123", version=1)
                
                assert result is True
                mock_delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_process_group_success(self):
        """Test successful process group start."""
        expected_result = {"component": {"state": "RUNNING"}}
        
        with patch('aiohttp.ClientSession.put') as mock_put:
            mock_response = AsyncMock()
            mock_response.json.return_value = expected_result
            mock_response.raise_for_status.return_value = None
            mock_put.return_value.__aenter__.return_value = mock_response
            
            client = NiFiAPIClient("http://localhost:8080")
            async with client:
                result = await client.start_process_group("pg-123")
                
                assert result == expected_result
                mock_put.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_process_group_success(self):
        """Test successful process group stop."""
        expected_result = {"component": {"state": "STOPPED"}}
        
        with patch('aiohttp.ClientSession.put') as mock_put:
            mock_response = AsyncMock()
            mock_response.json.return_value = expected_result
            mock_response.raise_for_status.return_value = None
            mock_put.return_value.__aenter__.return_value = mock_response
            
            client = NiFiAPIClient("http://localhost:8080")
            async with client:
                result = await client.stop_process_group("pg-123")
                
                assert result == expected_result
                mock_put.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_parameter_context_success(self):
        """Test successful parameter context creation."""
        expected_context = {
            "component": {
                "id": "pc-123",
                "name": "Test Context"
            }
        }
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.json.return_value = expected_context
            mock_response.raise_for_status.return_value = None
            mock_post.return_value.__aenter__.return_value = mock_response
            
            client = NiFiAPIClient("http://localhost:8080")
            async with client:
                result = await client.create_parameter_context(
                    "Test Context",
                    [{"name": "test.param", "value": "test.value"}]
                )
                
                assert result == expected_context
                mock_post.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_parameter_context_success(self):
        """Test successful parameter context retrieval."""
        expected_context = {
            "component": {
                "id": "pc-123",
                "name": "Test Context",
                "parameters": []
            }
        }
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.json.return_value = expected_context
            mock_response.raise_for_status.return_value = None
            mock_get.return_value.__aenter__.return_value = mock_response
            
            client = NiFiAPIClient("http://localhost:8080")
            async with client:
                result = await client.get_parameter_context("pc-123")
                
                assert result == expected_context
                mock_get.assert_called_once_with("http://localhost:8080/nifi-api/parameter-contexts/pc-123")

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """Test successful health check."""
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.raise_for_status.return_value = None
            mock_get.return_value.__aenter__.return_value = mock_response
            
            client = NiFiAPIClient("http://localhost:8080")
            async with client:
                result = await client.health_check()
                
                assert result is True
                mock_get.assert_called_once_with("http://localhost:8080/nifi-api/system-diagnostics")

    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        """Test health check failure."""
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.raise_for_status.side_effect = Exception("Connection error")
            mock_get.return_value.__aenter__.return_value = mock_response
            
            client = NiFiAPIClient("http://localhost:8080")
            async with client:
                result = await client.health_check()
                
                assert result is False

    @pytest.mark.asyncio
    async def test_get_system_diagnostics_success(self):
        """Test successful system diagnostics retrieval."""
        expected_diagnostics = {
            "systemDiagnostics": {
                "aggregateSnapshot": {
                    "totalFlowFiles": 100,
                    "totalBytes": 1024000
                }
            }
        }
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.json.return_value = expected_diagnostics
            mock_response.raise_for_status.return_value = None
            mock_get.return_value.__aenter__.return_value = mock_response
            
            client = NiFiAPIClient("http://localhost:8080")
            async with client:
                result = await client.get_system_diagnostics()
                
                assert result == expected_diagnostics
                mock_get.assert_called_once_with("http://localhost:8080/nifi-api/system-diagnostics")

    @pytest.mark.asyncio
    async def test_get_flow_status_success(self):
        """Test successful flow status retrieval."""
        expected_status = {
            "controllerStatus": {
                "activeThreadCount": 10,
                "queued": "15 / 1.5 MB"
            }
        }
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.json.return_value = expected_status
            mock_response.raise_for_status.return_value = None
            mock_get.return_value.__aenter__.return_value = mock_response
            
            client = NiFiAPIClient("http://localhost:8080")
            async with client:
                result = await client.get_flow_status()
                
                assert result == expected_status
                mock_get.assert_called_once_with("http://localhost:8080/nifi-api/flow/status")

    @pytest.mark.asyncio
    async def test_list_templates_success(self):
        """Test successful template listing."""
        expected_templates = {
            "templates": [
                {"id": "template1", "name": "Template 1"},
                {"id": "template2", "name": "Template 2"}
            ]
        }
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.json.return_value = expected_templates
            mock_response.raise_for_status.return_value = None
            mock_get.return_value.__aenter__.return_value = mock_response
            
            client = NiFiAPIClient("http://localhost:8080")
            async with client:
                result = await client.list_templates()
                
                assert result == expected_templates["templates"]
                mock_get.assert_called_once_with("http://localhost:8080/nifi-api/templates")