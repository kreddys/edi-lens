"""
EDI Lens CLI Application - Main application class and menu system.
"""

import asyncio
import json
from pathlib import Path
from typing import Dict, Any, Optional

from api.client import EDILensAPIClient
from menus.main_menu import MainMenu
from menus.flow_menu import FlowMenu
from menus.registry_menu import RegistryMenu
from menus.version_control_menu import VersionControlMenu
from menus.health_menu import HealthMenu
from menus.settings_menu import SettingsMenu
from utils.display import Display
from utils.config import Config


class EDILensCLI:
    """Main CLI application class that coordinates all menus and operations."""
    
    def __init__(self, non_interactive: bool = False, quiet_mode: bool = False, 
                 output_format: str = "table", backend_url: Optional[str] = None):
        """Initialize the CLI application."""
        self.config = Config()
        
        # Override backend URL if provided
        if backend_url:
            self.config.backend_url = backend_url
            
        self.display = Display()
        self.api_client: Optional[EDILensAPIClient] = None
        self.current_menu = "main"
        self.running = True
        
        # Non-interactive mode settings
        self.non_interactive = non_interactive
        self.quiet_mode = quiet_mode
        self.output_format = output_format
        
        # Initialize menus
        self.menus = {}
        
    async def initialize(self):
        """Initialize the application and check system health."""
        if not self.non_interactive and not self.quiet_mode:
            self.display.show_header()
            self.display.info("Initializing EDI Lens CLI...")
        
        # Initialize API client
        self.api_client = EDILensAPIClient(
            base_url=self.config.backend_url,
            timeout=self.config.request_timeout
        )
        
        # Initialize menus with dependencies (only needed for interactive mode)
        if not self.non_interactive:
            self.menus = {
                "main": MainMenu(self),
                "flow": FlowMenu(self),
                "registry": RegistryMenu(self),
                "version_control": VersionControlMenu(self),
                "health": HealthMenu(self),
                "settings": SettingsMenu(self)
            }
        
        # Quick health check (skip for non-interactive mode unless it's a health command)
        if not self.non_interactive:
            await self._initial_health_check()
        
    async def _initial_health_check(self):
        """Perform initial health check to ensure connectivity."""
        if not self.quiet_mode:
            self.display.info("🏥 Checking system health...")
        
        try:
            health_status = await self.api_client.get_system_health()
            
            # Display health status
            if health_status.get("status") == "healthy":
                if not self.quiet_mode:
                    self.display.success("✅ Backend API: Healthy")
            else:
                self.display.warning("⚠️ Backend API: Issues detected")
                
            # Check NiFi and Registry
            nifi_health = await self.api_client.get_nifi_health()
            if nifi_health.get("healthy"):
                if not self.quiet_mode:
                    self.display.success("✅ NiFi: Healthy")
            else:
                self.display.error("❌ NiFi: Not accessible")
                
            registry_health = await self.api_client.get_registry_health()
            if registry_health.get("healthy"):
                if not self.quiet_mode:
                    self.display.success("✅ Registry: Healthy")
            else:
                self.display.error("❌ Registry: Not accessible")
                
        except Exception as e:
            self.display.error(f"❌ Health check failed: {e}")
            self.display.warning("Some features may not be available.")
            
        if not self.quiet_mode:
            print()  # Add spacing
        
    async def run(self):
        """Main application loop."""
        await self.initialize()
        
        while self.running:
            try:
                current_menu = self.menus.get(self.current_menu)
                if current_menu:
                    await current_menu.show()
                else:
                    self.display.error(f"Unknown menu: {self.current_menu}")
                    self.current_menu = "main"
                    
            except KeyboardInterrupt:
                self.display.info("\n🔄 Returning to main menu...")
                self.current_menu = "main"
                await asyncio.sleep(0.5)
            except Exception as e:
                self.display.error(f"❌ Menu error: {e}")
                self.display.info("Returning to main menu...")
                self.current_menu = "main"
                await asyncio.sleep(1)
                
        self.display.info("👋 Thanks for using EDI Lens CLI!")
        
    def navigate_to(self, menu_name: str):
        """Navigate to a specific menu."""
        if menu_name in self.menus:
            self.current_menu = menu_name
        else:
            self.display.error(f"Invalid menu: {menu_name}")
            
    def exit_application(self):
        """Exit the application."""
        self.running = False
        
    async def get_flow_templates(self) -> Dict[str, Any]:
        """Get available flow templates from the data/flows directory."""
        templates = {}
        flows_dir = self.config.get_flow_templates_dir()
        
        if not flows_dir.exists():
            return templates
            
        # Look for JSON files
        for file_path in flows_dir.glob("**/*.json"):
            if file_path.is_file():
                # Use relative name as the key
                relative_path = file_path.relative_to(flows_dir)
                template_name = str(relative_path).replace(".json", "")
                templates[template_name] = file_path
                
        return templates

    # Non-interactive command execution methods
    async def run_command(self, command: str, args):
        """Execute a single command non-interactively."""
        await self.initialize()
        
        try:
            if command == "health-check":
                await self._cmd_health_check()
            elif command == "system-status":
                await self._cmd_system_status()
            elif command == "deploy-flow":
                await self._cmd_deploy_flow(args)
            elif command == "start-flow":
                await self._cmd_start_flow(args)
            elif command == "stop-flow":
                await self._cmd_stop_flow(args)
            elif command == "delete-flow":
                await self._cmd_delete_flow(args)
            elif command == "flow-status":
                await self._cmd_flow_status(args)
            elif command == "list-buckets":
                await self._cmd_list_buckets()
            elif command == "list-flows-in-bucket":
                await self._cmd_list_flows_in_bucket(args)
            elif command == "commit-changes":
                await self._cmd_commit_changes(args)
            elif command == "update-from-registry":
                await self._cmd_update_from_registry(args)
            elif command == "revert-changes":
                await self._cmd_revert_changes(args)
            elif command == "check-modifications":
                await self._cmd_check_modifications(args)
            else:
                print(f"❌ Unknown command: {command}")
                return False
                
            return True
            
        except Exception as e:
            print(f"❌ Command failed: {e}")
            return False
            
    async def run_batch_file(self, batch_file: Path):
        """Execute commands from a batch file."""
        if not batch_file.exists():
            print(f"❌ Batch file not found: {batch_file}")
            return False
            
        await self.initialize()
        
        try:
            with open(batch_file, 'r') as f:
                lines = f.readlines()
                
            for line_num, line in enumerate(lines, 1):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                    
                print(f"🔄 Executing line {line_num}: {line}")
                
                # Parse command line (simple implementation)
                parts = line.split()
                if not parts:
                    continue
                    
                # This is a simplified parser - could be enhanced
                command = parts[0]
                # Convert remaining parts to args object (simplified)
                args_dict = {}
                i = 1
                while i < len(parts):
                    if parts[i].startswith('--'):
                        key = parts[i][2:].replace('-', '_')
                        if i + 1 < len(parts) and not parts[i + 1].startswith('--'):
                            args_dict[key] = parts[i + 1]
                            i += 2
                        else:
                            args_dict[key] = True
                            i += 1
                    else:
                        i += 1
                        
                # Create args object
                class Args:
                    def __init__(self, **kwargs):
                        for k, v in kwargs.items():
                            setattr(self, k, v)
                            
                args = Args(**args_dict)
                
                success = await self.run_command(command, args)
                if not success:
                    print(f"❌ Batch execution stopped at line {line_num}")
                    return False
                    
        except Exception as e:
            print(f"❌ Batch execution failed: {e}")
            return False
            
        return True
        
    def _output_data(self, data, title: str = ""):
        """Output data in the specified format."""
        if self.quiet_mode and self.output_format != "json":
            return
            
        if self.output_format == "json":
            print(json.dumps(data, indent=2))
        elif self.output_format == "table":
            if isinstance(data, list) and data:
                if isinstance(data[0], dict):
                    headers = list(data[0].keys())
                    rows = [[str(item.get(h, "")) for h in headers] for item in data]
                    self.display.show_table(headers, rows, title)
                else:
                    print(f"{title}: {data}")
            else:
                print(f"{title}: {data}")
        else:
            print(data)

    # Command implementations
    async def _cmd_health_check(self):
        """Execute health check command."""
        try:
            health_data = {}
            
            # Backend health
            backend_health = await self.api_client.get_system_health()
            health_data["backend"] = {
                "status": backend_health.get("status"),
                "url": self.config.backend_url
            }
            
            # NiFi health
            nifi_health = await self.api_client.get_nifi_health()
            health_data["nifi"] = {
                "healthy": nifi_health.get("healthy"),
                "url": nifi_health.get("url")
            }
            
            # Registry health
            registry_health = await self.api_client.get_registry_health()
            health_data["registry"] = {
                "healthy": registry_health.get("healthy"),
                "url": registry_health.get("url")
            }
            
            self._output_data(health_data, "System Health")
            
            # Exit code based on health
            all_healthy = (
                backend_health.get("status") == "healthy" and
                nifi_health.get("healthy") and
                registry_health.get("healthy")
            )
            
            if not all_healthy:
                exit(1)
                
        except Exception as e:
            print(f"❌ Health check failed: {e}")
            exit(1)

    async def _cmd_deploy_flow(self, args):
        """Execute deploy flow command."""
        if not args.template:
            print("❌ Template name is required for deploy-flow command")
            return
            
        # Load template
        templates = await self.get_flow_templates()
        if args.template not in templates:
            print(f"❌ Template '{args.template}' not found")
            print(f"Available templates: {list(templates.keys())}")
            return
            
        template_path = templates[args.template]
        
        try:
            with open(template_path, 'r') as f:
                flow_definition = json.load(f)
        except Exception as e:
            print(f"❌ Failed to load template: {e}")
            return
            
        # Parse parameters - start with template defaults
        parameters = {}

        # First, add template default parameters if they exist
        template_params = flow_definition.get("parameters", {})
        for param_name, param_def in template_params.items():
            if isinstance(param_def, dict) and "default" in param_def:
                parameters[param_name] = param_def["default"]

        # Then override with CLI-provided parameters
        if args.params:
            for param in args.params:
                if '=' in param:
                    key, value = param.split('=', 1)
                    parameters[key] = value
                    
        # Deploy flow
        try:
            result = await self.api_client.deploy_flow(
                flow_definition=flow_definition,
                flow_name=flow_definition.get("name", args.template),
                bucket_id="default-bucket",
                parameters=parameters,
                flow_description=flow_definition.get("description", "")
            )
            
            if result.get("success"):
                process_group_id = result.get("process_group_id")
                print(f"✅ Flow deployed successfully! Process Group ID: {process_group_id}")
                
                if args.auto_start and process_group_id:
                    print("🔄 Auto-starting flow...")
                    start_result = await self.api_client.start_flow(process_group_id)
                    if start_result.get("success"):
                        print("✅ Flow started successfully!")
                    else:
                        print("⚠️ Flow deployed but failed to start")
                        
                self._output_data(result, "Deployment Result")
            else:
                print("❌ Flow deployment failed")
                self._output_data(result, "Deployment Error")
                
        except Exception as e:
            print(f"❌ Deployment failed: {e}")

    async def _cmd_start_flow(self, args):
        """Execute start flow command."""
        if not args.process_group_id:
            print("❌ Process Group ID is required for start-flow command")
            return
            
        try:
            result = await self.api_client.start_flow(args.process_group_id)
            if result.get("success"):
                print(f"✅ Flow {args.process_group_id} started successfully")
            else:
                print(f"❌ Failed to start flow {args.process_group_id}")
                
            self._output_data(result, "Start Flow Result")
            
        except Exception as e:
            print(f"❌ Start flow failed: {e}")

    async def _cmd_stop_flow(self, args):
        """Execute stop flow command."""
        if not args.process_group_id:
            print("❌ Process Group ID is required for stop-flow command")
            return
            
        try:
            result = await self.api_client.stop_flow(args.process_group_id)
            if result.get("success"):
                print(f"✅ Flow {args.process_group_id} stopped successfully")
            else:
                print(f"❌ Failed to stop flow {args.process_group_id}")
                
            self._output_data(result, "Stop Flow Result")
            
        except Exception as e:
            print(f"❌ Stop flow failed: {e}")

    async def _cmd_delete_flow(self, args):
        """Execute delete flow command."""
        if not args.process_group_id:
            print("❌ Process Group ID is required for delete-flow command")
            return
            
        try:
            result = await self.api_client.delete_flow(
                args.process_group_id, 
                args.remove_from_registry
            )
            if result.get("success"):
                print(f"✅ Flow {args.process_group_id} deleted successfully")
            else:
                print(f"❌ Failed to delete flow {args.process_group_id}")
                
            self._output_data(result, "Delete Flow Result")
            
        except Exception as e:
            print(f"❌ Delete flow failed: {e}")

    async def _cmd_flow_status(self, args):
        """Execute flow status command."""
        if not args.process_group_id:
            print("❌ Process Group ID is required for flow-status command")
            return
            
        try:
            result = await self.api_client.get_flow_status(args.process_group_id)
            print(f"📊 Flow Status for {args.process_group_id}:")
            self._output_data(result, "Flow Status")
            
        except Exception as e:
            print(f"❌ Get flow status failed: {e}")

    async def _cmd_list_buckets(self):
        """Execute list buckets command."""
        try:
            buckets = await self.api_client.list_buckets()
            if not self.quiet_mode:
                print(f"📋 Found {len(buckets)} Registry buckets:")
            self._output_data(buckets, "Registry Buckets")
            
        except Exception as e:
            print(f"❌ List buckets failed: {e}")

    async def _cmd_list_flows_in_bucket(self, args):
        """Execute list flows in bucket command."""
        if not args.bucket_id:
            print("❌ Bucket ID is required for list-flows-in-bucket command")
            return
            
        try:
            flows = await self.api_client.list_flows_in_bucket(args.bucket_id)
            if not self.quiet_mode:
                print(f"📄 Found {len(flows)} flows in bucket {args.bucket_id}:")
            self._output_data(flows, f"Flows in Bucket {args.bucket_id}")
            
        except Exception as e:
            print(f"❌ List flows failed: {e}")

    async def _cmd_commit_changes(self, args):
        """Execute commit changes command."""
        if not args.process_group_id:
            print("❌ Process Group ID is required for commit-changes command")
            return
            
        try:
            result = await self.api_client.commit_changes(
                args.process_group_id, 
                args.comments
            )
            if result.get("success"):
                print(f"✅ Changes committed for flow {args.process_group_id}")
            else:
                print(f"❌ Failed to commit changes for flow {args.process_group_id}")
                
            self._output_data(result, "Commit Result")
            
        except Exception as e:
            print(f"❌ Commit changes failed: {e}")

    async def _cmd_update_from_registry(self, args):
        """Execute update from registry command."""
        if not args.process_group_id:
            print("❌ Process Group ID is required for update-from-registry command")
            return
            
        try:
            result = await self.api_client.update_from_registry(args.process_group_id)
            if result.get("success"):
                print(f"✅ Flow {args.process_group_id} updated from Registry")
            else:
                print(f"❌ Failed to update flow {args.process_group_id} from Registry")
                
            self._output_data(result, "Update Result")
            
        except Exception as e:
            print(f"❌ Update from registry failed: {e}")

    async def _cmd_revert_changes(self, args):
        """Execute revert changes command."""
        if not args.process_group_id:
            print("❌ Process Group ID is required for revert-changes command")
            return
            
        try:
            result = await self.api_client.revert_changes(args.process_group_id)
            if result.get("success"):
                print(f"✅ Changes reverted for flow {args.process_group_id}")
            else:
                print(f"❌ Failed to revert changes for flow {args.process_group_id}")
                
            self._output_data(result, "Revert Result")
            
        except Exception as e:
            print(f"❌ Revert changes failed: {e}")

    async def _cmd_check_modifications(self, args):
        """Execute check modifications command."""
        if not args.process_group_id:
            print("❌ Process Group ID is required for check-modifications command")
            return
            
        try:
            result = await self.api_client.get_local_modifications(args.process_group_id)
            
            has_changes = result.get("has_local_changes", False)
            print(f"🔍 Modification status for {args.process_group_id}:")
            print(f"  Local changes: {'Yes' if has_changes else 'No'}")
            print(f"  Current version: {result.get('current_version', 'Unknown')}")
            print(f"  Latest version: {result.get('latest_version', 'Unknown')}")
            
            self._output_data(result, "Modification Status")
            
        except Exception as e:
            print(f"❌ Check modifications failed: {e}")

    async def _cmd_system_status(self):
        """Execute system status command."""
        try:
            # Gather comprehensive status
            status_data = {}
            
            # Backend info
            backend_health = await self.api_client.get_system_health()
            status_data["backend"] = backend_health
            
            # NiFi info
            nifi_health = await self.api_client.get_nifi_health()
            status_data["nifi"] = nifi_health
            
            # Registry info
            registry_health = await self.api_client.get_registry_health()
            status_data["registry"] = registry_health
            
            # Registry stats
            try:
                buckets = await self.api_client.list_buckets()
                status_data["registry_stats"] = {
                    "bucket_count": len(buckets),
                    "buckets": [{"name": b.get("name"), "id": b.get("identifier")} for b in buckets[:5]]
                }
            except:
                status_data["registry_stats"] = {"error": "Unable to fetch stats"}
            
            if not self.quiet_mode:
                print("📊 System Status Summary:")
            self._output_data(status_data, "System Status")
            
        except Exception as e:
            print(f"❌ System status check failed: {e}")