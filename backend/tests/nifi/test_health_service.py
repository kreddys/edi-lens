"""
Unit tests for NiFi Health Service.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

from src.nifi.services.health_service import NiFiHealthService

pytestmark = pytest.mark.unit


class TestNiFiHealthService:
    """Test NiFi Health Service."""

    @pytest.fixture
    def health_service(self):
        """Create a health service fixture."""
        return NiFiHealthService(
            nifi_url="http://localhost:8080",
            registry_url="http://localhost:18080",
            nifi_auth_token="nifi-token",
            registry_auth_token="registry-token"
        )

    @pytest.mark.asyncio
    async def test_health_service_initialization(self):
        """Test health service initialization."""
        service = NiFiHealthService(
            nifi_url="http://localhost:8080",
            registry_url="http://localhost:18080"
        )
        
        assert service.nifi_url == "http://localhost:8080"
        assert service.registry_url == "http://localhost:18080"
        assert service.nifi_auth_token is None
        assert service.registry_auth_token is None

    @pytest.mark.asyncio
    async def test_health_service_initialization_with_tokens(self):
        """Test health service initialization with auth tokens."""
        service = NiFiHealthService(
            nifi_url="http://localhost:8080",
            registry_url="http://localhost:18080",
            nifi_auth_token="nifi-token",
            registry_auth_token="registry-token"
        )
        
        assert service.nifi_url == "http://localhost:8080"
        assert service.registry_url == "http://localhost:18080"
        assert service.nifi_auth_token == "nifi-token"
        assert service.registry_auth_token == "registry-token"

    @pytest.mark.asyncio
    async def test_check_nifi_health_success(self, health_service):
        """Test successful NiFi health check."""
        mock_diagnostics = {
            "systemDiagnostics": {
                "aggregateSnapshot": {
                    "totalFlowFiles": 100,
                    "totalBytes": 1024000,
                    "usedHeap": "512 MB",
                    "maxHeap": "2 GB",
                    "heapUtilization": "25%",
                    "availableProcessors": 4,
                    "processorLoadAverage": 0.25
                }
            }
        }
        
        mock_flow_status = {
            "controllerStatus": {
                "activeThreadCount": 10,
                "queued": "15 / 1.5 MB",
                "runningCount": 5,
                "stoppedCount": 2,
                "invalidCount": 0,
                "disabledCount": 0
            }
        }
        
        with patch('src.nifi.services.health_service.NiFiAPIClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None
            
            mock_client.health_check.return_value = True
            mock_client.get_system_diagnostics.return_value = mock_diagnostics
            mock_client.get_flow_status.return_value = mock_flow_status
            
            result = await health_service.check_nifi_health()
            
            assert result["status"] == "HEALTHY"
            assert result["details"]["diagnostics"] == mock_diagnostics
            assert result["details"]["flow_status"] == mock_flow_status
            assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_check_nifi_health_api_failure(self, health_service):
        """Test NiFi health check with API failure."""
        with patch('src.nifi.services.health_service.NiFiAPIClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None
            
            mock_client.health_check.return_value = False
            
            result = await health_service.check_nifi_health()
            
            assert result["status"] == "UNHEALTHY"
            assert "error" in result["details"]
            assert result["details"]["error"] == "NiFi instance is unreachable"

    @pytest.mark.asyncio
    async def test_check_nifi_health_exception(self, health_service):
        """Test NiFi health check with exception."""
        with patch('src.nifi.services.health_service.NiFiAPIClient') as mock_client_class:
            mock_client_class.side_effect = Exception("Connection error")
            
            result = await health_service.check_nifi_health()
            
            assert result["status"] == "UNHEALTHY"
            assert "Connection error" in result["details"]["error"]

    @pytest.mark.asyncio
    async def test_check_registry_health_success(self, health_service):
        """Test successful Registry health check."""
        mock_registry_info = {
            "buildInfo": {
                "version": "1.23.2",
                "buildTimestamp": "2023-01-01T00:00:00Z"
            }
        }
        
        mock_health_info = {
            "status": "UP",
            "components": {
                "database": {"status": "UP"},
                "filesystem": {"status": "UP"}
            }
        }
        
        mock_buckets = [
            {"identifier": "bucket1", "name": "Test Bucket 1"},
            {"identifier": "bucket2", "name": "Test Bucket 2"}
        ]
        
        with patch('src.nifi.services.health_service.NiFiRegistryClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None
            
            mock_client.get_registry_info.return_value = mock_registry_info
            mock_client.health_check.return_value = mock_health_info
            mock_client.list_buckets.return_value = mock_buckets
            
            result = await health_service.check_registry_health()
            
            assert result["status"] == "HEALTHY"
            assert result["details"]["registry_info"] == mock_registry_info
            assert result["details"]["health_info"] == mock_health_info
            assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_check_registry_health_api_failure(self, health_service):
        """Test Registry health check with API failure."""
        with patch('src.nifi.services.health_service.NiFiRegistryClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None
            
            mock_client.get_registry_info.side_effect = Exception("API error")
            
            result = await health_service.check_registry_health()
            
            assert result["status"] == "DEGRADED"
            assert "API error" in result["details"]["warning"]

    @pytest.mark.asyncio
    async def test_comprehensive_health_check_all_up(self, health_service):
        """Test comprehensive health check with all services up."""
        mock_nifi_health = {
            "status": "HEALTHY",
            "details": {"nifi_url": "http://localhost:8080"}
        }
        
        mock_registry_health = {
            "status": "HEALTHY", 
            "details": {"registry_url": "http://localhost:18080"}
        }
        
        with patch.object(health_service, 'check_nifi_health', return_value=mock_nifi_health), \
             patch.object(health_service, 'check_registry_health', return_value=mock_registry_health):
            
            result = await health_service.comprehensive_health_check()
            
            assert result["overall_status"] == "HEALTHY"
            assert result["nifi"] == mock_nifi_health
            assert result["registry"] == mock_registry_health
            assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_comprehensive_health_check_partial_down(self, health_service):
        """Test comprehensive health check with one service down."""
        mock_nifi_health = {
            "status": "HEALTHY",
            "details": {"nifi_url": "http://localhost:8080"}
        }
        
        mock_registry_health = {
            "status": "UNHEALTHY",
            "details": {"registry_url": "http://localhost:18080", "error": "Connection failed"}
        }
        
        with patch.object(health_service, 'check_nifi_health', return_value=mock_nifi_health), \
             patch.object(health_service, 'check_registry_health', return_value=mock_registry_health):
            
            result = await health_service.comprehensive_health_check()
            
            assert result["overall_status"] == "UNHEALTHY"
            assert result["nifi"]["status"] == "HEALTHY"
            assert result["registry"]["status"] == "UNHEALTHY"

    @pytest.mark.asyncio
    async def test_comprehensive_health_check_all_down(self, health_service):
        """Test comprehensive health check with all services down."""
        mock_nifi_health = {
            "status": "UNHEALTHY",
            "details": {"nifi_url": "http://localhost:8080", "error": "NiFi down"}
        }
        
        mock_registry_health = {
            "status": "UNHEALTHY",
            "details": {"registry_url": "http://localhost:18080", "error": "Registry down"}
        }
        
        with patch.object(health_service, 'check_nifi_health', return_value=mock_nifi_health), \
             patch.object(health_service, 'check_registry_health', return_value=mock_registry_health):
            
            result = await health_service.comprehensive_health_check()
            
            assert result["overall_status"] == "UNHEALTHY"
            assert result["nifi"]["status"] == "UNHEALTHY"
            assert result["registry"]["status"] == "UNHEALTHY"

    @pytest.mark.asyncio
    async def test_get_detailed_diagnostics_success(self, health_service):
        """Test successful detailed diagnostics."""
        mock_templates = [{"id": "template1", "name": "Template 1"}]
        mock_buckets = [{"identifier": "bucket1", "name": "Test Bucket"}]
        
        mock_nifi_diagnostics = {
            "systemDiagnostics": {
                "aggregateSnapshot": {
                    "totalFlowFiles": 100,
                    "totalBytes": 1024000
                }
            }
        }
        
        mock_flow_status = {
            "controllerStatus": {
                "activeThreadCount": 10,
                "queued": "15 / 1.5 MB"
            }
        }
        
        mock_registry_info = {
            "buildInfo": {"version": "1.23.2"}
        }
        
        with patch('src.nifi.services.health_service.NiFiAPIClient') as mock_nifi_client_class, \
             patch('src.nifi.services.health_service.NiFiRegistryClient') as mock_registry_client_class:
            
            # Setup NiFi client mock
            mock_nifi_client = AsyncMock()
            mock_nifi_client_class.return_value.__aenter__.return_value = mock_nifi_client
            mock_nifi_client_class.return_value.__aexit__.return_value = None
            mock_nifi_client.get_system_diagnostics.return_value = mock_nifi_diagnostics
            mock_nifi_client.get_flow_status.return_value = mock_flow_status
            mock_nifi_client.list_templates.return_value = mock_templates
            
            # Setup Registry client mock
            mock_registry_client = AsyncMock()
            mock_registry_client_class.return_value.__aenter__.return_value = mock_registry_client
            mock_registry_client_class.return_value.__aexit__.return_value = None
            mock_registry_client.get_registry_info.return_value = mock_registry_info
            mock_registry_client.list_buckets.return_value = mock_buckets
            
            result = await health_service.get_detailed_diagnostics()
            
            assert result["system_diagnostics"] == mock_nifi_diagnostics
            assert result["flow_status"] == mock_flow_status
            assert result["available_templates"] == mock_templates
            assert result["registry_info"] == mock_registry_info
            assert result["buckets"] == mock_buckets
            assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_get_detailed_diagnostics_with_exceptions(self, health_service):
        """Test detailed diagnostics with exceptions."""
        # No need for comprehensive health check mock in this test
        
        with patch('src.nifi.services.health_service.NiFiAPIClient') as mock_nifi_client_class, \
             patch('src.nifi.services.health_service.NiFiRegistryClient') as mock_registry_client_class:
            
            # Setup clients to raise exceptions
            mock_nifi_client_class.side_effect = Exception("NiFi connection error")
            mock_registry_client_class.side_effect = Exception("Registry connection error")
            
            result = await health_service.get_detailed_diagnostics()
            
            assert "NiFi connection error" in result["error"]
            assert "timestamp" in result