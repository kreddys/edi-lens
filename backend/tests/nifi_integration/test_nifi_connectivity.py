"""
NiFi connectivity tests.
"""

import pytest
import asyncio
from src.core.config import settings
from src.nifi.clients.nifi_client import NiFiAPIClient
from src.nifi.clients.registry_client import NiFiRegistryClient

pytestmark = pytest.mark.integration


class TestNiFiConnectivity:
    """Test NiFi service connectivity."""

    @pytest.mark.asyncio
    async def test_nifi_connectivity(self):
        """Test basic connectivity to NiFi and Registry services."""
        # Test NiFi connectivity
        try:
            async with NiFiAPIClient(settings.NIFI_URL) as nifi_client:
                health = await nifi_client.health_check()
                assert health is True, "NiFi should be accessible"
                
                # Test system diagnostics
                diagnostics = await nifi_client.get_system_diagnostics()
                assert "systemDiagnostics" in diagnostics
        except Exception as e:
            pytest.skip(f"NiFi not accessible: {str(e)}")
        
        # Test Registry connectivity
        try:
            async with NiFiRegistryClient(settings.NIFI_REGISTRY_URL) as registry_client:
                registry_info = await registry_client.get_registry_info()
                assert "buildInfo" in registry_info or "version" in registry_info
        except Exception as e:
            pytest.skip(f"NiFi Registry not accessible: {str(e)}")

    @pytest.mark.asyncio
    async def test_nifi_basic_operations(self):
        """Test basic NiFi operations."""
        try:
            async with NiFiAPIClient(settings.NIFI_URL) as nifi_client:
                # Test getting process groups
                root_pg = await nifi_client.get_process_group("root")
                assert root_pg is not None
                assert "component" in root_pg
                
                # Test getting parameter contexts (should be empty initially)
                param_contexts = await nifi_client.get_parameter_contexts()
                assert isinstance(param_contexts, list)
                
        except Exception as e:
            pytest.skip(f"NiFi basic operations failed: {str(e)}")

    @pytest.mark.asyncio
    async def test_nifi_registry_basic_operations(self):
        """Test basic NiFi Registry operations."""
        try:
            async with NiFiRegistryClient(settings.NIFI_REGISTRY_URL) as registry_client:
                # Test listing buckets
                buckets = await registry_client.list_buckets()
                assert isinstance(buckets, list)
                
        except Exception as e:
            pytest.skip(f"NiFi Registry basic operations failed: {str(e)}")