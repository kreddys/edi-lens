"""
NiFi Health Monitoring Service for EDI Lens.

This service provides comprehensive health monitoring and diagnostics
for NiFi and NiFi Registry instances.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from src.nifi.clients.nifi_client import NiFiAPIClient
from src.nifi.clients.registry_client import NiFiRegistryClient

logger = logging.getLogger(__name__)


class NiFiHealthService:
    """Service for monitoring NiFi instance health."""

    def __init__(
        self,
        nifi_url: str,
        registry_url: str,
        nifi_auth_token: Optional[str] = None,
        registry_auth_token: Optional[str] = None
    ):
        self.nifi_url = nifi_url
        self.registry_url = registry_url
        self.nifi_auth_token = nifi_auth_token
        self.registry_auth_token = registry_auth_token

    async def check_nifi_health(self) -> Dict[str, Any]:
        """Check NiFi instance health."""
        try:
            async with NiFiAPIClient(self.nifi_url, self.nifi_auth_token) as nifi_client:
                # Check basic connectivity
                is_healthy = await nifi_client.health_check()
                
                if not is_healthy:
                    return {
                        "status": "UNHEALTHY",
                        "timestamp": datetime.utcnow().isoformat(),
                        "details": {
                            "nifi_url": self.nifi_url,
                            "error": "NiFi instance is unreachable"
                        }
                    }
                
                # Get system diagnostics
                try:
                    diagnostics = await nifi_client.get_system_diagnostics()
                    flow_status = await nifi_client.get_flow_status()
                    
                    return {
                        "status": "HEALTHY",
                        "timestamp": datetime.utcnow().isoformat(),
                        "details": {
                            "nifi_url": self.nifi_url,
                            "diagnostics": diagnostics,
                            "flow_status": flow_status
                        }
                    }
                except Exception as e:
                    return {
                        "status": "DEGRADED",
                        "timestamp": datetime.utcnow().isoformat(),
                        "details": {
                            "nifi_url": self.nifi_url,
                            "warning": f"NiFi is reachable but diagnostics failed: {str(e)}"
                        }
                    }
                    
        except Exception as e:
            return {
                "status": "UNHEALTHY",
                "timestamp": datetime.utcnow().isoformat(),
                "details": {
                    "nifi_url": self.nifi_url,
                    "error": f"Failed to connect to NiFi: {str(e)}"
                }
            }

    async def check_registry_health(self) -> Dict[str, Any]:
        """Check NiFi Registry health."""
        try:
            async with NiFiRegistryClient(self.registry_url, self.registry_auth_token) as registry_client:
                # Check registry info
                try:
                    registry_info = await registry_client.get_registry_info()
                    health_info = await registry_client.health_check()
                    
                    return {
                        "status": "HEALTHY",
                        "timestamp": datetime.utcnow().isoformat(),
                        "details": {
                            "registry_url": self.registry_url,
                            "registry_info": registry_info,
                            "health_info": health_info
                        }
                    }
                except Exception as e:
                    return {
                        "status": "DEGRADED",
                        "timestamp": datetime.utcnow().isoformat(),
                        "details": {
                            "registry_url": self.registry_url,
                            "warning": f"Registry is reachable but health check failed: {str(e)}"
                        }
                    }
                    
        except Exception as e:
            return {
                "status": "UNHEALTHY",
                "timestamp": datetime.utcnow().isoformat(),
                "details": {
                    "registry_url": self.registry_url,
                    "error": f"Failed to connect to Registry: {str(e)}"
                }
            }

    async def comprehensive_health_check(self) -> Dict[str, Any]:
        """Perform comprehensive health check of both NiFi and Registry."""
        # Run both checks concurrently
        nifi_task = self.check_nifi_health()
        registry_task = self.check_registry_health()
        
        nifi_health, registry_health = await asyncio.gather(
            nifi_task, registry_task,
            return_exceptions=True
        )
        
        # Handle exceptions
        if isinstance(nifi_health, Exception):
            nifi_health = {
                "status": "ERROR",
                "timestamp": datetime.utcnow().isoformat(),
                "details": {
                    "nifi_url": self.nifi_url,
                    "error": f"Exception during NiFi health check: {str(nifi_health)}"
                }
            }
            
        if isinstance(registry_health, Exception):
            registry_health = {
                "status": "ERROR",
                "timestamp": datetime.utcnow().isoformat(),
                "details": {
                    "registry_url": self.registry_url,
                    "error": f"Exception during Registry health check: {str(registry_health)}"
                }
            }
        
        # Determine overall status
        statuses = [nifi_health["status"], registry_health["status"]]
        if "ERROR" in statuses or "UNHEALTHY" in statuses:
            overall_status = "UNHEALTHY"
        elif "DEGRADED" in statuses:
            overall_status = "DEGRADED"
        else:
            overall_status = "HEALTHY"
        
        return {
            "overall_status": overall_status,
            "timestamp": datetime.utcnow().isoformat(),
            "nifi": nifi_health,
            "registry": registry_health
        }

    async def get_detailed_diagnostics(self) -> Dict[str, Any]:
        """Get detailed diagnostics for troubleshooting."""
        try:
            diagnostics = {
                "timestamp": datetime.utcnow().isoformat(),
                "nifi_url": self.nifi_url,
                "registry_url": self.registry_url
            }
            
            # NiFi diagnostics
            async with NiFiAPIClient(self.nifi_url, self.nifi_auth_token) as nifi_client:
                try:
                    # Get system diagnostics
                    system_diagnostics = await nifi_client.get_system_diagnostics()
                    diagnostics["system_diagnostics"] = system_diagnostics
                    
                    # Get flow status
                    flow_status = await nifi_client.get_flow_status()
                    diagnostics["flow_status"] = flow_status
                    
                    # Get available templates
                    templates = await nifi_client.list_templates()
                    diagnostics["available_templates"] = templates
                    
                except Exception as e:
                    diagnostics["nifi_diagnostics_error"] = str(e)
            
            # Registry diagnostics
            async with NiFiRegistryClient(self.registry_url, self.registry_auth_token) as registry_client:
                try:
                    # Get buckets
                    buckets = await registry_client.list_buckets()
                    diagnostics["buckets"] = buckets
                    
                    # Get registry info
                    registry_info = await registry_client.get_registry_info()
                    diagnostics["registry_info"] = registry_info
                    
                except Exception as e:
                    diagnostics["registry_diagnostics_error"] = str(e)
            
            return diagnostics
            
        except Exception as e:
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "error": f"Failed to get detailed diagnostics: {str(e)}",
                "nifi_url": self.nifi_url,
                "registry_url": self.registry_url
            }