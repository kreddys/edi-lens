"""
Registry operations menu for the EDI Lens CLI.
"""

from typing import List
from .base_menu import BaseMenu


class RegistryMenu(BaseMenu):
    """Menu for Registry operations."""
    
    def get_menu_title(self) -> str:
        """Get the title of the registry menu."""
        return "📋 Registry Operations"
        
    def get_menu_options(self) -> List[str]:
        """Get the list of registry options."""
        return [
            "📁 List Buckets",
            "📄 List Flows in Bucket",
            "👁️ View Flow Details",
            "🗑️ Delete Flow from Registry",
            "📊 Registry Statistics"
        ]
        
    async def show(self):
        """Show the registry operations menu."""
        while True:
            choice = self.show_menu_and_get_choice()
            should_continue = await self.handle_menu_selection(choice)
            if not should_continue:
                self.app.navigate_to("main")
                break
                
    async def execute_option(self, option: int):
        """Execute the selected registry option."""
        if option == 1:
            await self._list_buckets()
        elif option == 2:
            await self._list_flows_in_bucket()
        elif option == 3:
            await self._view_flow_details()
        elif option == 4:
            await self._delete_flow_from_registry()
        elif option == 5:
            await self._show_registry_statistics()
            
    async def _list_buckets(self):
        """List all Registry buckets."""
        self.display.section_header("📁 Registry Buckets")
        
        try:
            self.display.show_progress("Fetching buckets")
            buckets = await self.api_client.list_buckets()
            self.display.complete_progress(True)
            
            if not buckets:
                self.display.info("No buckets found in Registry.")
            else:
                # Prepare table data
                headers = ["Name", "ID", "Description", "Created"]
                rows = []
                
                for bucket in buckets:
                    name = bucket.get("name", "Unknown")
                    bucket_id = bucket.get("identifier", "N/A")
                    description = bucket.get("description", "")[:50] + "..." if len(bucket.get("description", "")) > 50 else bucket.get("description", "")
                    created = bucket.get("createdTimestamp", "Unknown")
                    
                    rows.append([name, bucket_id, description, created])
                    
                self.display.show_table(headers, rows, "Registry Buckets")
                
        except Exception as e:
            self.display.complete_progress(False)
            await self.show_error_details(e)
            
        self.display.pause()
        
    async def _list_flows_in_bucket(self):
        """List flows in a specific bucket."""
        self.display.section_header("📄 Flows in Bucket")
        
        bucket_id = self.display.get_user_input("Enter Bucket ID")
        if not bucket_id:
            return
            
        try:
            self.display.show_progress("Fetching flows")
            flows = await self.api_client.list_flows_in_bucket(bucket_id)
            self.display.complete_progress(True)
            
            if not flows:
                self.display.info(f"No flows found in bucket: {bucket_id}")
            else:
                # Prepare table data
                headers = ["Name", "Flow ID", "Description", "Modified"]
                rows = []
                
                for flow in flows:
                    name = flow.get("name", "Unknown")
                    flow_id = flow.get("identifier", "N/A")
                    description = flow.get("description", "")[:50] + "..." if len(flow.get("description", "")) > 50 else flow.get("description", "")
                    modified = flow.get("modifiedTimestamp", "Unknown")
                    
                    rows.append([name, flow_id, description, modified])
                    
                self.display.show_table(headers, rows, f"Flows in Bucket: {bucket_id}")
                
        except Exception as e:
            self.display.complete_progress(False)
            await self.show_error_details(e)
            
        self.display.pause()
        
    async def _view_flow_details(self):
        """View details of a specific flow."""
        self.display.section_header("👁️ Flow Details")
        
        bucket_id = self.display.get_user_input("Enter Bucket ID")
        if not bucket_id:
            return
            
        flow_id = self.display.get_user_input("Enter Flow ID")
        if not flow_id:
            return
            
        version = self.display.get_user_input("Enter Version (optional, latest if empty)")
        version = int(version) if version.isdigit() else None
        
        try:
            self.display.show_progress("Fetching flow details")
            flow_data = await self.api_client.get_flow_from_registry(bucket_id, flow_id, version)
            self.display.complete_progress(True)
            
            # Display flow information
            self.display.section_header("Flow Information")
            
            flow_info = [
                ("Name", flow_data.get("flow", {}).get("name", "Unknown")),
                ("Flow ID", flow_data.get("flow", {}).get("identifier", "N/A")),
                ("Bucket ID", bucket_id),
                ("Version", flow_data.get("version", "Unknown")),
                ("Description", flow_data.get("flow", {}).get("description", "No description")),
                ("Created", flow_data.get("flow", {}).get("createdTimestamp", "Unknown")),
                ("Modified", flow_data.get("flow", {}).get("modifiedTimestamp", "Unknown")),
            ]
            
            for label, value in flow_info:
                self.display.info(f"  {label}: {value}")
                
            # Show flow definition summary if available
            if "flowDefinition" in flow_data:
                flow_def = flow_data["flowDefinition"]
                processor_count = len(flow_def.get("processors", []))
                connection_count = len(flow_def.get("connections", []))
                
                self.display.info(f"  Processors: {processor_count}")
                self.display.info(f"  Connections: {connection_count}")
                
        except Exception as e:
            self.display.complete_progress(False)
            await self.show_error_details(e)
            
        self.display.pause()
        
    async def _delete_flow_from_registry(self):
        """Delete a flow from Registry."""
        self.display.section_header("🗑️ Delete Flow from Registry")
        self.display.warning("This operation is not yet implemented.")
        self.display.info("Use the NiFi Registry UI for flow deletion.")
        self.display.pause()
        
    async def _show_registry_statistics(self):
        """Show Registry statistics."""
        self.display.section_header("📊 Registry Statistics")
        
        try:
            self.display.show_progress("Gathering statistics")
            buckets = await self.api_client.list_buckets()
            
            # Count flows across all buckets
            total_flows = 0
            bucket_flow_counts = {}
            
            for bucket in buckets:
                bucket_id = bucket.get("identifier")
                if bucket_id:
                    try:
                        flows = await self.api_client.list_flows_in_bucket(bucket_id)
                        flow_count = len(flows)
                        bucket_flow_counts[bucket.get("name", bucket_id)] = flow_count
                        total_flows += flow_count
                    except:
                        bucket_flow_counts[bucket.get("name", bucket_id)] = "Error"
                        
            self.display.complete_progress(True)
            
            # Display statistics
            self.display.info(f"📊 Registry Statistics:")
            self.display.info(f"  Total Buckets: {len(buckets)}")
            self.display.info(f"  Total Flows: {total_flows}")
            self.display.info(f"  Registry URL: {self.config.registry_url}")
            
            if bucket_flow_counts:
                self.display.section_header("Flows per Bucket")
                for bucket_name, count in bucket_flow_counts.items():
                    self.display.info(f"  {bucket_name}: {count}")
                    
        except Exception as e:
            self.display.complete_progress(False)
            await self.show_error_details(e)
            
        self.display.pause()