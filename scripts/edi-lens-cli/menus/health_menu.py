"""
System health menu for the EDI Lens CLI.
"""

from typing import List
from .base_menu import BaseMenu


class HealthMenu(BaseMenu):
    """Menu for system health monitoring."""
    
    def get_menu_title(self) -> str:
        """Get the title of the health menu."""
        return "🏥 System Health"
        
    def get_menu_options(self) -> List[str]:
        """Get the list of health options."""
        return [
            "🔍 Quick Health Check",
            "📊 Detailed System Status",
            "🌊 NiFi Status",
            "📋 Registry Status",
            "🔗 Connectivity Test",
            "📈 System Information"
        ]
        
    async def show(self):
        """Show the health menu."""
        while True:
            choice = self.show_menu_and_get_choice()
            should_continue = await self.handle_menu_selection(choice)
            if not should_continue:
                self.app.navigate_to("main")
                break
                
    async def execute_option(self, option: int):
        """Execute the selected health option."""
        if option == 1:
            await self._quick_health_check()
        elif option == 2:
            await self._detailed_system_status()
        elif option == 3:
            await self._nifi_status()
        elif option == 4:
            await self._registry_status()
        elif option == 5:
            await self._connectivity_test()
        elif option == 6:
            await self._system_information()
            
    async def _quick_health_check(self):
        """Perform a quick health check of all services."""
        self.display.section_header("🔍 Quick Health Check")
        
        services = [
            ("Backend API", self.api_client.get_system_health),
            ("NiFi", self.api_client.get_nifi_health),
            ("Registry", self.api_client.get_registry_health)
        ]
        
        for service_name, health_check in services:
            try:
                self.display.show_progress(f"Checking {service_name}")
                result = await health_check()
                self.display.complete_progress(True)
                
                if service_name == "Backend API":
                    is_healthy = result.get("status") == "healthy"
                else:
                    is_healthy = result.get("healthy", False)
                    
                if is_healthy:
                    self.display.success(f"✅ {service_name}: Healthy")
                else:
                    self.display.error(f"❌ {service_name}: Unhealthy")
                    
            except Exception as e:
                self.display.complete_progress(False)
                self.display.error(f"❌ {service_name}: Connection failed ({e})")
                
        self.display.pause()
        
    async def _detailed_system_status(self):
        """Show detailed system status."""
        self.display.section_header("📊 Detailed System Status")
        
        try:
            # Backend status
            self.display.info("🔍 Backend API Status:")
            backend_health = await self.api_client.get_system_health()
            
            self.display.info(f"  Status: {backend_health.get('status', 'Unknown')}")
            self.display.info(f"  NiFi URL: {backend_health.get('nifi_url', 'Unknown')}")
            self.display.info(f"  Registry URL: {backend_health.get('registry_url', 'Unknown')}")
            self.display.info(f"  Debug Mode: {backend_health.get('debug', 'Unknown')}")
            
            print()  # Spacing
            
            # NiFi status
            self.display.info("🌊 NiFi Status:")
            try:
                nifi_health = await self.api_client.get_nifi_health()
                self.display.info(f"  Service: {nifi_health.get('service', 'Unknown')}")
                self.display.info(f"  URL: {nifi_health.get('url', 'Unknown')}")
                self.display.info(f"  Healthy: {nifi_health.get('healthy', 'Unknown')}")
            except Exception as e:
                self.display.error(f"  Error: {e}")
                
            print()  # Spacing
            
            # Registry status
            self.display.info("📋 Registry Status:")
            try:
                registry_health = await self.api_client.get_registry_health()
                self.display.info(f"  Service: {registry_health.get('service', 'Unknown')}")
                self.display.info(f"  URL: {registry_health.get('url', 'Unknown')}")
                self.display.info(f"  Healthy: {registry_health.get('healthy', 'Unknown')}")
            except Exception as e:
                self.display.error(f"  Error: {e}")
                
        except Exception as e:
            self.display.error(f"Failed to get system status: {e}")
            
        self.display.pause()
        
    async def _nifi_status(self):
        """Show detailed NiFi status."""
        self.display.section_header("🌊 NiFi Status")
        
        try:
            self.display.show_progress("Checking NiFi status")
            nifi_health = await self.api_client.get_nifi_health()
            self.display.complete_progress(True)
            
            self.display.info("NiFi Service Information:")
            self.display.info(f"  URL: {nifi_health.get('url', 'Unknown')}")
            self.display.info(f"  Status: {'✅ Healthy' if nifi_health.get('healthy') else '❌ Unhealthy'}")
            
            # Show quick link to NiFi UI
            nifi_url = self.config.get_nifi_ui_url()
            self.display.show_quick_links(nifi_url)
            
        except Exception as e:
            self.display.complete_progress(False)
            await self.show_error_details(e)
            
        self.display.pause()
        
    async def _registry_status(self):
        """Show detailed Registry status."""
        self.display.section_header("📋 Registry Status")
        
        try:
            self.display.show_progress("Checking Registry status")
            registry_health = await self.api_client.get_registry_health()
            self.display.complete_progress(True)
            
            self.display.info("Registry Service Information:")
            self.display.info(f"  URL: {registry_health.get('url', 'Unknown')}")
            self.display.info(f"  Status: {'✅ Healthy' if registry_health.get('healthy') else '❌ Unhealthy'}")
            
            # Try to get bucket count as additional health indicator
            try:
                buckets = await self.api_client.list_buckets()
                self.display.info(f"  Available Buckets: {len(buckets)}")
            except:
                self.display.warning("  Could not retrieve bucket information")
                
            # Show quick link to Registry UI
            registry_url = self.config.get_registry_ui_url()
            self.display.show_quick_links(self.config.nifi_url, registry_url)
            
        except Exception as e:
            self.display.complete_progress(False)
            await self.show_error_details(e)
            
        self.display.pause()
        
    async def _connectivity_test(self):
        """Test connectivity to all services."""
        self.display.section_header("🔗 Connectivity Test")
        
        endpoints = [
            ("Backend Health", "/health"),
            ("NiFi Health", "/health/nifi"),
            ("Registry Health", "/health/registry"),
            ("Registry Buckets", "/api/flows/registry/buckets")
        ]
        
        results = []
        
        for endpoint_name, endpoint_path in endpoints:
            try:
                self.display.show_progress(f"Testing {endpoint_name}")
                
                # Simple connectivity test
                if endpoint_path == "/health":
                    await self.api_client.get_system_health()
                elif endpoint_path == "/health/nifi":
                    await self.api_client.get_nifi_health()
                elif endpoint_path == "/health/registry":
                    await self.api_client.get_registry_health()
                elif endpoint_path == "/api/flows/registry/buckets":
                    await self.api_client.list_buckets()
                    
                self.display.complete_progress(True)
                results.append((endpoint_name, "✅ Success", ""))
                
            except Exception as e:
                self.display.complete_progress(False)
                results.append((endpoint_name, "❌ Failed", str(e)[:50]))
                
        # Show results table
        headers = ["Endpoint", "Status", "Error"]
        self.display.show_table(headers, results, "Connectivity Test Results")
        
        self.display.pause()
        
    async def _system_information(self):
        """Show system configuration information."""
        self.display.section_header("📈 System Information")
        
        config_info = self.config.to_dict()
        
        self.display.info("Configuration:")
        for key, value in config_info.items():
            self.display.info(f"  {key}: {value}")
            
        print()  # Spacing
        
        # CLI information
        try:
            from .. import __version__
            version = __version__
        except ImportError:
            version = "1.0.0"
            
        self.display.info("CLI Information:")
        self.display.info(f"  Version: {version}")
        self.display.info(f"  Environment: {self.config.environment}")
        self.display.info(f"  Debug Mode: {self.config.debug_mode}")
        
        self.display.pause()