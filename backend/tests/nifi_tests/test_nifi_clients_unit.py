"""
Unit tests for NiFi clients.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from aiohttp import ClientResponse

from src.nifi.clients.nifi_client import NiFiAPIClient
from src.nifi.clients.registry_client import NiFiRegistryClient
from src.core.config import settings


pytestmark = pytest.mark.unit


class TestNiFiAPIClient:
    """Test NiFi API Client."""

    @pytest.fixture
    def mock_response(self):
        """Create a mock aiohttp response."""
        response = AsyncMock(spec=ClientResponse)
        response.status = 200
        response.raise_for_status = AsyncMock()
        return response

    @pytest.mark.asyncio
    async def test_nifi_client_initialization(self):
        """Test NiFi API client initialization."""
        client = NiFiAPIClient("http://localhost:8080")
        assert client.base_url == "http://localhost:8080"
        assert client.nifi_url == "http://localhost:8080/nifi-api"
        assert client.session is None

    @pytest.mark.asyncio
    async def test_nifi_client_initialization_with_trailing_slash(self):
        """Test NiFi API client initialization with trailing slash."""
        client = NiFiAPIClient("http://localhost:8080/")
        assert client.base_url == "http://localhost:8080"
        assert client.nifi_url == "http://localhost:8080/nifi-api"
        assert client.session is None

    @pytest.mark.asyncio
    async def test_nifi_client_context_manager(self):
        """Test NiFi API client context manager."""
        client = NiFiAPIClient("http://localhost:8080")
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value = mock_session
            
            async with client as ctx:
                assert ctx is client
                assert client.session is not None
                assert isinstance(client.session, AsyncMock)

    @pytest.mark.asyncio
    async def test_health_check_success(self, mock_response):
        """Test successful health check."""
        mock_response.status = 200
        
        # Create a proper async context manager mock
        class AsyncContextManagerMock:
            def __init__(self, return_value):
                self.return_value = return_value
            
            async def __aenter__(self):
                return self.return_value
            
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session.get = MagicMock(return_value=AsyncContextManagerMock(mock_response))
            mock_session_class.return_value = mock_session
            
            client = NiFiAPIClient("http://localhost:8080")
            async with client:
                result = await client.health_check()
                assert result is True
                mock_session.get.assert_called_once_with("http://localhost:8080/nifi-api/system-diagnostics")

    @pytest.mark.asyncio
    async def test_health_check_failure(self, mock_response):
        """Test health check failure."""
        from aiohttp import ClientError
        mock_session = AsyncMock()
        mock_session.get = MagicMock(side_effect=ClientError("Connection failed"))
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session_class.return_value = mock_session
            
            client = NiFiAPIClient("http://localhost:8080")
            async with client:
                result = await client.health_check()
                assert result is False

    @pytest.mark.asyncio
    async def test_get_process_group_success(self, mock_response):
        """Test successful process group retrieval."""
        expected_pg = {
            "component": {
                "id": "root",
                "name": "NiFi Flow"
            }
        }
        mock_response.json = AsyncMock(return_value=expected_pg)
        mock_response.raise_for_status = AsyncMock()
        
        # Create a proper async context manager mock
        class AsyncContextManagerMock:
            def __init__(self, return_value):
                self.return_value = return_value
            
            async def __aenter__(self):
                return self.return_value
            
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session.get = MagicMock(return_value=AsyncContextManagerMock(mock_response))
            mock_session_class.return_value = mock_session
            
            client = NiFiAPIClient("http://localhost:8080")
            async with client:
                result = await client.get_process_group("root")
                assert result == expected_pg
                mock_session.get.assert_called_once_with("http://localhost:8080/nifi-api/process-groups/root")

    @pytest.mark.asyncio
    async def test_get_system_diagnostics_success(self, mock_response):
        """Test successful system diagnostics retrieval."""
        expected_diagnostics = {
            "systemDiagnostics": {
                "aggregateSnapshot": {
                    "totalFlowFiles": 100,
                    "totalBytes": 1024000
                }
            }
        }
        mock_response.json = AsyncMock(return_value=expected_diagnostics)
        mock_response.raise_for_status = AsyncMock()
        
        # Create a proper async context manager mock
        class AsyncContextManagerMock:
            def __init__(self, return_value):
                self.return_value = return_value
            
            async def __aenter__(self):
                return self.return_value
            
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session.get = MagicMock(return_value=AsyncContextManagerMock(mock_response))
            mock_session_class.return_value = mock_session
            
            client = NiFiAPIClient("http://localhost:8080")
            async with client:
                result = await client.get_system_diagnostics()
                assert result == expected_diagnostics
                mock_session.get.assert_called_once_with("http://localhost:8080/nifi-api/system-diagnostics")

    @pytest.mark.asyncio
    async def test_get_flow_status_success(self, mock_response):
        """Test successful flow status retrieval."""
        expected_status = {
            "controllerStatus": {
                "activeThreadCount": 10,
                "queued": "15 / 1.5 MB"
            }
        }
        mock_response.json = AsyncMock(return_value=expected_status)
        mock_response.raise_for_status = AsyncMock()
        
        # Create a proper async context manager mock
        class AsyncContextManagerMock:
            def __init__(self, return_value):
                self.return_value = return_value
            
            async def __aenter__(self):
                return self.return_value
            
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session.get = MagicMock(return_value=AsyncContextManagerMock(mock_response))
            mock_session_class.return_value = mock_session
            
            client = NiFiAPIClient("http://localhost:8080")
            async with client:
                result = await client.get_flow_status()
                assert result == expected_status
                mock_session.get.assert_called_once_with("http://localhost:8080/nifi-api/flow/status")

    @pytest.mark.asyncio
    async def test_create_process_group_success(self, mock_response):
        """Test successful process group creation."""
        expected_pg = {
            "component": {
                "id": "pg-123",
                "name": "Test Process Group"
            }
        }
        mock_response.json = AsyncMock(return_value=expected_pg)
        mock_response.raise_for_status = AsyncMock()
        
        # Create a proper async context manager mock
        class AsyncContextManagerMock:
            def __init__(self, return_value):
                self.return_value = return_value
            
            async def __aenter__(self):
                return self.return_value
            
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session.post = MagicMock(return_value=AsyncContextManagerMock(mock_response))
            mock_session_class.return_value = mock_session
            
            client = NiFiAPIClient("http://localhost:8080")
            async with client:
                result = await client.create_process_group(
                    parent_group_id="root", 
                    name="Test Process Group", 
                    position={"x": 100, "y": 100}
                )
                assert result == expected_pg
                mock_session.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_parameter_context_success(self, mock_response):
        """Test successful parameter context creation."""
        expected_context = {
            "component": {
                "id": "pc-123",
                "name": "Test Context"
            }
        }
        mock_response.json = AsyncMock(return_value=expected_context)
        mock_response.raise_for_status = AsyncMock()
        
        # Create a proper async context manager mock
        class AsyncContextManagerMock:
            def __init__(self, return_value):
                self.return_value = return_value
            
            async def __aenter__(self):
                return self.return_value
            
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session.post = MagicMock(return_value=AsyncContextManagerMock(mock_response))
            mock_session_class.return_value = mock_session
            
            client = NiFiAPIClient("http://localhost:8080")
            async with client:
                result = await client.create_parameter_context(
                    name="Test Context",
                    description="Test parameter context",
                    parameters=[]
                )
                assert result == expected_context
                mock_session.post.assert_called_once_with(
                    "http://localhost:8080/nifi-api/parameter-contexts",
                    json={
                        "revision": {"version": 0},
                        "component": {
                            "name": "Test Context",
                            "description": "Test parameter context",
                            "parameters": []
                        }
                    }
                )

    @pytest.mark.asyncio
    async def test_start_process_group_success(self, mock_response):
        """Test successful process group start."""
        expected_result = {"component": {"state": "RUNNING"}}
        mock_response.json = AsyncMock(return_value=expected_result)
        mock_response.raise_for_status = AsyncMock()
        
        # Create a proper async context manager mock
        class AsyncContextManagerMock:
            def __init__(self, return_value):
                self.return_value = return_value
            
            async def __aenter__(self):
                return self.return_value
            
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session.put = MagicMock(return_value=AsyncContextManagerMock(mock_response))
            mock_session_class.return_value = mock_session
            
            client = NiFiAPIClient("http://localhost:8080")
            async with client:
                result = await client.start_process_group("pg-123")
                assert result == expected_result
                mock_session.put.assert_called_once_with(
                    "http://localhost:8080/nifi-api/flow/process-groups/pg-123",
                    json={"id": "pg-123", "state": "RUNNING"},
                    headers={"Content-Type": "application/json"}
                )

    @pytest.mark.asyncio
    async def test_stop_process_group_success(self, mock_response):
        """Test successful process group stop."""
        expected_result = {"component": {"state": "STOPPED"}}
        mock_response.json = AsyncMock(return_value=expected_result)
        mock_response.raise_for_status = AsyncMock()
        
        # Create a proper async context manager mock
        class AsyncContextManagerMock:
            def __init__(self, return_value):
                self.return_value = return_value
            
            async def __aenter__(self):
                return self.return_value
            
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session.put = MagicMock(return_value=AsyncContextManagerMock(mock_response))
            mock_session_class.return_value = mock_session
            
            client = NiFiAPIClient("http://localhost:8080")
            async with client:
                result = await client.stop_process_group("pg-123")
                assert result == expected_result
                mock_session.put.assert_called_once_with(
                    "http://localhost:8080/nifi-api/flow/process-groups/pg-123",
                    json={"id": "pg-123", "state": "STOPPED"},
                    headers={"Content-Type": "application/json"}
                )

    @pytest.mark.asyncio
    async def test_delete_process_group_success(self, mock_response):
        """Test successful process group deletion."""
        mock_response.status = 200
        mock_response.raise_for_status = AsyncMock()
        
        # Create a proper async context manager mock
        class AsyncContextManagerMock:
            def __init__(self, return_value):
                self.return_value = return_value
            
            async def __aenter__(self):
                return self.return_value
            
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session.delete = MagicMock(return_value=AsyncContextManagerMock(mock_response))
            mock_session_class.return_value = mock_session
            
            client = NiFiAPIClient("http://localhost:8080")
            async with client:
                result = await client.delete_process_group("pg-123", version=1)
                assert result is True
                mock_session.delete.assert_called_once()


class TestNiFiRegistryClient:
    """Test NiFi Registry Client."""

    @pytest.fixture
    def mock_response(self):
        """Create a mock aiohttp response."""
        response = AsyncMock(spec=ClientResponse)
        response.status = 200
        response.raise_for_status = AsyncMock()
        return response

    @pytest.mark.asyncio
    async def test_registry_client_initialization(self):
        """Test registry client initialization."""
        client = NiFiRegistryClient("http://localhost:18080")
        assert client.registry_url == "http://localhost:18080"
        assert client.session is None

    @pytest.mark.asyncio
    async def test_registry_client_initialization_with_trailing_slash(self):
        """Test registry client initialization with trailing slash."""
        client = NiFiRegistryClient("http://localhost:18080/")
        assert client.registry_url == "http://localhost:18080"
        assert client.session is None

    @pytest.mark.asyncio
    async def test_registry_client_context_manager(self):
        """Test registry client context manager."""
        client = NiFiRegistryClient("http://localhost:18080")
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value = mock_session
            
            async with client as ctx:
                assert ctx is client
                assert client.session is not None
                assert isinstance(client.session, AsyncMock)

    @pytest.mark.asyncio
    async def test_list_buckets_success(self, mock_response):
        """Test successful bucket listing."""
        expected_buckets = [
            {"identifier": "bucket1", "name": "Test Bucket 1"},
            {"identifier": "bucket2", "name": "Test Bucket 2"}
        ]
        mock_response.json = AsyncMock(return_value=expected_buckets)
        mock_response.raise_for_status = AsyncMock()
        
        # Create a proper async context manager mock
        class AsyncContextManagerMock:
            def __init__(self, return_value):
                self.return_value = return_value
            
            async def __aenter__(self):
                return self.return_value
            
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session.get = MagicMock(return_value=AsyncContextManagerMock(mock_response))
            mock_session_class.return_value = mock_session
            
            client = NiFiRegistryClient("http://localhost:18080")
            async with client:
                result = await client.list_buckets()
                assert result == expected_buckets
                mock_session.get.assert_called_once_with("http://localhost:18080/nifi-registry-api/buckets")

    @pytest.mark.asyncio
    async def test_create_bucket_success(self, mock_response):
        """Test successful bucket creation."""
        expected_bucket = {"identifier": "new-bucket", "name": "New Bucket"}
        mock_response.json = AsyncMock(return_value=expected_bucket)
        mock_response.raise_for_status = AsyncMock()
        
        # Create a proper async context manager mock
        class AsyncContextManagerMock:
            def __init__(self, return_value):
                self.return_value = return_value
            
            async def __aenter__(self):
                return self.return_value
            
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session.post = MagicMock(return_value=AsyncContextManagerMock(mock_response))
            mock_session_class.return_value = mock_session
            
            client = NiFiRegistryClient("http://localhost:18080")
            async with client:
                result = await client.create_bucket("New Bucket", "Test bucket")
                assert result == expected_bucket
                mock_session.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_bucket_success(self, mock_response):
        """Test successful bucket retrieval."""
        expected_bucket = {"identifier": "bucket1", "name": "Test Bucket"}
        mock_response.json = AsyncMock(return_value=expected_bucket)
        mock_response.raise_for_status = AsyncMock()
        
        # Create a proper async context manager mock
        class AsyncContextManagerMock:
            def __init__(self, return_value):
                self.return_value = return_value
            
            async def __aenter__(self):
                return self.return_value
            
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session.get = MagicMock(return_value=AsyncContextManagerMock(mock_response))
            mock_session_class.return_value = mock_session
            
            client = NiFiRegistryClient("http://localhost:18080")
            async with client:
                result = await client.get_bucket("bucket1")
                assert result == expected_bucket
                mock_session.get.assert_called_once_with("http://localhost:18080/nifi-registry-api/buckets/bucket1")

    @pytest.mark.asyncio
    async def test_delete_bucket_success(self, mock_response):
        """Test successful bucket deletion."""
        mock_response.status = 200
        mock_response.raise_for_status = AsyncMock()
        
        # Create a proper async context manager mock
        class AsyncContextManagerMock:
            def __init__(self, return_value):
                self.return_value = return_value
            
            async def __aenter__(self):
                return self.return_value
            
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session.delete = MagicMock(return_value=AsyncContextManagerMock(mock_response))
            mock_session_class.return_value = mock_session
            
            client = NiFiRegistryClient("http://localhost:18080")
            async with client:
                result = await client.delete_bucket("bucket1")
                assert result is True
                mock_session.delete.assert_called_once_with("http://localhost:18080/nifi-registry-api/buckets/bucket1")

    @pytest.mark.asyncio
    async def test_create_flow_success(self, mock_response):
        """Test successful flow creation."""
        expected_flow = {"identifier": "flow1", "name": "Test Flow"}
        mock_response.json = AsyncMock(return_value=expected_flow)
        mock_response.raise_for_status = AsyncMock()
        
        # Create a proper async context manager mock
        class AsyncContextManagerMock:
            def __init__(self, return_value):
                self.return_value = return_value
            
            async def __aenter__(self):
                return self.return_value
            
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session.post = MagicMock(return_value=AsyncContextManagerMock(mock_response))
            mock_session_class.return_value = mock_session
            
            client = NiFiRegistryClient("http://localhost:18080")
            async with client:
                result = await client.create_flow("bucket1", "Test Flow", "Test flow description")
                assert result == expected_flow
                mock_session.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_flows_success(self, mock_response):
        """Test successful flow listing."""
        expected_flows = [
            {"identifier": "flow1", "name": "Flow 1"},
            {"identifier": "flow2", "name": "Flow 2"}
        ]
        mock_response.json = AsyncMock(return_value=expected_flows)
        mock_response.raise_for_status = AsyncMock()
        
        # Create a proper async context manager mock
        class AsyncContextManagerMock:
            def __init__(self, return_value):
                self.return_value = return_value
            
            async def __aenter__(self):
                return self.return_value
            
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session.get = MagicMock(return_value=AsyncContextManagerMock(mock_response))
            mock_session_class.return_value = mock_session
            
            client = NiFiRegistryClient("http://localhost:18080")
            async with client:
                result = await client.list_flows("bucket1")
                assert result == expected_flows
                mock_session.get.assert_called_once_with("http://localhost:18080/nifi-registry-api/buckets/bucket1/flows")

    @pytest.mark.asyncio
    async def test_get_registry_info_success(self, mock_response):
        """Test successful registry info retrieval."""
        expected_info = {"buildInfo": {"version": "1.23.2"}}
        mock_response.json = AsyncMock(return_value=expected_info)
        mock_response.raise_for_status = AsyncMock()
        
        # Create a proper async context manager mock
        class AsyncContextManagerMock:
            def __init__(self, return_value):
                self.return_value = return_value
            
            async def __aenter__(self):
                return self.return_value
            
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session.get = MagicMock(return_value=AsyncContextManagerMock(mock_response))
            mock_session_class.return_value = mock_session
            
            client = NiFiRegistryClient("http://localhost:18080")
            async with client:
                result = await client.get_registry_info()
                assert result == expected_info
                mock_session.get.assert_called_once_with("http://localhost:18080/nifi-registry-api/config")

    @pytest.mark.asyncio
    async def test_health_check_success(self, mock_response):
        """Test successful health check."""
        expected_health = {"status": "UP"}
        mock_response.json = AsyncMock(return_value=expected_health)
        mock_response.raise_for_status = AsyncMock()
        
        # Create a proper async context manager mock
        class AsyncContextManagerMock:
            def __init__(self, return_value):
                self.return_value = return_value
            
            async def __aenter__(self):
                return self.return_value
            
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session.get = MagicMock(return_value=AsyncContextManagerMock(mock_response))
            mock_session_class.return_value = mock_session
            
            client = NiFiRegistryClient("http://localhost:18080")
            async with client:
                result = await client.health_check()
                assert result == expected_health
                mock_session.get.assert_called_once_with("http://localhost:18080/nifi-registry-api/health")