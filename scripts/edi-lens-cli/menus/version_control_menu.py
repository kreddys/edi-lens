"""
Version control menu for the EDI Lens CLI.
"""

from typing import List
from .base_menu import BaseMenu


class VersionControlMenu(BaseMenu):
    """Menu for version control operations."""
    
    def get_menu_title(self) -> str:
        """Get the title of the version control menu."""
        return "🔀 Version Control Operations"
        
    def get_menu_options(self) -> List[str]:
        """Get the list of version control options."""
        return [
            "📤 Commit Changes to Registry",
            "📥 Update from Registry",
            "↩️ Revert Local Changes",
            "🔍 Check Local Modifications",
            "📊 Version History"
        ]
        
    async def show(self):
        """Show the version control menu."""
        while True:
            choice = self.show_menu_and_get_choice()
            should_continue = await self.handle_menu_selection(choice)
            if not should_continue:
                self.app.navigate_to("main")
                break
                
    async def execute_option(self, option: int):
        """Execute the selected version control option."""
        if option == 1:
            await self._commit_changes()
        elif option == 2:
            await self._update_from_registry()
        elif option == 3:
            await self._revert_changes()
        elif option == 4:
            await self._check_modifications()
        elif option == 5:
            await self._show_version_history()
            
    async def _commit_changes(self):
        """Commit local changes to Registry."""
        self.display.section_header("📤 Commit Changes to Registry")
        
        process_group_id = self.display.get_user_input("Enter Process Group ID")
        if not process_group_id:
            return
            
        comments = self.display.get_user_input("Commit comments", "Updated flow")
        
        try:
            self.display.show_progress("Committing changes to Registry")
            result = await self.api_client.commit_changes(process_group_id, comments)
            self.display.complete_progress(True)
            
            await self.show_operation_result(result, "Commit")
            
        except Exception as e:
            self.display.complete_progress(False)
            await self.show_error_details(e)
            
    async def _update_from_registry(self):
        """Update flow from Registry."""
        self.display.section_header("📥 Update from Registry")
        
        process_group_id = self.display.get_user_input("Enter Process Group ID")
        if not process_group_id:
            return
            
        # Warn about local changes
        self.display.warning("⚠️ This will overwrite any local changes!")
        if not self.confirm_action("Continue with update?"):
            self.display.info("Update cancelled.")
            return
            
        try:
            self.display.show_progress("Updating from Registry")
            result = await self.api_client.update_from_registry(process_group_id)
            self.display.complete_progress(True)
            
            await self.show_operation_result(result, "Update")
            
        except Exception as e:
            self.display.complete_progress(False)
            await self.show_error_details(e)
            
    async def _revert_changes(self):
        """Revert local changes."""
        self.display.section_header("↩️ Revert Local Changes")
        
        process_group_id = self.display.get_user_input("Enter Process Group ID")
        if not process_group_id:
            return
            
        # Confirm revert
        self.display.warning("⚠️ This will discard all local changes!")
        if not self.confirm_action("Are you sure you want to revert?"):
            self.display.info("Revert cancelled.")
            return
            
        try:
            self.display.show_progress("Reverting changes")
            result = await self.api_client.revert_changes(process_group_id)
            self.display.complete_progress(True)
            
            await self.show_operation_result(result, "Revert")
            
        except Exception as e:
            self.display.complete_progress(False)
            await self.show_error_details(e)
            
    async def _check_modifications(self):
        """Check for local modifications."""
        self.display.section_header("🔍 Local Modifications")
        
        process_group_id = self.display.get_user_input("Enter Process Group ID")
        if not process_group_id:
            return
            
        try:
            self.display.show_progress("Checking for modifications")
            modifications = await self.api_client.get_local_modifications(process_group_id)
            self.display.complete_progress(True)
            
            has_changes = modifications.get("has_local_changes", False)
            current_version = modifications.get("current_version", "Unknown")
            latest_version = modifications.get("latest_version", "Unknown")
            is_latest = modifications.get("is_latest", True)
            
            self.display.section_header("Modification Status")
            
            if has_changes:
                self.display.warning("⚠️ Local changes detected!")
            else:
                self.display.success("✅ No local changes")
                
            self.display.info(f"Current Version: {current_version}")
            self.display.info(f"Latest Version: {latest_version}")
            
            if not is_latest:
                self.display.warning("⚠️ Flow is not at the latest version")
            else:
                self.display.success("✅ Flow is at the latest version")
                
            # Show differences if available
            differences = modifications.get("differences", {})
            if differences:
                self.display.section_header("Differences")
                for key, value in differences.items():
                    self.display.info(f"  {key}: {value}")
                    
        except Exception as e:
            self.display.complete_progress(False)
            await self.show_error_details(e)
            
        self.display.pause()
        
    async def _show_version_history(self):
        """Show version history for a flow."""
        self.display.section_header("📊 Version History")
        self.display.info("Version history feature not yet implemented.")
        self.display.info("Use the NiFi Registry UI to view version history.")
        self.display.pause()