"""
Settings menu for the EDI Lens CLI.
"""

from typing import List
from .base_menu import BaseMenu


class SettingsMenu(BaseMenu):
    """Menu for CLI settings and configuration."""
    
    def get_menu_title(self) -> str:
        """Get the title of the settings menu."""
        return "⚙️ Settings & Configuration"
        
    def get_menu_options(self) -> List[str]:
        """Get the list of settings options."""
        return [
            "📋 View Current Configuration",
            "🌐 Change Backend URL",
            "📁 Manage Data Directories",
            "🎨 Display Settings",
            "🔧 Reset to Defaults",
            "ℹ️ About EDI Lens CLI"
        ]
        
    async def show(self):
        """Show the settings menu."""
        while True:
            choice = self.show_menu_and_get_choice()
            should_continue = await self.handle_menu_selection(choice)
            if not should_continue:
                self.app.navigate_to("main")
                break
                
    async def execute_option(self, option: int):
        """Execute the selected settings option."""
        if option == 1:
            await self._view_configuration()
        elif option == 2:
            await self._change_backend_url()
        elif option == 3:
            await self._manage_data_directories()
        elif option == 4:
            await self._display_settings()
        elif option == 5:
            await self._reset_to_defaults()
        elif option == 6:
            await self._show_about()
            
    async def _view_configuration(self):
        """View current configuration."""
        self.display.section_header("📋 Current Configuration")
        
        config_data = self.config.to_dict()
        
        # Create table for configuration
        headers = ["Setting", "Value"]
        rows = [[key, str(value)] for key, value in config_data.items()]
        
        self.display.show_table(headers, rows, "Configuration Settings")
        
        self.display.pause()
        
    async def _change_backend_url(self):
        """Change the backend API URL."""
        self.display.section_header("🌐 Change Backend URL")
        
        self.display.info(f"Current Backend URL: {self.config.backend_url}")
        
        new_url = self.display.get_user_input("Enter new Backend URL", self.config.backend_url)
        
        if new_url and new_url != self.config.backend_url:
            # Validate the URL format
            if not (new_url.startswith("http://") or new_url.startswith("https://")):
                self.display.error("Invalid URL format. Must start with http:// or https://")
                self.display.pause()
                return
                
            # Test connectivity to new URL
            self.display.show_progress("Testing connection to new URL")
            
            # Create a temporary API client to test
            from api.client import EDILensAPIClient
            test_client = EDILensAPIClient(base_url=new_url)
            
            try:
                await test_client.get_system_health()
                self.display.complete_progress(True)
                
                # Update configuration
                self.config.backend_url = new_url
                self.app.api_client = EDILensAPIClient(base_url=new_url)
                
                self.display.success(f"✅ Backend URL updated to: {new_url}")
                
            except Exception as e:
                self.display.complete_progress(False)
                self.display.error(f"Failed to connect to new URL: {e}")
                
            finally:
                await test_client.close()
        else:
            self.display.info("No changes made.")
            
        self.display.pause()
        
    async def _manage_data_directories(self):
        """Manage data directories."""
        self.display.section_header("📁 Data Directories")
        
        directories = [
            ("Data Directory", self.config.data_dir),
            ("Flows Directory", self.config.flows_dir),
            ("Test Data Directory", self.config.test_data_dir)
        ]
        
        self.display.info("Current directories:")
        for name, path in directories:
            exists = "✅" if path.exists() else "❌"
            self.display.info(f"  {name}: {path} {exists}")
            
        print()  # Spacing
        
        if self.display.get_yes_no("Create missing directories?", True):
            self.config.ensure_directories()
            self.display.success("✅ Directories created/verified")
        else:
            self.display.info("No changes made.")
            
        self.display.pause()
        
    async def _display_settings(self):
        """Configure display settings."""
        self.display.section_header("🎨 Display Settings")
        
        self.display.info(f"Current display width: {self.display.width}")
        self.display.info(f"Colors enabled: {self.display.colors_enabled}")
        self.display.info(f"Items per page: {self.config.items_per_page}")
        
        print()  # Spacing
        
        # Allow changing display width
        new_width = self.display.get_user_input("Display width", str(self.display.width))
        
        try:
            width = int(new_width)
            if 40 <= width <= 200:
                self.display.width = width
                self.display.success(f"✅ Display width set to {width}")
            else:
                self.display.error("Width must be between 40 and 200")
        except ValueError:
            self.display.error("Invalid width value")
            
        self.display.pause()
        
    async def _reset_to_defaults(self):
        """Reset settings to defaults."""
        self.display.section_header("🔧 Reset to Defaults")
        
        self.display.warning("⚠️ This will reset all settings to their default values.")
        
        if self.confirm_action("Are you sure you want to reset all settings?"):
            # Reset configuration
            self.config.backend_url = "http://localhost:8000"
            self.display.width = 80
            self.config.items_per_page = 10
            
            # Recreate API client with default URL
            from api.client import EDILensAPIClient
            self.app.api_client = EDILensAPIClient()
            
            self.display.success("✅ Settings reset to defaults")
        else:
            self.display.info("Reset cancelled.")
            
        self.display.pause()
        
    async def _show_about(self):
        """Show information about the CLI."""
        self.display.section_header("ℹ️ About EDI Lens CLI")
        
        about_text = """
🌊 EDI Lens CLI - Interactive NiFi Flow Manager

Version: 1.0.0
Author: EDI Lens Team

Description:
A powerful command-line interface for managing Apache NiFi flows,
Registry operations, and version control. This tool provides an
interactive way to deploy, monitor, and maintain EDI processing
workflows.

Features:
• 🚀 Deploy flows from templates
• 📋 Manage Registry buckets and flows  
• 🔀 Version control operations
• 🏥 System health monitoring
• ⚙️ Configuration management

GitHub: https://github.com/your-org/edi-lens
Documentation: https://docs.edi-lens.com

© 2024 EDI Lens Team. All rights reserved.
"""
        
        print(about_text)
        
        self.display.pause()