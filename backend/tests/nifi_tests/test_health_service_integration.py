"""
Integration tests for NiFi Health Service with real NiFi instances.

These tests validate health monitoring and diagnostics against actual NiFi and NiFi Registry services.
"""

import pytest
from src.nifi.services.health_service import HealthService
from src.core.config import settings


pytestmark = pytest.mark.integration


class TestNiFiHealthServiceIntegration:
    """Integration tests for NiFi Health Service with real NiFi services."""

    @pytest.mark.asyncio
    async def test_nifi_health_check_with_real_instance(self):
        """Test NiFi health check against real NiFi instance."""
        service = HealthService(
            nifi_url=settings.NIFI_URL,
            registry_url=settings.NIFI_REGISTRY_URL,
        )
        try:
            health_result = await service.check_nifi_health()
            assert isinstance(health_result, dict)
            assert "status" in health_result
            assert "timestamp" in health_result
        except Exception as e:
            pytest.fail(f"NiFi health check failed with exception: {e}")

    @pytest.mark.asyncio
    async def test_registry_health_check_with_real_instance(self):
        """Test NiFi Registry health check against real Registry instance."""
        service = HealthService(
            nifi_url=settings.NIFI_URL,
            registry_url=settings.NIFI_REGISTRY_URL,
        )
        try:
            health_result = await service.check_registry_health()
            assert isinstance(health_result, dict)
            assert "status" in health_result
            assert "timestamp" in health_result
        except Exception as e:
            pytest.fail(f"NiFi Registry health check failed with exception: {e}")

    @pytest.mark.asyncio
    async def test_comprehensive_health_check(self):
        """Test comprehensive health check of both NiFi and Registry."""
        service = HealthService(
            nifi_url=settings.NIFI_URL,
            registry_url=settings.NIFI_REGISTRY_URL,
        )
        try:
            comprehensive_result = await service.comprehensive_health_check()
            assert isinstance(comprehensive_result, dict)
            assert "overall_status" in comprehensive_result
            assert "nifi" in comprehensive_result
            assert "registry" in comprehensive_result
        except Exception as e:
            pytest.fail(f"Comprehensive health check failed with exception: {e}")

    @pytest.mark.asyncio
    async def test_get_detailed_diagnostics(self):
        """Test detailed diagnostics collection from NiFi."""
        service = HealthService(
            nifi_url=settings.NIFI_URL,
            registry_url=settings.NIFI_REGISTRY_URL,
        )
        try:
            diagnostics = await service.get_detailed_diagnostics()
            assert isinstance(diagnostics, dict)
            assert "timestamp" in diagnostics
        except Exception as e:
            pytest.fail(f"Detailed diagnostics collection failed with exception: {e}")

    @pytest.mark.asyncio
    async def test_health_service_error_handling(self):
        """Test health service error handling for unreachable services."""
        invalid_service = HealthService(
            nifi_url="http://invalid-nifi:9999",
            registry_url="http://invalid-registry:9999",
        )
        nifi_health = await invalid_service.check_nifi_health()
        assert nifi_health["status"] == "UNHEALTHY"
        assert "error" in nifi_health["details"]

        registry_health = await invalid_service.check_registry_health()
        assert registry_health["status"] == "DEGRADED"
        assert "warning" in registry_health["details"]
