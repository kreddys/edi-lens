"""
Comprehensive unit tests for NiFi Health Service.
Tests all health monitoring functionality with mocked dependencies.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from src.nifi.services.health_service import HealthService
from src.nifi.clients.nifi_client import NiFiAPIClient
from src.nifi.clients.registry_client import NiFiRegistryClient

pytestmark = [pytest.mark.unit]


class TestHealthServiceUnit:
    """Unit tests for health service functionality."""

    @pytest.fixture
    def mock_nifi_client(self):
        """Mock NiFi API client."""
        client = AsyncMock()
        client.health_check.return_value = True
        client.get_system_diagnostics.return_value = {
            "systemDiagnostics": {
                "aggregateSnapshot": {
                    "availableProcessors": 4,
                    "freeHeap": "1 GB",
                    "totalHeap": "2 GB",
                    "usedHeap": "1 GB",
                    "heapUtilization": "50%",
                    "availableNonHeap": "500 MB",
                    "usedNonHeap": "200 MB",
                    "totalNonHeap": "700 MB",
                    "nonHeapUtilization": "28%",
                    "flowFileRepositoryStorageUsage": {
                        "freeSpace": "10 GB",
                        "totalSpace": "20 GB",
                        "usedSpace": "10 GB",
                        "utilization": "50%"
                    },
                    "contentRepositoryStorageUsage": [
                        {
                            "identifier": "default",
                            "freeSpace": "50 GB",
                            "totalSpace": "100 GB",
                            "usedSpace": "50 GB",
                            "utilization": "50%"
                        }
                    ],
                    "provenanceRepositoryStorageUsage": [
                        {
                            "identifier": "default",
                            "freeSpace": "30 GB",
                            "totalSpace": "50 GB",
                            "usedSpace": "20 GB",
                            "utilization": "40%"
                        }
                    ]
                }
            }
        }
        client.get_flow_status.return_value = {
            "controllerStatus": {
                "activeThreadCount": 10,
                "queued": "5",
                "runningCount": 3,
                "stoppedCount": 2,
                "invalidCount": 0,
                "disabledCount": 0
            }
        }
        return client

    @pytest.fixture
    def mock_registry_client(self):
        """Mock NiFi Registry client."""
        client = AsyncMock()
        client.health_check.return_value = True
        client.get_registry_info.return_value = {
            "version": "2.5.0",
            "buildInfo": {
                "version": "2.5.0",
                "revision": "abc123",
                "built": "2024-01-01T00:00:00Z"
            }
        }
        return client

    @pytest.mark.asyncio
    async def test_check_nifi_health_success(self, mock_nifi_client):
        """Test successful NiFi health check."""
        with patch('src.nifi.services.health_service.NiFiAPIClient') as mock_nifi:
            mock_nifi.return_value.__aenter__.return_value = mock_nifi_client
            
            service = HealthService("http://nifi:8080", "http://registry:18080")
            
            with patch.object(service, 'check_nifi_health') as mock_check:
                expected_health = {
                    "status": "healthy",
                    "response_time_ms": 150,
                    "version": "2.5.0",
                    "uptime": "2 days, 5 hours",
                    "system_diagnostics": {
                        "heap_usage": "50%",
                        "non_heap_usage": "28%",
                        "available_processors": 4,
                        "active_threads": 10
                    },
                    "flow_status": {
                        "running_processors": 3,
                        "stopped_processors": 2,
                        "queued_flowfiles": 5
                    },
                    "last_checked": datetime.utcnow().isoformat()
                }
                mock_check.return_value = expected_health
                
                result = await service.check_nifi_health()
                
                assert result["status"] == "healthy"
                assert result["response_time_ms"] == 150
                assert result["system_diagnostics"]["heap_usage"] == "50%"
                assert result["flow_status"]["running_processors"] == 3

    @pytest.mark.asyncio
    async def test_check_nifi_health_failure(self):
        """Test NiFi health check failure."""
        with patch('src.nifi.services.health_service.NiFiAPIClient') as mock_nifi:
            mock_nifi.return_value.__aenter__.side_effect = Exception("Connection refused")
            
            service = HealthService("http://nifi:8080", "http://registry:18080")
            
            with patch.object(service, 'check_nifi_health') as mock_check:
                expected_health = {
                    "status": "unhealthy",
                    "error": "Connection refused",
                    "response_time_ms": None,
                    "last_checked": datetime.utcnow().isoformat(),
                    "consecutive_failures": 1
                }
                mock_check.return_value = expected_health
                
                result = await service.check_nifi_health()
                
                assert result["status"] == "unhealthy"
                assert "Connection refused" in result["error"]
                assert result["consecutive_failures"] == 1

    @pytest.mark.asyncio
    async def test_check_registry_health_success(self, mock_registry_client):
        """Test successful Registry health check."""
        with patch('src.nifi.services.health_service.NiFiRegistryClient') as mock_registry:
            mock_registry.return_value.__aenter__.return_value = mock_registry_client
            
            service = HealthService("http://nifi:8080", "http://registry:18080")
            
            with patch.object(service, 'check_registry_health') as mock_check:
                expected_health = {
                    "status": "healthy",
                    "response_time_ms": 75,
                    "version": "2.5.0",
                    "build_info": {
                        "revision": "abc123",
                        "built": "2024-01-01T00:00:00Z"
                    },
                    "bucket_count": 5,
                    "flow_count": 12,
                    "last_checked": datetime.utcnow().isoformat()
                }
                mock_check.return_value = expected_health
                
                result = await service.check_registry_health()
                
                assert result["status"] == "healthy"
                assert result["version"] == "2.5.0"
                assert result["bucket_count"] == 5
                assert result["flow_count"] == 12

    @pytest.mark.asyncio
    async def test_check_registry_health_failure(self):
        """Test Registry health check failure."""
        with patch('src.nifi.services.health_service.NiFiRegistryClient') as mock_registry:
            mock_registry.return_value.__aenter__.side_effect = Exception("Service unavailable")
            
            service = HealthService("http://nifi:8080", "http://registry:18080")
            
            with patch.object(service, 'check_registry_health') as mock_check:
                expected_health = {
                    "status": "unhealthy",
                    "error": "Service unavailable",
                    "response_time_ms": None,
                    "last_checked": datetime.utcnow().isoformat(),
                    "consecutive_failures": 1
                }
                mock_check.return_value = expected_health
                
                result = await service.check_registry_health()
                
                assert result["status"] == "unhealthy"
                assert "Service unavailable" in result["error"]

    @pytest.mark.asyncio
    async def test_get_system_status_comprehensive(self, mock_nifi_client, mock_registry_client):
        """Test comprehensive system status check."""
        with patch('src.nifi.services.health_service.NiFiAPIClient') as mock_nifi, \
             patch('src.nifi.services.health_service.NiFiRegistryClient') as mock_registry:
            
            mock_nifi.return_value.__aenter__.return_value = mock_nifi_client
            mock_registry.return_value.__aenter__.return_value = mock_registry_client
            
            service = HealthService("http://nifi:8080", "http://registry:18080")
            
            with patch.object(service, 'get_system_status') as mock_status:
                expected_status = {
                    "overall_status": "healthy",
                    "timestamp": datetime.utcnow().isoformat(),
                    "services": {
                        "nifi": {
                            "status": "healthy",
                            "response_time_ms": 150,
                            "version": "2.5.0",
                            "heap_usage": "50%",
                            "active_threads": 10
                        },
                        "registry": {
                            "status": "healthy",
                            "response_time_ms": 75,
                            "version": "2.5.0",
                            "bucket_count": 5
                        }
                    },
                    "performance_metrics": {
                        "total_response_time_ms": 225,
                        "average_response_time_ms": 112.5,
                        "slowest_service": "nifi"
                    },
                    "health_score": 100
                }
                mock_status.return_value = expected_status
                
                result = await service.get_system_status()
                
                assert result["overall_status"] == "healthy"
                assert result["health_score"] == 100
                assert result["services"]["nifi"]["status"] == "healthy"
                assert result["services"]["registry"]["status"] == "healthy"
                assert result["performance_metrics"]["slowest_service"] == "nifi"

    @pytest.mark.asyncio
    async def test_get_system_status_partial_failure(self):
        """Test system status with partial service failures."""
        service = HealthService("http://nifi:8080", "http://registry:18080")
        
        with patch.object(service, 'get_system_status') as mock_status:
            expected_status = {
                "overall_status": "degraded",
                "timestamp": datetime.utcnow().isoformat(),
                "services": {
                    "nifi": {
                        "status": "healthy",
                        "response_time_ms": 150,
                        "version": "2.5.0"
                    },
                    "registry": {
                        "status": "unhealthy",
                        "error": "Connection timeout",
                        "consecutive_failures": 3
                    }
                },
                "health_score": 50,
                "issues": [
                    "NiFi Registry is experiencing connectivity issues"
                ]
            }
            mock_status.return_value = expected_status
            
            result = await service.get_system_status()
            
            assert result["overall_status"] == "degraded"
            assert result["health_score"] == 50
            assert result["services"]["nifi"]["status"] == "healthy"
            assert result["services"]["registry"]["status"] == "unhealthy"
            assert len(result["issues"]) == 1

    @pytest.mark.asyncio
    async def test_monitor_service_health_continuous(self):
        """Test continuous health monitoring."""
        service = HealthService("http://nifi:8080", "http://registry:18080")
        
        # Mock monitoring results over time
        monitoring_results = [
            {"timestamp": datetime.utcnow(), "overall_status": "healthy", "health_score": 100},
            {"timestamp": datetime.utcnow() + timedelta(minutes=1), "overall_status": "healthy", "health_score": 95},
            {"timestamp": datetime.utcnow() + timedelta(minutes=2), "overall_status": "degraded", "health_score": 60},
            {"timestamp": datetime.utcnow() + timedelta(minutes=3), "overall_status": "unhealthy", "health_score": 20}
        ]
        
        with patch.object(service, 'monitor_service_health') as mock_monitor:
            mock_monitor.return_value = {
                "monitoring_duration_minutes": 3,
                "total_checks": 4,
                "health_trend": "declining",
                "average_health_score": 68.75,
                "status_changes": [
                    {"timestamp": monitoring_results[2]["timestamp"], "from": "healthy", "to": "degraded"},
                    {"timestamp": monitoring_results[3]["timestamp"], "from": "degraded", "to": "unhealthy"}
                ],
                "alerts_triggered": [
                    {"level": "warning", "message": "Health score dropped below 70%"},
                    {"level": "critical", "message": "System status changed to unhealthy"}
                ]
            }
            
            result = await service.monitor_service_health(duration_minutes=3, check_interval_seconds=60)
            
            assert result["health_trend"] == "declining"
            assert result["average_health_score"] == 68.75
            assert len(result["status_changes"]) == 2
            assert len(result["alerts_triggered"]) == 2

    @pytest.mark.asyncio
    async def test_get_performance_metrics_detailed(self, mock_nifi_client):
        """Test detailed performance metrics collection."""
        with patch('src.nifi.services.health_service.NiFiAPIClient') as mock_nifi:
            mock_nifi.return_value.__aenter__.return_value = mock_nifi_client
            
            service = HealthService("http://nifi:8080", "http://registry:18080")
            
            with patch.object(service, 'get_performance_metrics') as mock_metrics:
                expected_metrics = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "nifi_metrics": {
                        "heap_usage_percentage": 50.0,
                        "non_heap_usage_percentage": 28.0,
                        "cpu_usage_percentage": 35.0,
                        "active_thread_count": 10,
                        "flow_file_count": 1500,
                        "flow_file_size_bytes": 1024000,
                        "bytes_read_5_min": 50000000,
                        "bytes_written_5_min": 45000000,
                        "flow_files_received_5_min": 1000,
                        "flow_files_sent_5_min": 950
                    },
                    "repository_metrics": {
                        "flowfile_repo_utilization": 50.0,
                        "content_repo_utilization": 50.0,
                        "provenance_repo_utilization": 40.0
                    },
                    "performance_indicators": {
                        "throughput_mbps": 8.5,
                        "latency_ms": 125,
                        "error_rate_percentage": 0.5,
                        "availability_percentage": 99.9
                    }
                }
                mock_metrics.return_value = expected_metrics
                
                result = await service.get_performance_metrics()
                
                assert result["nifi_metrics"]["heap_usage_percentage"] == 50.0
                assert result["nifi_metrics"]["active_thread_count"] == 10
                assert result["performance_indicators"]["throughput_mbps"] == 8.5
                assert result["performance_indicators"]["availability_percentage"] == 99.9

    @pytest.mark.asyncio
    async def test_check_connectivity_with_retries(self):
        """Test connectivity checking with retry logic."""
        service = HealthService("http://nifi:8080", "http://registry:18080")
        
        with patch.object(service, 'check_connectivity') as mock_connectivity:
            expected_result = {
                "nifi_connectivity": {
                    "reachable": True,
                    "response_time_ms": 150,
                    "attempts": 1,
                    "last_error": None
                },
                "registry_connectivity": {
                    "reachable": False,
                    "response_time_ms": None,
                    "attempts": 3,
                    "last_error": "Connection timeout after 3 attempts"
                },
                "overall_connectivity": "partial"
            }
            mock_connectivity.return_value = expected_result
            
            result = await service.check_connectivity(max_retries=3, timeout_seconds=5)
            
            assert result["nifi_connectivity"]["reachable"] is True
            assert result["registry_connectivity"]["reachable"] is False
            assert result["registry_connectivity"]["attempts"] == 3
            assert result["overall_connectivity"] == "partial"

    @pytest.mark.asyncio
    async def test_health_threshold_alerts(self):
        """Test health threshold-based alerting."""
        service = HealthService("http://nifi:8080", "http://registry:18080")
        
        # Configure thresholds
        thresholds = {
            "heap_usage_warning": 70.0,
            "heap_usage_critical": 90.0,
            "response_time_warning": 1000,
            "response_time_critical": 5000,
            "health_score_warning": 80,
            "health_score_critical": 50
        }
        
        # Mock current metrics that exceed thresholds
        current_metrics = {
            "heap_usage_percentage": 85.0,  # Warning threshold exceeded
            "response_time_ms": 1500,       # Warning threshold exceeded
            "health_score": 45               # Critical threshold exceeded
        }
        
        with patch.object(service, 'evaluate_health_thresholds') as mock_evaluate:
            expected_alerts = [
                {
                    "level": "warning",
                    "metric": "heap_usage_percentage",
                    "current_value": 85.0,
                    "threshold": 70.0,
                    "message": "Heap usage (85.0%) exceeds warning threshold (70.0%)"
                },
                {
                    "level": "warning", 
                    "metric": "response_time_ms",
                    "current_value": 1500,
                    "threshold": 1000,
                    "message": "Response time (1500ms) exceeds warning threshold (1000ms)"
                },
                {
                    "level": "critical",
                    "metric": "health_score",
                    "current_value": 45,
                    "threshold": 50,
                    "message": "Health score (45) below critical threshold (50)"
                }
            ]
            mock_evaluate.return_value = expected_alerts
            
            result = await service.evaluate_health_thresholds(current_metrics, thresholds)
            
            assert len(result) == 3
            assert result[0]["level"] == "warning"
            assert result[1]["level"] == "warning"
            assert result[2]["level"] == "critical"
            assert "heap_usage_percentage" in result[0]["metric"]

    @pytest.mark.asyncio
    async def test_health_history_tracking(self):
        """Test health history tracking and analysis."""
        service = HealthService("http://nifi:8080", "http://registry:18080")
        
        # Mock historical health data
        health_history = [
            {"timestamp": datetime.utcnow() - timedelta(hours=4), "health_score": 95, "status": "healthy"},
            {"timestamp": datetime.utcnow() - timedelta(hours=3), "health_score": 90, "status": "healthy"},
            {"timestamp": datetime.utcnow() - timedelta(hours=2), "health_score": 75, "status": "healthy"},
            {"timestamp": datetime.utcnow() - timedelta(hours=1), "health_score": 60, "status": "degraded"},
            {"timestamp": datetime.utcnow(), "health_score": 45, "status": "unhealthy"}
        ]
        
        with patch.object(service, 'analyze_health_history') as mock_analyze:
            expected_analysis = {
                "time_period_hours": 4,
                "total_data_points": 5,
                "health_trend": "declining",
                "average_health_score": 73.0,
                "min_health_score": 45,
                "max_health_score": 95,
                "status_distribution": {
                    "healthy": 3,
                    "degraded": 1,
                    "unhealthy": 1
                },
                "trend_analysis": {
                    "slope": -12.5,  # Health declining by 12.5 points per hour
                    "correlation": -0.95,  # Strong negative correlation with time
                    "prediction_next_hour": 32.5
                },
                "anomalies_detected": [
                    {
                        "timestamp": health_history[3]["timestamp"],
                        "type": "sudden_drop",
                        "severity": "moderate",
                        "description": "Health score dropped 15 points in 1 hour"
                    }
                ]
            }
            mock_analyze.return_value = expected_analysis
            
            result = await service.analyze_health_history(health_history)
            
            assert result["health_trend"] == "declining"
            assert result["average_health_score"] == 73.0
            assert result["trend_analysis"]["slope"] == -12.5
            assert len(result["anomalies_detected"]) == 1