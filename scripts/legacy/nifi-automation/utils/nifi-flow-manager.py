#!/usr/bin/env python3
"""
NiFi Flow Manager - YAML-based flow creation and management
Supports creating, deleting, and managing NiFi flows from YAML configurations
"""

import requests
import json
import time
import sys
import yaml
import os
from typing import Dict, Any, List, Optional
from pathlib import Path

class NiFiFlowManager:
    def __init__(self, nifi_url: str = "http://localhost:8080", username: str = "superuser@edilens.com", password: str = "password123456789"):
        self.base_url = f"{nifi_url}/nifi-api"
        self.session = requests.Session()
        self.process_group_id = "root"
        self.username = username
        self.password = password
        self.token = None
        self.created_processors = {}  # Track created processors by ID
        self.created_connections = {}  # Track created connections by ID
        
    def authenticate(self) -> bool:
        """Authenticate with NiFi and get access token"""
        try:
            print("🔐 Authenticating with NiFi...")
            
            response = self.session.post(
                f"{self.base_url}/access/token",
                data={"username": self.username, "password": self.password},
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            if response.status_code == 201:
                self.token = response.text
                self.session.headers.update({"Authorization": f"Bearer {self.token}"})
                print("✅ Authentication successful!")
                return True
            else:
                print(f"❌ Authentication failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Authentication error: {e}")
            return False
    
    def wait_for_nifi(self, timeout: int = 60) -> bool:
        """Wait for NiFi to be available and authenticate"""
        print("⏳ Waiting for NiFi to be available...")
        
        for i in range(timeout):
            try:
                response = self.session.get(f"{self.base_url}/access/config")
                if response.status_code in [200, 401]:
                    print("✅ NiFi is available!")
                    return self.authenticate()
            except:
                pass
            
            if i % 10 == 0:
                print(f"⏳ Still waiting... ({i}/{timeout}s)")
            time.sleep(1)
        
        print("❌ Timeout waiting for NiFi")
        return False
    
    def get_process_group_id(self) -> str:
        """Get the root process group ID"""
        try:
            response = self.session.get(f"{self.base_url}/flow/process-groups/root")
            response.raise_for_status()
            return response.json()["processGroupFlow"]["id"]
        except Exception as e:
            print(f"❌ Failed to get process group ID: {e}")
            return "root"
    
    def load_flow_config(self, config_path: str) -> Dict[str, Any]:
        """Load flow configuration from YAML file"""
        try:
            with open(config_path, 'r') as file:
                config = yaml.safe_load(file)
                print(f"✅ Loaded flow configuration: {config['flow']['name']}")
                return config
        except Exception as e:
            print(f"❌ Failed to load flow config from {config_path}: {e}")
            return None
    
    def list_existing_processors(self) -> List[Dict[str, Any]]:
        """Get list of existing processors in the root group"""
        try:
            response = self.session.get(f"{self.base_url}/process-groups/{self.process_group_id}/processors")
            response.raise_for_status()
            processors = response.json()["processors"]
            return processors
        except Exception as e:
            print(f"❌ Failed to list processors: {e}")
            return []
    
    def delete_processor(self, processor_id: str, revision: int) -> bool:
        """Delete a processor"""
        try:
            # Stop processor first if running
            self.stop_processor(processor_id, revision)
            time.sleep(1)
            
            # Get current revision and state
            response = self.session.get(f"{self.base_url}/processors/{processor_id}")
            if response.status_code == 200:
                processor_data = response.json()
                current_revision = processor_data["revision"]["version"]
                validation_errors = processor_data["component"].get("validationErrors", [])
                
                # If processor has validation errors, try to fix them by auto-terminating relationships
                if validation_errors:
                    print(f"🔧 Fixing validation errors for processor {processor_id}")
                    
                    # Get all relationships and auto-terminate them
                    relationships = processor_data["component"].get("relationships", [])
                    auto_terminated = []
                    for rel in relationships:
                        auto_terminated.append(rel["name"])
                    
                    # Update processor to auto-terminate all relationships
                    update_data = {
                        "revision": {"version": current_revision},
                        "component": {
                            "id": processor_id,
                            "config": {
                                "autoTerminatedRelationships": auto_terminated
                            }
                        }
                    }
                    
                    update_response = self.session.put(
                        f"{self.base_url}/processors/{processor_id}",
                        json=update_data,
                        headers={"Content-Type": "application/json"}
                    )
                    
                    if update_response.status_code == 200:
                        print(f"🔧 Fixed validation errors for processor {processor_id}")
                        current_revision = update_response.json()["revision"]["version"]
                        time.sleep(1)  # Wait for update to take effect
                    else:
                        print(f"⚠️ Failed to fix validation errors: {update_response.status_code}")
            else:
                current_revision = revision
            
            # Delete processor
            response = self.session.delete(
                f"{self.base_url}/processors/{processor_id}",
                params={"version": current_revision}
            )
            
            if response.status_code == 200:
                return True
            else:
                print(f"⚠️ Failed to delete processor {processor_id}: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Error deleting processor {processor_id}: {e}")
            return False
    
    def stop_processor(self, processor_id: str, revision: int = None) -> bool:
        """Stop a processor"""
        try:
            # Get current revision if not provided
            if revision is None:
                response = self.session.get(f"{self.base_url}/processors/{processor_id}")
                if response.status_code != 200:
                    return False
                revision = response.json()["revision"]["version"]
            
            stop_data = {
                "revision": {"version": revision},
                "state": "STOPPED"
            }
            
            response = self.session.put(
                f"{self.base_url}/processors/{processor_id}/run-status",
                json=stop_data,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                return True
            else:
                # Try alternative format
                stop_data = {
                    "revision": {"version": revision},
                    "component": {"state": "STOPPED"}
                }
                
                response = self.session.put(
                    f"{self.base_url}/processors/{processor_id}/run-status",
                    json=stop_data,
                    headers={"Content-Type": "application/json"}
                )
                return response.status_code == 200
        except:
            return False
    
    def list_existing_connections(self) -> List[Dict[str, Any]]:
        """Get list of existing connections in the root group"""
        try:
            response = self.session.get(f"{self.base_url}/process-groups/{self.process_group_id}/connections")
            response.raise_for_status()
            connections = response.json()["connections"]
            return connections
        except Exception as e:
            print(f"❌ Failed to list connections: {e}")
            return []
    
    def delete_connection(self, connection_id: str, revision: int) -> bool:
        """Delete a connection"""
        try:
            response = self.session.delete(
                f"{self.base_url}/connections/{connection_id}",
                params={"version": revision}
            )
            
            if response.status_code == 200:
                print(f"✅ Deleted connection: {connection_id}")
                return True
            else:
                print(f"⚠️ Failed to delete connection {connection_id}: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Error deleting connection {connection_id}: {e}")
            return False
    
    def persistent_data_cleanup(self) -> bool:
        """Ultimate cleanup - handles persistent data in NiFi volumes"""
        print("🗑️ PERSISTENT DATA CLEANUP: Removing all flows and clearing NiFi data")
        print("⚠️ This will completely reset NiFi to a clean state")
        
        import subprocess
        import time
        
        try:
            # Step 1: Stop NiFi container
            print("🛑 Stopping NiFi container...")
            subprocess.run(["docker", "stop", "nifi"], check=False, capture_output=True)
            time.sleep(5)
            
            # Step 2: Remove NiFi data volume (this clears all persistent flows)
            print("🗑️ Clearing NiFi persistent data...")
            result = subprocess.run(["docker", "volume", "ls", "-q"], capture_output=True, text=True)
            volumes = result.stdout.strip().split('\n')
            
            nifi_volumes = [v for v in volumes if 'nifi' in v.lower()]
            for volume in nifi_volumes:
                if volume.strip():
                    print(f"🗑️ Removing volume: {volume}")
                    subprocess.run(["docker", "volume", "rm", volume], check=False, capture_output=True)
            
            # Step 3: Restart NiFi container
            print("🚀 Starting NiFi container...")
            subprocess.run(["docker", "start", "nifi"], check=False, capture_output=True)
            
            # Step 4: Wait for NiFi to be ready
            print("⏳ Waiting for NiFi to initialize (this may take 2-3 minutes)...")
            max_attempts = 36  # 3 minutes
            for attempt in range(max_attempts):
                try:
                    response = self.session.get(f"{self.base_url}/system-diagnostics", timeout=5)
                    if response.status_code == 200:
                        print("✅ NiFi is ready!")
                        break
                except:
                    pass
                
                if attempt % 6 == 0:
                    print(f"⏳ Still waiting... ({attempt}/{max_attempts})")
                time.sleep(5)
            else:
                print("⚠️ NiFi may still be starting. Check manually.")
            
            # Step 5: Redeploy EDI processors
            print("📦 Redeploying EDI processors...")
            subprocess.run(["bash", "-c", "cd docker/nifi-processors && ./deploy-edi-processors.sh volume"], 
                         check=False, capture_output=True)
            
            print("✅ PERSISTENT DATA CLEANUP COMPLETED!")
            print("🎯 NiFi is now in a completely clean state")
            return True
            
        except Exception as e:
            print(f"❌ Error during persistent data cleanup: {e}")
            return False

    def nuclear_cleanup(self) -> bool:
        """Nuclear option - delete everything by force, handling all edge cases"""
        print("☢️ NUCLEAR CLEANUP: Forcefully removing all processors and connections")
        print("⚠️ This will stop all processors, clear queues, and delete everything")
        
        # Ensure we have the correct process group ID
        if self.process_group_id == "root":
            actual_id = self.get_process_group_id()
            if actual_id and actual_id != "root":
                self.process_group_id = actual_id
        
        import time
        
        # Step 1: Force stop ALL processors multiple times
        for attempt in range(3):
            print(f"🛑 Stop attempt {attempt + 1}/3...")
            processors = self.list_existing_processors()
            
            for proc in processors:
                proc_id = proc["id"]
                name = proc.get("component", {}).get("name", "Unknown")
                
                # Try multiple stop methods
                for stop_attempt in range(2):
                    try:
                        # Get fresh revision
                        fresh_response = self.session.get(f"{self.base_url}/processors/{proc_id}")
                        if fresh_response.status_code == 200:
                            revision = fresh_response.json()["revision"]["version"]
                            
                            # Force stop
                            stop_data = {"revision": {"version": revision}, "state": "STOPPED"}
                            self.session.put(f"{self.base_url}/processors/{proc_id}/run-status", 
                                           json=stop_data, headers={"Content-Type": "application/json"})
                            time.sleep(0.5)
                    except:
                        pass
            
            time.sleep(2)
        
        # Step 2: Clear all queues by deleting connections aggressively
        print("🧹 Clearing queues by deleting connections...")
        for attempt in range(3):
            connections = self.list_existing_connections()
            if not connections:
                break
                
            print(f"🔗 Connection deletion attempt {attempt + 1}/3 ({len(connections)} connections)")
            
            for conn in connections:
                try:
                    conn_id = conn["id"]
                    # Get fresh revision
                    fresh_response = self.session.get(f"{self.base_url}/connections/{conn_id}")
                    if fresh_response.status_code == 200:
                        revision = fresh_response.json()["revision"]["version"]
                    else:
                        revision = conn["revision"]["version"]
                    
                    # Force delete connection
                    self.session.delete(f"{self.base_url}/connections/{conn_id}", 
                                      params={"version": revision})
                except:
                    pass
            
            time.sleep(2)
        
        # Step 3: Auto-terminate all relationships on all processors
        print("🔧 Auto-terminating all relationships...")
        processors = self.list_existing_processors()
        
        for proc in processors:
            try:
                proc_id = proc["id"]
                fresh_response = self.session.get(f"{self.base_url}/processors/{proc_id}")
                if fresh_response.status_code == 200:
                    processor_data = fresh_response.json()
                    revision = processor_data["revision"]["version"]
                    relationships = processor_data["component"].get("relationships", [])
                    
                    # Auto-terminate all relationships
                    auto_terminated = [rel["name"] for rel in relationships]
                    
                    update_data = {
                        "revision": {"version": revision},
                        "component": {
                            "id": proc_id,
                            "config": {"autoTerminatedRelationships": auto_terminated}
                        }
                    }
                    
                    self.session.put(f"{self.base_url}/processors/{proc_id}", 
                                   json=update_data, headers={"Content-Type": "application/json"})
            except:
                pass
        
        time.sleep(3)
        
        # Step 4: Force delete all processors
        print("🗑️ Force deleting all processors...")
        for attempt in range(3):
            processors = self.list_existing_processors()
            if not processors:
                break
                
            print(f"📦 Processor deletion attempt {attempt + 1}/3 ({len(processors)} processors)")
            
            for proc in processors:
                try:
                    proc_id = proc["id"]
                    name = proc.get("component", {}).get("name", "Unknown")
                    
                    # Get fresh revision
                    fresh_response = self.session.get(f"{self.base_url}/processors/{proc_id}")
                    if fresh_response.status_code == 200:
                        revision = fresh_response.json()["revision"]["version"]
                    else:
                        revision = proc["revision"]["version"]
                    
                    # Force delete
                    delete_response = self.session.delete(f"{self.base_url}/processors/{proc_id}", 
                                                        params={"version": revision})
                    
                    if delete_response.status_code == 200:
                        print(f"🗑️ Deleted: {name}")
                    
                except:
                    pass
            
            time.sleep(2)
        
        # Final verification
        final_processors = self.list_existing_processors()
        final_connections = self.list_existing_connections()
        
        if len(final_processors) == 0 and len(final_connections) == 0:
            print("✅ NUCLEAR CLEANUP SUCCESSFUL! All processors and connections removed.")
            return True
        else:
            print(f"⚠️ NUCLEAR CLEANUP PARTIAL: {len(final_processors)} processors and {len(final_connections)} connections remain")
            return False

    def cleanup_existing_flow(self, flow_name: str = None, force: bool = False) -> bool:
        """Delete all existing processors and connections"""
        print("🧹 Cleaning up existing flow...")
        
        # Ensure we have the correct process group ID
        if self.process_group_id == "root":
            actual_id = self.get_process_group_id()
            if actual_id and actual_id != "root":
                self.process_group_id = actual_id
        
        # Always stop all processors first to avoid 409 errors
        print("🛑 Stopping all processors first...")
        processors = self.list_existing_processors()
        stopped_count = 0
        
        for proc in processors:
            name = proc.get("component", {}).get("name", "Unknown")
            state = proc.get("component", {}).get("state", "Unknown")
            
            if state == "RUNNING":
                if self.stop_processor(proc["id"], proc["revision"]["version"]):
                    print(f"🛑 Stopped: {name}")
                    stopped_count += 1
                else:
                    print(f"⚠️ Failed to stop: {name}")
            else:
                print(f"✅ Already stopped: {name}")
                stopped_count += 1
        
        print(f"🛑 Stopped {stopped_count}/{len(processors)} processors")
        
        # Wait for processors to fully stop
        import time
        if stopped_count > 0:
            print("⏳ Waiting 5 seconds for processors to fully stop...")
            time.sleep(5)
        
        # Delete connections first (they depend on processors)
        print("🔗 Deleting connections...")
        connections = self.list_existing_connections()
        deleted_connections = 0
        failed_connections = 0
        
        for conn in connections:
            if self.delete_connection(conn["id"], conn["revision"]["version"]):
                deleted_connections += 1
            else:
                failed_connections += 1
        
        print(f"🔗 Deleted {deleted_connections} connections ({failed_connections} failed)")
        
        # Then delete processors
        print("📦 Deleting processors...")
        processors = self.list_existing_processors()  # Get fresh list
        deleted_processors = 0
        failed_processors = 0
        
        for proc in processors:
            name = proc.get("component", {}).get("name", "Unknown")
            
            # Optionally filter by flow name if provided
            if flow_name and flow_name not in proc["component"]["name"]:
                continue
                
            # Get fresh revision before deletion
            try:
                fresh_proc_response = self.session.get(f"{self.base_url}/processors/{proc['id']}")
                if fresh_proc_response.status_code == 200:
                    fresh_revision = fresh_proc_response.json()["revision"]["version"]
                else:
                    fresh_revision = proc["revision"]["version"]
            except:
                fresh_revision = proc["revision"]["version"]
            
            if self.delete_processor(proc["id"], fresh_revision):
                print(f"🗑️ Deleted: {name}")
                deleted_processors += 1
            else:
                print(f"❌ Failed to delete: {name}")
                failed_processors += 1
        
        print(f"📦 Deleted {deleted_processors} processors ({failed_processors} failed)")
        
        total_success = deleted_processors + deleted_connections
        total_failed = failed_processors + failed_connections
        
        if total_failed == 0:
            print("✅ Cleanup completed successfully!")
        else:
            print(f"⚠️ Cleanup completed with {total_failed} failures")
            
        return total_failed == 0
    
    def create_processor(self, processor_config: Dict[str, Any]) -> Optional[str]:
        """Create a processor from configuration"""
        try:
            processor_data = {
                "revision": {"version": 0},
                "component": {
                    "type": processor_config["type"],
                    "name": processor_config["name"],
                    "position": processor_config["position"],
                    "config": {
                        "properties": processor_config.get("properties", {}),
                        "autoTerminatedRelationships": processor_config.get("auto_terminated_relationships", [])
                    }
                }
            }
            
            response = self.session.post(
                f"{self.base_url}/process-groups/{self.process_group_id}/processors",
                json=processor_data,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 201:
                processor_id = response.json()["id"]
                self.created_processors[processor_config["id"]] = processor_id
                print(f"✅ Created processor: {processor_config['name']} ({processor_id})")
                return processor_id
            else:
                print(f"❌ Failed to create processor {processor_config['name']}: {response.status_code}")
                print(f"❌ Response text: {response.text}")
                print(f"❌ Request URL: {self.base_url}/process-groups/{self.process_group_id}/processors")
                return None
                
        except Exception as e:
            print(f"❌ Error creating processor {processor_config['name']}: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def create_connection(self, connection_config: Dict[str, Any]) -> Optional[str]:
        """Create a connection from configuration"""
        try:
            source_id = self.created_processors.get(connection_config["source"])
            dest_id = self.created_processors.get(connection_config["destination"])
            
            if not source_id or not dest_id:
                print(f"❌ Cannot create connection: source or destination processor not found")
                return None
            
            connection_data = {
                "revision": {"version": 0},
                "component": {
                    "source": {
                        "id": source_id,
                        "groupId": self.process_group_id,
                        "type": "PROCESSOR"
                    },
                    "destination": {
                        "id": dest_id,
                        "groupId": self.process_group_id,
                        "type": "PROCESSOR"
                    },
                    "selectedRelationships": connection_config["relationships"]
                }
            }
            
            response = self.session.post(
                f"{self.base_url}/process-groups/{self.process_group_id}/connections",
                json=connection_data,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 201:
                connection_id = response.json()["id"]
                self.created_connections[connection_config["id"]] = connection_id
                print(f"✅ Created connection: {connection_config['source']} → {connection_config['destination']} ({connection_config['relationships']})")
                return connection_id
            else:
                print(f"❌ Failed to create connection: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Error creating connection: {e}")
            return None
    
    def create_flow_from_config(self, config_path: str, cleanup_first: bool = True) -> bool:
        """Create a complete flow from YAML configuration"""
        print(f"🚀 Creating NiFi flow from configuration: {config_path}")
        
        # Wait for NiFi and authenticate
        if not self.wait_for_nifi():
            return False
        
        # Get actual process group ID (not "root")
        actual_id = self.get_process_group_id()
        if actual_id and actual_id != "root":
            self.process_group_id = actual_id
            print(f"✅ Using process group ID: {self.process_group_id}")
        else:
            print(f"❌ Failed to get valid process group ID: {actual_id}")
            return False
        
        # Load configuration
        config = self.load_flow_config(config_path)
        if not config:
            return False
        
        flow_config = config["flow"]
        
        # Cleanup existing flow if requested
        if cleanup_first:
            self.cleanup_existing_flow(flow_config["name"])
            time.sleep(2)  # Wait for cleanup to complete
        
        print(f"🏗️ Creating flow: {flow_config['name']}")
        
        # Create processors
        print("📦 Creating processors...")
        for processor_config in flow_config["processors"]:
            processor_id = self.create_processor(processor_config)
            if not processor_id:
                if flow_config.get("settings", {}).get("cleanup_on_error", True):
                    print("🧹 Cleaning up due to error...")
                    self.cleanup_existing_flow(flow_config["name"])
                return False
        
        # Create connections
        print("🔗 Creating connections...")
        for connection_config in flow_config["connections"]:
            connection_id = self.create_connection(connection_config)
            if not connection_id:
                if flow_config.get("settings", {}).get("cleanup_on_error", True):
                    print("🧹 Cleaning up due to error...")
                    self.cleanup_existing_flow(flow_config["name"])
                return False
        
        # Auto-start processors if configured
        if flow_config.get("settings", {}).get("auto_start", False):
            print("▶️ Starting processors...")
            self.start_all_processors()
        
        print(f"🎉 Flow '{flow_config['name']}' created successfully!")
        print(f"📊 Created {len(self.created_processors)} processors and {len(self.created_connections)} connections")
        
        return True
    
    def start_all_processors(self) -> bool:
        """Start all processors in the current process group"""
        # Get all processors in the process group
        processors = self.list_existing_processors()
        
        if not processors:
            print("No processors found to start")
            return True
        
        success_count = 0
        for processor in processors:
            processor_id = processor["id"]
            if self.start_processor(processor_id):
                success_count += 1
        
        print(f"✅ Started {success_count}/{len(processors)} processors")
        return success_count == len(processors)
    
    def start_processor(self, processor_id: str) -> bool:
        """Start a specific processor"""
        try:
            # Get current processor state and revision
            response = self.session.get(f"{self.base_url}/processors/{processor_id}")
            if response.status_code != 200:
                print(f"❌ Failed to get processor {processor_id}: {response.status_code}")
                return False
            
            processor_data = response.json()
            revision = processor_data["revision"]["version"]
            current_state = processor_data["component"]["state"]
            name = processor_data["component"]["name"]
            validation_errors = processor_data["component"].get("validationErrors", [])
            
            # Check if processor has validation errors
            if validation_errors:
                print(f"⚠️ Processor {name} has validation errors:")
                for error in validation_errors:
                    print(f"   - {error}")
                return False
            
            # Skip if already running
            if current_state == "RUNNING":
                print(f"✅ Processor {name} already running")
                return True
            
            print(f"🔧 Starting processor: {name} (current state: {current_state})")
            
            # Start the processor with correct NiFi API format
            start_data = {
                "revision": {"version": revision},
                "state": "RUNNING"
            }
            
            response = self.session.put(
                f"{self.base_url}/processors/{processor_id}/run-status",
                json=start_data,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                print(f"✅ Successfully started: {name}")
                return True
            else:
                print(f"❌ Failed to start {name}: {response.status_code}")
                print(f"❌ Response: {response.text}")
                return False
            
        except Exception as e:
            print(f"❌ Exception starting processor {processor_id}: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def stop_all_processors(self) -> bool:
        """Stop all processors in the current process group"""
        processors = self.list_existing_processors()
        
        if not processors:
            print("No processors found to stop")
            return True
        
        success_count = 0
        for processor in processors:
            processor_id = processor["id"]
            name = processor.get("component", {}).get("name", "Unknown")
            state = processor.get("component", {}).get("state", "Unknown")
            
            if state == "STOPPED":
                print(f"✅ {name}: Already stopped")
                success_count += 1
            elif self.stop_processor(processor_id):
                print(f"🛑 Stopped: {name}")
                success_count += 1
            else:
                print(f"❌ Failed to stop: {name}")
        
        print(f"✅ Stopped {success_count}/{len(processors)} processors")
        return success_count == len(processors)
    
    def show_status(self, verbose: bool = False) -> None:
        """Show status of all processors and connections"""
        print("📊 NiFi Flow Status")
        print("=" * 50)
        
        # Show processors
        processors = self.list_existing_processors()
        connections = self.list_existing_connections()
        
        print(f"📦 Processors: {len(processors)}")
        print(f"🔗 Connections: {len(connections)}")
        print()
        
        if processors:
            running_count = 0
            stopped_count = 0
            invalid_count = 0
            
            for processor in processors:
                name = processor.get("component", {}).get("name", "Unknown")
                state = processor.get("component", {}).get("state", "Unknown")
                validation_errors = processor.get("component", {}).get("validationErrors", [])
                
                if state == "RUNNING":
                    running_count += 1
                    status_icon = "🟢"
                elif state == "STOPPED":
                    stopped_count += 1
                    status_icon = "🟡"
                else:
                    status_icon = "🔴"
                
                if validation_errors:
                    invalid_count += 1
                    status_icon = "❌"
                
                print(f"{status_icon} {name}: {state}")
                
                if verbose and validation_errors:
                    for error in validation_errors[:3]:  # Show first 3 errors
                        print(f"   ⚠️ {error}")
                    if len(validation_errors) > 3:
                        print(f"   ... and {len(validation_errors) - 3} more errors")
            
            print()
            print(f"Summary: {running_count} running, {stopped_count} stopped, {invalid_count} with errors")
        else:
            print("No processors found")

def main():
    """Main function with command line interface"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="NiFi Flow Manager - Create and manage flows from YAML",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create flow with auto-start
  %(prog)s create -c flows/edi-validation-flow.yaml --start
  
  # Force cleanup all processors
  %(prog)s cleanup --force
  
  # Nuclear cleanup (handles stuck processors)
  %(prog)s nuclear
  
  # Create flow without cleanup
  %(prog)s create -c flows/edi-validation-flow.yaml --no-cleanup
  
  # Stop all processors
  %(prog)s stop
  
  # Check status
  %(prog)s status
        """
    )
    
    parser.add_argument("action", 
                       choices=["create", "delete", "cleanup", "nuclear", "persistent", "start", "stop", "status", "restart"], 
                       help="Action to perform")
    parser.add_argument("--config", "-c", help="Path to YAML flow configuration file")
    parser.add_argument("--flow-name", "-f", help="Flow name for deletion/cleanup")
    parser.add_argument("--no-cleanup", action="store_true", help="Don't cleanup existing flow before creating")
    parser.add_argument("--start", action="store_true", help="Start processors after creation")
    parser.add_argument("--force", action="store_true", help="Force operation (stop processors before cleanup)")
    parser.add_argument("--wait", type=int, default=5, help="Wait time in seconds between operations")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    manager = NiFiFlowManager()
    
    if args.action == "create":
        if not args.config:
            print("❌ --config is required for create action")
            sys.exit(1)
        
        if not os.path.exists(args.config):
            print(f"❌ Configuration file not found: {args.config}")
            sys.exit(1)
        
        cleanup_first = not args.no_cleanup
        success = manager.create_flow_from_config(args.config, cleanup_first)
        
        if success and args.start:
            print(f"⏳ Waiting {args.wait} seconds before starting processors...")
            import time
            time.sleep(args.wait)
            manager.start_all_processors()
        
        sys.exit(0 if success else 1)
    
    elif args.action == "delete" or args.action == "cleanup":
        if not manager.wait_for_nifi():
            sys.exit(1)
        
        manager.process_group_id = manager.get_process_group_id()
        success = manager.cleanup_existing_flow(args.flow_name, force=args.force)
        sys.exit(0 if success else 1)
    
    elif args.action == "nuclear":
        if not manager.wait_for_nifi():
            sys.exit(1)
        
        manager.process_group_id = manager.get_process_group_id()
        success = manager.nuclear_cleanup()
        sys.exit(0 if success else 1)
    
    elif args.action == "persistent":
        # Don't wait for NiFi since we'll be restarting it
        success = manager.persistent_data_cleanup()
        sys.exit(0 if success else 1)
    
    elif args.action == "start":
        if not manager.wait_for_nifi():
            sys.exit(1)
        
        manager.process_group_id = manager.get_process_group_id()
        success = manager.start_all_processors()
        sys.exit(0 if success else 1)
    
    elif args.action == "stop":
        if not manager.wait_for_nifi():
            sys.exit(1)
        
        manager.process_group_id = manager.get_process_group_id()
        success = manager.stop_all_processors()
        sys.exit(0 if success else 1)
    
    elif args.action == "status":
        if not manager.wait_for_nifi():
            sys.exit(1)
        
        manager.process_group_id = manager.get_process_group_id()
        manager.show_status(verbose=args.verbose)
        sys.exit(0)
    
    elif args.action == "restart":
        if not manager.wait_for_nifi():
            sys.exit(1)
        
        manager.process_group_id = manager.get_process_group_id()
        print("🔄 Restarting all processors...")
        manager.stop_all_processors()
        import time
        time.sleep(args.wait)
        success = manager.start_all_processors()
        sys.exit(0 if success else 1)
    
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()