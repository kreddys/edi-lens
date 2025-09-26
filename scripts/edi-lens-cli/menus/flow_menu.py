"""
Flow management menu for the EDI Lens CLI.
"""

import json
from pathlib import Path
from typing import List, Dict, Any
from .base_menu import BaseMenu


class FlowMenu(BaseMenu):
    """Menu for managing NiFi flows."""
    
    def get_menu_title(self) -> str:
        """Get the title of the flow menu."""
        return "📁 Flow Management"
        
    def get_menu_options(self) -> List[str]:
        """Get the list of flow management options."""
        return [
            "🚀 Deploy New Flow",
            "📥 Import from Registry",
            "▶️ Start Flow",
            "⏹️ Stop Flow", 
            "🗑️ Delete Flow",
            "📊 View Flow Status",
            "📋 List All Flows"
        ]
        
    async def show(self):
        """Show the flow management menu."""
        while True:
            choice = self.show_menu_and_get_choice()
            should_continue = await self.handle_menu_selection(choice)
            if not should_continue:
                self.app.navigate_to("main")
                break
                
    async def execute_option(self, option: int):
        """Execute the selected flow management option."""
        if option == 1:
            await self._deploy_new_flow()
        elif option == 2:
            await self._import_from_registry()
        elif option == 3:
            await self._start_flow()
        elif option == 4:
            await self._stop_flow()
        elif option == 5:
            await self._delete_flow()
        elif option == 6:
            await self._view_flow_status()
        elif option == 7:
            await self._list_all_flows()
            
    async def _deploy_new_flow(self):
        """Deploy a new flow from template."""
        self.display.section_header("🚀 Deploy New Flow")
        
        try:
            # Get available flow templates
            templates = await self._get_available_templates()
            
            if not templates:
                self.display.warning("No flow templates found in data/flows directory.")
                self.display.info("Please add flow template JSON files to data/flows/")
                self.display.pause()
                return
                
            # Show available templates
            self.display.info("Available flow templates:")
            template_names = list(templates.keys())
            
            for i, name in enumerate(template_names, 1):
                self.display.info(f"  {i}. {name}")
                
            # Get user selection
            while True:
                try:
                    choice = self.display.get_user_input("Select template (number)")
                    if not choice:
                        return
                        
                    template_index = int(choice) - 1
                    if 0 <= template_index < len(template_names):
                        selected_template = template_names[template_index]
                        break
                    else:
                        self.display.error("Invalid selection. Please try again.")
                except ValueError:
                    self.display.error("Please enter a valid number.")
                    
            # Load the selected template
            template_path = templates[selected_template]
            flow_definition = await self._load_flow_template(template_path)
            
            if not flow_definition:
                return
                
            self.display.success(f"✅ Loaded template: {selected_template}")
            
            # Get flow configuration
            flow_config = await self._get_flow_configuration(flow_definition)
            
            if not flow_config:
                return
                
            # Deploy the flow
            await self._perform_flow_deployment(flow_definition, flow_config)
            
        except Exception as e:
            await self.show_error_details(e)
            
    async def _get_available_templates(self) -> Dict[str, Path]:
        """Get available flow templates from the data/flows directory."""
        templates = {}
        flows_dir = self.config.get_flow_templates_dir()
        
        if not flows_dir.exists():
            flows_dir.mkdir(parents=True, exist_ok=True)
            return templates
            
        # Look for JSON files
        for file_path in flows_dir.glob("**/*.json"):
            if file_path.is_file():
                # Use relative name as the key
                relative_path = file_path.relative_to(flows_dir)
                template_name = str(relative_path).replace(".json", "")
                templates[template_name] = file_path
                
        return templates
        
    async def _load_flow_template(self, template_path: Path) -> Dict[str, Any]:
        """Load and validate a flow template."""
        try:
            with open(template_path, 'r') as f:
                flow_definition = json.load(f)
                
            # Basic validation
            required_fields = ["name", "processors"]
            for field in required_fields:
                if field not in flow_definition:
                    self.display.error(f"Invalid template: missing required field '{field}'")
                    return None
                    
            return flow_definition
            
        except json.JSONDecodeError as e:
            self.display.error(f"Invalid JSON in template: {e}")
            return None
        except Exception as e:
            self.display.error(f"Failed to load template: {e}")
            return None
            
    async def _get_flow_configuration(self, flow_definition: Dict[str, Any]) -> Dict[str, Any]:
        """Get flow configuration from user input."""
        self.display.section_header("📝 Flow Configuration")
        
        # Flow name
        default_name = flow_definition.get("name", "untitled-flow")
        flow_name = self.display.get_user_input("Flow name", default_name)
        
        # Flow description
        flow_description = self.display.get_user_input("Flow description (optional)", "")
        
        # Bucket name
        bucket_name = self.display.get_user_input("Registry bucket name", "default-bucket")
        
        # Parameters
        parameters = {}
        self.display.info("\n📋 Flow Parameters:")
        self.display.info("Enter parameter values (press Enter to skip):")
        
        # Look for parameter placeholders in the flow definition
        param_placeholders = self._extract_parameter_placeholders(flow_definition)
        
        for param_name in param_placeholders:
            param_value = self.display.get_user_input(f"  {param_name}")
            if param_value:
                parameters[param_name] = param_value
                
        # Auto-start option
        auto_start = self.display.get_yes_no("Auto-start flow after deployment?", False)
        
        return {
            "flow_name": flow_name,
            "flow_description": flow_description,
            "bucket_name": bucket_name,
            "parameters": parameters,
            "auto_start": auto_start
        }
        
    def _extract_parameter_placeholders(self, flow_definition: Dict[str, Any]) -> List[str]:
        """Extract parameter placeholders from flow definition."""
        placeholders = set()
        
        # Look for #{parameter_name} patterns in the flow definition
        def find_placeholders(obj):
            if isinstance(obj, dict):
                for value in obj.values():
                    find_placeholders(value)
            elif isinstance(obj, list):
                for item in obj:
                    find_placeholders(item)
            elif isinstance(obj, str):
                import re
                # Find #{parameter_name} patterns
                matches = re.findall(r'#\{([^}]+)\}', obj)
                placeholders.update(matches)
                
        find_placeholders(flow_definition)
        return sorted(list(placeholders))
        
    async def _perform_flow_deployment(self, flow_definition: Dict[str, Any], config: Dict[str, Any]):
        """Perform the actual flow deployment."""
        self.display.section_header("🚀 Deploying Flow")
        
        try:
            self.display.show_progress("Deploying flow to NiFi and registering in Registry")
            
            result = await self.api_client.deploy_flow(
                flow_definition=flow_definition,
                flow_name=config["flow_name"],
                bucket_id=config["bucket_name"],
                parameters=config["parameters"],
                flow_description=config["flow_description"]
            )
            
            self.display.complete_progress(True)
            
            if result.get("success"):
                self.display.success("✅ Flow deployed successfully!")
                
                process_group_id = result.get("process_group_id")
                if process_group_id:
                    self.display.info(f"Process Group ID: {process_group_id}")
                    
                    # Show quick links
                    nifi_url = self.config.get_nifi_ui_url(process_group_id)
                    registry_url = self.config.get_registry_ui_url()
                    self.display.show_quick_links(nifi_url, registry_url)
                    
                    # Auto-start if requested
                    if config.get("auto_start"):
                        self.display.info("\n▶️ Starting flow...")
                        start_result = await self.api_client.start_flow(process_group_id)
                        
                        if start_result.get("success"):
                            self.display.success("✅ Flow started successfully!")
                        else:
                            self.display.warning("⚠️ Flow deployed but failed to start")
                            
            else:
                self.display.error("❌ Flow deployment failed!")
                if "message" in result:
                    self.display.error(result["message"])
                    
        except Exception as e:
            self.display.complete_progress(False)
            await self.show_error_details(e)
            
        self.display.pause()
        
    async def _import_from_registry(self):
        """Import a flow from Registry."""
        self.display.section_header("📥 Import from Registry")
        self.display.info("This feature will be implemented to import flows from Registry.")
        self.display.pause()
        
    async def _start_flow(self):
        """Start a flow."""
        self.display.section_header("▶️ Start Flow")
        
        process_group_id = self.display.get_user_input("Enter Process Group ID")
        if not process_group_id:
            return
            
        try:
            self.display.show_progress("Starting flow")
            result = await self.api_client.start_flow(process_group_id)
            self.display.complete_progress(True)
            
            await self.show_operation_result(result, "Flow start")
            
        except Exception as e:
            self.display.complete_progress(False)
            await self.show_error_details(e)
            
    async def _stop_flow(self):
        """Stop a flow."""
        self.display.section_header("⏹️ Stop Flow")
        
        process_group_id = self.display.get_user_input("Enter Process Group ID")
        if not process_group_id:
            return
            
        try:
            self.display.show_progress("Stopping flow")
            result = await self.api_client.stop_flow(process_group_id)
            self.display.complete_progress(True)
            
            await self.show_operation_result(result, "Flow stop")
            
        except Exception as e:
            self.display.complete_progress(False)
            await self.show_error_details(e)
            
    async def _delete_flow(self):
        """Delete a flow."""
        self.display.section_header("🗑️ Delete Flow")
        
        process_group_id = self.display.get_user_input("Enter Process Group ID")
        if not process_group_id:
            return
            
        # Confirm deletion
        if not self.confirm_action("Are you sure you want to delete this flow?"):
            self.display.info("Deletion cancelled.")
            return
            
        # Ask about registry removal
        remove_from_registry = self.display.get_yes_no("Also remove from Registry?", False)
        
        try:
            self.display.show_progress("Deleting flow")
            result = await self.api_client.delete_flow(process_group_id, remove_from_registry)
            self.display.complete_progress(True)
            
            await self.show_operation_result(result, "Flow deletion")
            
        except Exception as e:
            self.display.complete_progress(False)
            await self.show_error_details(e)
            
    async def _view_flow_status(self):
        """View status of a flow."""
        self.display.section_header("📊 Flow Status")
        
        process_group_id = self.display.get_user_input("Enter Process Group ID")
        if not process_group_id:
            return
            
        try:
            self.display.show_progress("Fetching flow status")
            status = await self.api_client.get_flow_status(process_group_id)
            self.display.complete_progress(True)
            
            self.display.show_flow_status(status)
            
            # Show quick links
            nifi_url = self.config.get_nifi_ui_url(process_group_id)
            self.display.show_quick_links(nifi_url)
            
        except Exception as e:
            self.display.complete_progress(False)
            await self.show_error_details(e)
            
        self.display.pause()
        
    async def _list_all_flows(self):
        """List all flows in NiFi."""
        self.display.section_header("📋 All Flows")
        self.display.info("This feature will be implemented to list all flows.")
        self.display.pause()