"""
Main menu for the EDI Lens CLI.
"""

from typing import List
from .base_menu import BaseMenu


class MainMenu(BaseMenu):
    """Main menu that serves as the entry point for all operations."""
    
    def get_menu_title(self) -> str:
        """Get the title of the main menu."""
        return "🌊 EDI Lens CLI - Main Menu"
        
    def get_menu_options(self) -> List[str]:
        """Get the list of main menu options."""
        return [
            "📁 Flow Management",
            "📋 Registry Operations", 
            "🔀 Version Control",
            "🏥 System Health",
            "⚙️ Settings"
        ]
        
    async def show(self):
        """Show the main menu and handle navigation."""
        while True:
            choice = self.show_menu_and_get_choice()
            
            # Handle the choice
            should_continue = await self.handle_menu_selection(choice)
            if not should_continue:
                # User chose to exit
                self.app.exit_application()
                break
                
    async def execute_option(self, option: int):
        """Execute the selected main menu option."""
        if option == 1:
            # Flow Management
            await self._show_flow_overview()
            self.app.navigate_to("flow")
            
        elif option == 2:
            # Registry Operations
            await self._show_registry_overview()
            self.app.navigate_to("registry")
            
        elif option == 3:
            # Version Control
            await self._show_version_control_overview()
            self.app.navigate_to("version_control")
            
        elif option == 4:
            # System Health
            self.app.navigate_to("health")
            
        elif option == 5:
            # Settings
            self.app.navigate_to("settings")
            
    async def _show_flow_overview(self):
        """Show a quick overview before entering flow management."""
        self.display.section_header("Flow Management Overview")
        
        try:
            # Get basic system status
            self.display.show_progress("Loading flow information")
            
            # Try to get some basic info (this could be expanded)
            nifi_health = await self.api_client.get_nifi_health()
            registry_health = await self.api_client.get_registry_health()
            
            self.display.complete_progress(True)
            
            if nifi_health.get("healthy") and registry_health.get("healthy"):
                self.display.success("✅ NiFi and Registry are accessible")
            else:
                self.display.warning("⚠️ Some services may not be fully accessible")
                
        except Exception as e:
            self.display.complete_progress(False)
            self.display.warning(f"Could not fetch flow overview: {e}")
            
        self.display.info("📁 Entering Flow Management...")
        
    async def _show_registry_overview(self):
        """Show a quick overview before entering registry operations."""
        self.display.section_header("Registry Overview")
        
        try:
            self.display.show_progress("Loading registry information")
            
            # Get buckets count
            buckets = await self.api_client.list_buckets()
            self.display.complete_progress(True)
            
            self.display.info(f"📋 Available buckets: {len(buckets)}")
            
            if buckets:
                self.display.info("Recent buckets:")
                for bucket in buckets[:3]:  # Show first 3 buckets
                    name = bucket.get("name", "Unknown")
                    self.display.info(f"  • {name}")
                    
        except Exception as e:
            self.display.complete_progress(False)
            self.display.warning(f"Could not fetch registry overview: {e}")
            
        self.display.info("📋 Entering Registry Operations...")
        
    async def _show_version_control_overview(self):
        """Show a quick overview before entering version control."""
        self.display.section_header("Version Control Overview")
        
        self.display.info("🔀 Version control operations allow you to:")
        self.display.info("  • Commit local changes to Registry")
        self.display.info("  • Update flows from Registry")
        self.display.info("  • Revert local modifications")
        self.display.info("  • Compare local vs Registry versions")
        
        self.display.info("🔀 Entering Version Control...")