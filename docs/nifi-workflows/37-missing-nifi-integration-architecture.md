# Missing NiFi Integration Architecture

**Date**: August 16, 2025  
**Author**: Assistant  
**Status**: Complete NiFi Integration Gap Analysis  

## Overview

This document details the complete NiFi integration layer that is missing from our current implementation. While we have excellent workflow template management and basic workflow CRUD operations, we have **0% implementation** of actual NiFi connectivity and deployment functionality.

## 🏗️ Required NiFi Integration Architecture

### 1. Core NiFi Integration Components

#### NiFi Registry Client
```python
# Required: src/core/nifi/registry_client.py
from typing import Optional, List, Dict, Any
import aiohttp
import json

class NiFiRegistryClient:
    """Client for NiFi Registry API integration."""
    
    def __init__(self, registry_url: str, auth_token: Optional[str] = None):
        self.registry_url = registry_url.rstrip('/')
        self.auth_token = auth_token
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        headers = {'Content-Type': 'application/json'}
        if self.auth_token:
            headers['Authorization'] = f'Bearer {self.auth_token}'
        
        self.session = aiohttp.ClientSession(
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=30)
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    # Bucket Management
    async def list_buckets(self) -> List[Dict[str, Any]]:
        """List all available buckets."""
        async with self.session.get(f"{self.registry_url}/nifi-registry-api/buckets") as response:
            response.raise_for_status()
            return await response.json()
    
    async def create_bucket(self, name: str, description: str = "") -> Dict[str, Any]:
        """Create a new bucket for storing flows."""
        bucket_data = {
            "name": name,
            "description": description,
            "allowBundleRedeploy": False,
            "allowPublicRead": False
        }
        
        async with self.session.post(
            f"{self.registry_url}/nifi-registry-api/buckets",
            json=bucket_data
        ) as response:
            response.raise_for_status()
            return await response.json()
    
    async def get_bucket(self, bucket_id: str) -> Dict[str, Any]:
        """Get bucket details by ID."""
        async with self.session.get(
            f"{self.registry_url}/nifi-registry-api/buckets/{bucket_id}"
        ) as response:
            response.raise_for_status()
            return await response.json()
    
    # Flow Management
    async def create_flow(
        self,
        bucket_id: str,
        flow_name: str,
        flow_description: str = "",
        flow_type: str = "Flow"
    ) -> Dict[str, Any]:
        """Create a new flow in the registry."""
        flow_data = {
            "name": flow_name,
            "description": flow_description,
            "type": flow_type,
            "bucketIdentifier": bucket_id
        }
        
        async with self.session.post(
            f"{self.registry_url}/nifi-registry-api/buckets/{bucket_id}/flows",
            json=flow_data
        ) as response:
            response.raise_for_status()
            return await response.json()
    
    async def create_flow_version(
        self,
        bucket_id: str,
        flow_id: str,
        flow_snapshot: Dict[str, Any],
        version_comments: str = ""
    ) -> Dict[str, Any]:
        """Create a new version of a flow."""
        version_data = {
            "bucketIdentifier": bucket_id,
            "flowIdentifier": flow_id,
            "comments": version_comments,
            "flowSnapshot": flow_snapshot
        }
        
        async with self.session.post(
            f"{self.registry_url}/nifi-registry-api/buckets/{bucket_id}/flows/{flow_id}/versions",
            json=version_data
        ) as response:
            response.raise_for_status()
            return await response.json()
    
    async def get_flow_versions(
        self,
        bucket_id: str,
        flow_id: str
    ) -> List[Dict[str, Any]]:
        """Get all versions of a flow."""
        async with self.session.get(
            f"{self.registry_url}/nifi-registry-api/buckets/{bucket_id}/flows/{flow_id}/versions"
        ) as response:
            response.raise_for_status()
            return await response.json()
    
    async def get_flow_version(
        self,
        bucket_id: str,
        flow_id: str,
        version: int
    ) -> Dict[str, Any]:
        """Get specific version of a flow."""
        async with self.session.get(
            f"{self.registry_url}/nifi-registry-api/buckets/{bucket_id}/flows/{flow_id}/versions/{version}"
        ) as response:
            response.raise_for_status()
            return await response.json()
    
    async def delete_flow(self, bucket_id: str, flow_id: str) -> None:
        """Delete a flow from the registry."""
        async with self.session.delete(
            f"{self.registry_url}/nifi-registry-api/buckets/{bucket_id}/flows/{flow_id}"
        ) as response:
            response.raise_for_status()
    
    # Health Check
    async def health_check(self) -> Dict[str, Any]:
        """Check NiFi Registry health."""
        async with self.session.get(
            f"{self.registry_url}/nifi-registry-api/about"
        ) as response:
            response.raise_for_status()
            return await response.json()
```

#### NiFi API Client
```python
# Required: src/core/nifi/api_client.py
from typing import Optional, List, Dict, Any, Union
import aiohttp
import json
from enum import Enum

class ProcessGroupState(str, Enum):
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    DISABLED = "DISABLED"

class NiFiAPIClient:
    """Client for NiFi REST API integration."""
    
    def __init__(self, nifi_url: str, auth_token: Optional[str] = None):
        self.nifi_url = nifi_url.rstrip('/')
        self.auth_token = auth_token
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        headers = {'Content-Type': 'application/json'}
        if self.auth_token:
            headers['Authorization'] = f'Bearer {self.auth_token}'
        
        self.session = aiohttp.ClientSession(
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=60)
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    # Process Group Management
    async def create_process_group(
        self,
        parent_group_id: str,
        name: str,
        position_x: float = 0.0,
        position_y: float = 0.0
    ) -> Dict[str, Any]:
        """Create a new process group."""
        process_group_data = {
            "revision": {"version": 0},
            "component": {
                "name": name,
                "position": {
                    "x": position_x,
                    "y": position_y
                }
            }
        }
        
        async with self.session.post(
            f"{self.nifi_url}/nifi-api/process-groups/{parent_group_id}/process-groups",
            json=process_group_data
        ) as response:
            response.raise_for_status()
            return await response.json()
    
    async def get_process_group(self, process_group_id: str) -> Dict[str, Any]:
        """Get process group details."""
        async with self.session.get(
            f"{self.nifi_url}/nifi-api/process-groups/{process_group_id}"
        ) as response:
            response.raise_for_status()
            return await response.json()
    
    async def delete_process_group(self, process_group_id: str, version: int) -> None:
        """Delete a process group."""
        async with self.session.delete(
            f"{self.nifi_url}/nifi-api/process-groups/{process_group_id}",
            params={"version": version}
        ) as response:
            response.raise_for_status()
    
    async def start_process_group(self, process_group_id: str) -> Dict[str, Any]:
        """Start all processors in a process group."""
        return await self._change_process_group_state(process_group_id, ProcessGroupState.RUNNING)
    
    async def stop_process_group(self, process_group_id: str) -> Dict[str, Any]:
        """Stop all processors in a process group."""
        return await self._change_process_group_state(process_group_id, ProcessGroupState.STOPPED)
    
    async def _change_process_group_state(
        self,
        process_group_id: str,
        state: ProcessGroupState
    ) -> Dict[str, Any]:
        """Change the state of a process group."""
        state_data = {
            "id": process_group_id,
            "state": state.value
        }
        
        async with self.session.put(
            f"{self.nifi_url}/nifi-api/flow/process-groups/{process_group_id}",
            json=state_data
        ) as response:
            response.raise_for_status()
            return await response.json()
    
    # Flow Deployment from Registry
    async def deploy_flow_from_registry(
        self,
        parent_group_id: str,
        registry_client_id: str,
        bucket_id: str,
        flow_id: str,
        flow_version: int,
        flow_name: str,
        position_x: float = 0.0,
        position_y: float = 0.0
    ) -> Dict[str, Any]:
        """Deploy a flow from NiFi Registry."""
        deployment_data = {
            "revision": {"version": 0},
            "component": {
                "name": flow_name,
                "position": {
                    "x": position_x,
                    "y": position_y
                },
                "versionControlInformation": {
                    "registryId": registry_client_id,
                    "bucketId": bucket_id,
                    "flowId": flow_id,
                    "version": flow_version
                }
            }
        }
        
        async with self.session.post(
            f"{self.nifi_url}/nifi-api/process-groups/{parent_group_id}/process-groups",
            json=deployment_data
        ) as response:
            response.raise_for_status()
            return await response.json()
    
    async def update_flow_version(
        self,
        process_group_id: str,
        version: int,
        new_flow_version: int
    ) -> Dict[str, Any]:
        """Update process group to a new flow version."""
        update_data = {
            "processGroupRevision": {"version": version},
            "versionControlInformation": {
                "version": new_flow_version
            }
        }
        
        async with self.session.put(
            f"{self.nifi_url}/nifi-api/versions/update-requests/process-groups/{process_group_id}",
            json=update_data
        ) as response:
            response.raise_for_status()
            return await response.json()
    
    # Parameter Context Management
    async def create_parameter_context(
        self,
        name: str,
        description: str = "",
        parameters: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Create a parameter context."""
        parameter_entities = []
        if parameters:
            for param_name, param_value in parameters.items():
                parameter_entities.append({
                    "parameter": {
                        "name": param_name,
                        "value": param_value,
                        "sensitive": False
                    }
                })
        
        context_data = {
            "revision": {"version": 0},
            "component": {
                "name": name,
                "description": description,
                "parameters": parameter_entities
            }
        }
        
        async with self.session.post(
            f"{self.nifi_url}/nifi-api/parameter-contexts",
            json=context_data
        ) as response:
            response.raise_for_status()
            return await response.json()
    
    async def update_parameter_context(
        self,
        context_id: str,
        version: int,
        parameters: Dict[str, str]
    ) -> Dict[str, Any]:
        """Update parameters in a parameter context."""
        parameter_entities = []
        for param_name, param_value in parameters.items():
            parameter_entities.append({
                "parameter": {
                    "name": param_name,
                    "value": param_value,
                    "sensitive": False
                }
            })
        
        update_data = {
            "revision": {"version": version},
            "component": {
                "id": context_id,
                "parameters": parameter_entities
            }
        }
        
        async with self.session.put(
            f"{self.nifi_url}/nifi-api/parameter-contexts/{context_id}",
            json=update_data
        ) as response:
            response.raise_for_status()
            return await response.json()
    
    async def get_parameter_context(self, context_id: str) -> Dict[str, Any]:
        """Get parameter context details."""
        async with self.session.get(
            f"{self.nifi_url}/nifi-api/parameter-contexts/{context_id}"
        ) as response:
            response.raise_for_status()
            return await response.json()
    
    async def assign_parameter_context(
        self,
        process_group_id: str,
        context_id: str,
        version: int
    ) -> Dict[str, Any]:
        """Assign parameter context to a process group."""
        assignment_data = {
            "revision": {"version": version},
            "component": {
                "id": process_group_id,
                "parameterContext": {
                    "id": context_id
                }
            }
        }
        
        async with self.session.put(
            f"{self.nifi_url}/nifi-api/process-groups/{process_group_id}",
            json=assignment_data
        ) as response:
            response.raise_for_status()
            return await response.json()
    
    # Processor Control
    async def get_processors(self, process_group_id: str) -> List[Dict[str, Any]]:
        """Get all processors in a process group."""
        async with self.session.get(
            f"{self.nifi_url}/nifi-api/process-groups/{process_group_id}/processors"
        ) as response:
            response.raise_for_status()
            result = await response.json()
            return result.get('processors', [])
    
    async def start_processor(self, processor_id: str, version: int) -> Dict[str, Any]:
        """Start a specific processor."""
        return await self._change_processor_state(processor_id, version, "RUNNING")
    
    async def stop_processor(self, processor_id: str, version: int) -> Dict[str, Any]:
        """Stop a specific processor."""
        return await self._change_processor_state(processor_id, version, "STOPPED")
    
    async def _change_processor_state(
        self,
        processor_id: str,
        version: int,
        state: str
    ) -> Dict[str, Any]:
        """Change processor state."""
        state_data = {
            "revision": {"version": version},
            "component": {
                "id": processor_id,
                "state": state
            }
        }
        
        async with self.session.put(
            f"{self.nifi_url}/nifi-api/processors/{processor_id}",
            json=state_data
        ) as response:
            response.raise_for_status()
            return await response.json()
    
    # System Information
    async def get_cluster_summary(self) -> Dict[str, Any]:
        """Get NiFi cluster summary."""
        async with self.session.get(
            f"{self.nifi_url}/nifi-api/flow/cluster/summary"
        ) as response:
            response.raise_for_status()
            return await response.json()
    
    async def get_system_diagnostics(self) -> Dict[str, Any]:
        """Get system diagnostics."""
        async with self.session.get(
            f"{self.nifi_url}/nifi-api/system-diagnostics"
        ) as response:
            response.raise_for_status()
            return await response.json()
    
    async def health_check(self) -> Dict[str, Any]:
        """Check NiFi API health."""
        async with self.session.get(
            f"{self.nifi_url}/nifi-api/flow/about"
        ) as response:
            response.raise_for_status()
            return await response.json()
```

### 2. High-Level Service Layer

#### Workflow Deployment Service
```python
# Required: src/services/workflow_deployment_service.py
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.core.nifi.registry_client import NiFiRegistryClient
from src.core.nifi.api_client import NiFiAPIClient
from src.models.workflow_template import WorkflowTemplate, Workflow
from src.core.config import get_settings

class WorkflowDeploymentService:
    """Service for deploying workflows to NiFi."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.settings = get_settings()
    
    async def deploy_workflow(
        self,
        workflow_id: str,
        auth_context: AuthContext
    ) -> Dict[str, Any]:
        """Deploy a workflow to NiFi."""
        
        # 1. Load workflow and template
        workflow = await self._get_workflow(workflow_id)
        template = await self._get_template(workflow.template_id)
        
        # 2. Validate workflow can be deployed
        await self._validate_deployment_readiness(workflow, template)
        
        # 3. Deploy to NiFi Registry if needed
        registry_info = await self._ensure_template_in_registry(template)
        
        # 4. Create parameter context for workflow
        parameter_context = await self._create_parameter_context(workflow, template)
        
        # 5. Deploy process group from registry
        process_group = await self._deploy_process_group(
            workflow, template, registry_info, parameter_context
        )
        
        # 6. Configure and start workflow
        await self._configure_and_start_workflow(workflow, process_group)
        
        # 7. Update workflow record
        await self._update_workflow_deployment_info(
            workflow, process_group, parameter_context, registry_info
        )
        
        return {
            "workflow_id": workflow_id,
            "status": "DEPLOYED",
            "nifi_process_group_id": process_group["id"],
            "nifi_parameter_context_id": parameter_context["id"],
            "deployment_method": "registry",
            "flow_version": registry_info["version"]
        }
    
    async def undeploy_workflow(
        self,
        workflow_id: str,
        auth_context: AuthContext
    ) -> Dict[str, Any]:
        """Remove workflow from NiFi."""
        
        workflow = await self._get_workflow(workflow_id)
        
        if not workflow.nifi_process_group_id:
            raise ValueError("Workflow is not deployed")
        
        async with NiFiAPIClient(
            self.settings.nifi_api_url,
            self.settings.nifi_service_token
        ) as nifi_client:
            
            # 1. Stop process group
            await nifi_client.stop_process_group(workflow.nifi_process_group_id)
            
            # 2. Get current version for deletion
            pg_info = await nifi_client.get_process_group(workflow.nifi_process_group_id)
            
            # 3. Delete process group
            await nifi_client.delete_process_group(
                workflow.nifi_process_group_id,
                pg_info["revision"]["version"]
            )
            
            # 4. Clean up parameter context if it's workflow-specific
            if workflow.nifi_parameter_context_id:
                try:
                    context_info = await nifi_client.get_parameter_context(
                        workflow.nifi_parameter_context_id
                    )
                    # Only delete if it's not shared
                    if context_info["component"]["name"].startswith(f"workflow-{workflow_id}"):
                        await nifi_client.delete_parameter_context(
                            workflow.nifi_parameter_context_id,
                            context_info["revision"]["version"]
                        )
                except Exception:
                    # Context might already be deleted or shared
                    pass
        
        # 5. Update workflow record
        workflow.nifi_process_group_id = None
        workflow.nifi_parameter_context_id = None
        workflow.deployment_method = None
        workflow.flow_version = None
        workflow.status = "STOPPED"
        
        await self.session.commit()
        
        return {
            "workflow_id": workflow_id,
            "status": "UNDEPLOYED",
            "message": "Workflow successfully removed from NiFi"
        }
    
    async def restart_workflow(
        self,
        workflow_id: str,
        auth_context: AuthContext
    ) -> Dict[str, Any]:
        """Restart a deployed workflow."""
        
        workflow = await self._get_workflow(workflow_id)
        
        if not workflow.nifi_process_group_id:
            raise ValueError("Workflow is not deployed")
        
        async with NiFiAPIClient(
            self.settings.nifi_api_url,
            self.settings.nifi_service_token
        ) as nifi_client:
            
            # 1. Stop process group
            await nifi_client.stop_process_group(workflow.nifi_process_group_id)
            
            # 2. Wait for processors to stop (would need proper polling)
            await asyncio.sleep(2)
            
            # 3. Start process group
            await nifi_client.start_process_group(workflow.nifi_process_group_id)
        
        workflow.status = "ACTIVE"
        await self.session.commit()
        
        return {
            "workflow_id": workflow_id,
            "status": "RESTARTED",
            "nifi_status": "RUNNING"
        }
    
    async def get_deployment_status(
        self,
        workflow_id: str,
        auth_context: AuthContext
    ) -> Dict[str, Any]:
        """Get detailed deployment status."""
        
        workflow = await self._get_workflow(workflow_id)
        
        if not workflow.nifi_process_group_id:
            return {
                "workflow_id": workflow_id,
                "status": "NOT_DEPLOYED",
                "deployment_status": "NONE"
            }
        
        async with NiFiAPIClient(
            self.settings.nifi_api_url,
            self.settings.nifi_service_token
        ) as nifi_client:
            
            try:
                # Get process group status
                pg_info = await nifi_client.get_process_group(workflow.nifi_process_group_id)
                
                # Get processors status
                processors = await nifi_client.get_processors(workflow.nifi_process_group_id)
                
                # Aggregate status
                running_processors = sum(1 for p in processors if p["status"]["runStatus"] == "RUNNING")
                total_processors = len(processors)
                
                return {
                    "workflow_id": workflow_id,
                    "status": workflow.status,
                    "deployment_status": "DEPLOYED",
                    "nifi_status": pg_info["status"]["name"],
                    "process_group_id": workflow.nifi_process_group_id,
                    "parameter_context_id": workflow.nifi_parameter_context_id,
                    "flow_version": workflow.flow_version,
                    "processors": {
                        "total": total_processors,
                        "running": running_processors,
                        "stopped": total_processors - running_processors
                    },
                    "last_updated": pg_info.get("lastUpdated")
                }
                
            except Exception as e:
                return {
                    "workflow_id": workflow_id,
                    "status": "ERROR",
                    "deployment_status": "ERROR",
                    "error": str(e)
                }
    
    # Private helper methods
    async def _get_workflow(self, workflow_id: str) -> Workflow:
        """Load workflow from database."""
        query = select(Workflow).where(Workflow.workflow_id == workflow_id)
        result = await self.session.execute(query)
        workflow = result.scalar_one_or_none()
        
        if not workflow:
            raise ValueError(f"Workflow {workflow_id} not found")
        
        return workflow
    
    async def _get_template(self, template_id: str) -> WorkflowTemplate:
        """Load template from database."""
        query = select(WorkflowTemplate).where(WorkflowTemplate.template_id == template_id)
        result = await self.session.execute(query)
        template = result.scalar_one_or_none()
        
        if not template:
            raise ValueError(f"Template {template_id} not found")
        
        return template
    
    async def _validate_deployment_readiness(
        self,
        workflow: Workflow,
        template: WorkflowTemplate
    ) -> None:
        """Validate workflow can be deployed."""
        
        if template.status != "ACTIVE":
            raise ValueError(f"Template {template.template_id} is not active")
        
        if not template.flow_definition:
            raise ValueError(f"Template {template.template_id} has no flow definition")
        
        if workflow.status in ["DELETED", "ERROR"]:
            raise ValueError(f"Workflow {workflow.workflow_id} cannot be deployed in {workflow.status} state")
    
    async def _ensure_template_in_registry(
        self,
        template: WorkflowTemplate
    ) -> Dict[str, Any]:
        """Ensure template is deployed to NiFi Registry."""
        
        # If template already has registry info, verify it exists
        if template.nifi_registry_flow_id and template.nifi_registry_bucket_id:
            async with NiFiRegistryClient(
                self.settings.nifi_registry_url,
                self.settings.nifi_service_token
            ) as registry_client:
                
                try:
                    # Check if flow exists
                    versions = await registry_client.get_flow_versions(
                        template.nifi_registry_bucket_id,
                        template.nifi_registry_flow_id
                    )
                    
                    # Return latest version info
                    return {
                        "bucket_id": template.nifi_registry_bucket_id,
                        "flow_id": template.nifi_registry_flow_id,
                        "version": max(v["version"] for v in versions)
                    }
                    
                except Exception:
                    # Flow doesn't exist, will create below
                    pass
        
        # Create new flow in registry
        async with NiFiRegistryClient(
            self.settings.nifi_registry_url,
            self.settings.nifi_service_token
        ) as registry_client:
            
            # Get or create bucket
            bucket_id = await self._get_or_create_bucket(registry_client, template.scope)
            
            # Create flow
            flow = await registry_client.create_flow(
                bucket_id,
                template.name,
                template.description or ""
            )
            
            # Create initial version
            flow_snapshot = self._build_flow_snapshot(template)
            version = await registry_client.create_flow_version(
                bucket_id,
                flow["identifier"],
                flow_snapshot,
                f"Initial version from template {template.template_id}"
            )
            
            # Update template with registry info
            template.nifi_registry_bucket_id = bucket_id
            template.nifi_registry_flow_id = flow["identifier"]
            await self.session.commit()
            
            return {
                "bucket_id": bucket_id,
                "flow_id": flow["identifier"],
                "version": version["snapshotMetadata"]["version"]
            }
    
    async def _get_or_create_bucket(
        self,
        registry_client: NiFiRegistryClient,
        scope: str
    ) -> str:
        """Get or create bucket for template scope."""
        
        bucket_name = f"edi-lens-{scope.lower()}"
        
        # Try to find existing bucket
        buckets = await registry_client.list_buckets()
        for bucket in buckets:
            if bucket["name"] == bucket_name:
                return bucket["identifier"]
        
        # Create new bucket
        bucket = await registry_client.create_bucket(
            bucket_name,
            f"EDI Lens {scope} Templates"
        )
        
        return bucket["identifier"]
    
    def _build_flow_snapshot(self, template: WorkflowTemplate) -> Dict[str, Any]:
        """Build NiFi flow snapshot from template definition."""
        
        # This would convert our template flow_definition format
        # to NiFi's expected flow snapshot format
        # The exact structure depends on how we design our template format
        
        flow_definition = template.flow_definition
        
        # Basic snapshot structure
        snapshot = {
            "flowContents": {
                "identifier": str(uuid4()),
                "name": template.name,
                "comments": template.description or "",
                "position": {"x": 0, "y": 0},
                "processGroups": [],
                "processors": flow_definition.get("processors", []),
                "connections": flow_definition.get("connections", []),
                "labels": flow_definition.get("labels", []),
                "funnels": flow_definition.get("funnels", []),
                "controllerServices": flow_definition.get("controllerServices", []),
                "parameterContexts": flow_definition.get("parameterContexts", [])
            },
            "externalControllerServices": {},
            "parameterProviders": {},
            "flowEncodingVersion": "1.0"
        }
        
        return snapshot
    
    async def _create_parameter_context(
        self,
        workflow: Workflow,
        template: WorkflowTemplate
    ) -> Dict[str, Any]:
        """Create parameter context for workflow configuration."""
        
        async with NiFiAPIClient(
            self.settings.nifi_api_url,
            self.settings.nifi_service_token
        ) as nifi_client:
            
            # Build parameters from workflow configuration
            parameters = {}
            
            # Add tenant-specific parameters
            parameters["TENANT_ID"] = workflow.tenant_id
            parameters["WORKFLOW_ID"] = str(workflow.workflow_id)
            parameters["WORKFLOW_NAME"] = workflow.name
            
            # Add configuration parameters
            config = workflow.configuration
            for key, value in config.items():
                if isinstance(value, (str, int, float, bool)):
                    parameters[key.upper()] = str(value)
                elif isinstance(value, dict):
                    # Flatten nested configuration
                    for nested_key, nested_value in value.items():
                        if isinstance(nested_value, (str, int, float, bool)):
                            parameters[f"{key.upper()}_{nested_key.upper()}"] = str(nested_value)
            
            # Create parameter context
            context_name = f"workflow-{workflow.workflow_id}-params"
            context = await nifi_client.create_parameter_context(
                context_name,
                f"Parameters for workflow {workflow.name}",
                parameters
            )
            
            return context
    
    async def _deploy_process_group(
        self,
        workflow: Workflow,
        template: WorkflowTemplate,
        registry_info: Dict[str, Any],
        parameter_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Deploy process group from registry."""
        
        async with NiFiAPIClient(
            self.settings.nifi_api_url,
            self.settings.nifi_service_token
        ) as nifi_client:
            
            # Deploy from registry
            process_group = await nifi_client.deploy_flow_from_registry(
                parent_group_id=self.settings.nifi_root_process_group_id,
                registry_client_id=self.settings.nifi_registry_client_id,
                bucket_id=registry_info["bucket_id"],
                flow_id=registry_info["flow_id"],
                flow_version=registry_info["version"],
                flow_name=f"{workflow.name} ({workflow.workflow_id})",
                position_x=100.0,
                position_y=100.0
            )
            
            # Assign parameter context
            await nifi_client.assign_parameter_context(
                process_group["id"],
                parameter_context["id"],
                process_group["revision"]["version"]
            )
            
            return process_group
    
    async def _configure_and_start_workflow(
        self,
        workflow: Workflow,
        process_group: Dict[str, Any]
    ) -> None:
        """Configure and start the deployed workflow."""
        
        async with NiFiAPIClient(
            self.settings.nifi_api_url,
            self.settings.nifi_service_token
        ) as nifi_client:
            
            # Start the process group
            await nifi_client.start_process_group(process_group["id"])
    
    async def _update_workflow_deployment_info(
        self,
        workflow: Workflow,
        process_group: Dict[str, Any],
        parameter_context: Dict[str, Any],
        registry_info: Dict[str, Any]
    ) -> None:
        """Update workflow with deployment information."""
        
        workflow.nifi_process_group_id = process_group["id"]
        workflow.nifi_parameter_context_id = parameter_context["id"]
        workflow.deployment_method = "registry"
        workflow.flow_version = registry_info["version"]
        workflow.status = "ACTIVE"
        
        await self.session.commit()
```

### 3. Configuration Requirements

#### NiFi Integration Settings
```python
# Required: Add to src/core/config.py
from pydantic import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # ... existing settings ...
    
    # NiFi Integration Settings
    nifi_api_url: str = "http://nifi:8080/nifi-api"
    nifi_registry_url: str = "http://nifi-registry:18080"
    nifi_service_token: Optional[str] = None
    nifi_registry_client_id: str = "edi-lens-registry-client"
    nifi_root_process_group_id: str = "root"
    
    # NiFi Deployment Settings
    nifi_default_bucket_name: str = "edi-lens-templates"
    nifi_deployment_timeout_seconds: int = 300
    nifi_health_check_interval_seconds: int = 30
    
    # NiFi Authentication
    nifi_username: Optional[str] = None
    nifi_password: Optional[str] = None
    nifi_keystore_path: Optional[str] = None
    nifi_keystore_password: Optional[str] = None
    nifi_truststore_path: Optional[str] = None
    nifi_truststore_password: Optional[str] = None
    
    class Config:
        env_file = ".env"
```

#### Docker Compose Integration
```yaml
# Required: Add to docker/docker-compose.yml
services:
  # ... existing services ...
  
  nifi-registry:
    image: apache/nifi-registry:1.18.0
    container_name: nifi-registry
    ports:
      - "18080:18080"
    environment:
      NIFI_REGISTRY_WEB_HTTP_HOST: '0.0.0.0'
      NIFI_REGISTRY_WEB_HTTP_PORT: '18080'
      NIFI_REGISTRY_FLOW_PROVIDER: file
      NIFI_REGISTRY_FLOW_PROVIDER_FILE_DIR: /opt/nifi-registry/flow-storage
    volumes:
      - nifi_registry_data:/opt/nifi-registry/flow-storage
      - nifi_registry_logs:/opt/nifi-registry/logs
    networks:
      - edi-lens-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:18080/nifi-registry-api/about"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 60s

  nifi:
    image: apache/nifi:1.18.0
    container_name: nifi
    ports:
      - "8080:8080"
      - "8443:8443"
    environment:
      NIFI_WEB_HTTP_HOST: '0.0.0.0'
      NIFI_WEB_HTTP_PORT: '8080'
      NIFI_CLUSTER_IS_NODE: 'false'
      NIFI_ZK_CONNECT_STRING: 'zookeeper:2181'
      NIFI_ELECTION_MAX_WAIT: '1 min'
      NIFI_SENSITIVE_PROPS_KEY: 'changeme'
      # Registry client configuration
      NIFI_REGISTRY_CLIENTS: |
        <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
        <registryClients>
          <registryClient>
            <id>edi-lens-registry-client</id>
            <name>EDI Lens Registry</name>
            <url>http://nifi-registry:18080</url>
            <description>EDI Lens NiFi Registry</description>
          </registryClient>
        </registryClients>
    volumes:
      - nifi_data:/opt/nifi/nifi-current/work
      - nifi_logs:/opt/nifi/nifi-current/logs
      - nifi_conf:/opt/nifi/nifi-current/conf
    networks:
      - edi-lens-network
    depends_on:
      nifi-registry:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/nifi-api/flow/about"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 120s

volumes:
  # ... existing volumes ...
  nifi_registry_data:
  nifi_registry_logs:
  nifi_data:
  nifi_logs:
  nifi_conf:
```

### 4. API Integration Layer

#### NiFi Health Monitoring Service
```python
# Required: src/services/nifi_health_service.py
from typing import Dict, Any, List
import asyncio
from datetime import datetime, timedelta

from src.core.nifi.api_client import NiFiAPIClient
from src.core.nifi.registry_client import NiFiRegistryClient
from src.core.config import get_settings

class NiFiHealthService:
    """Service for monitoring NiFi cluster health."""
    
    def __init__(self):
        self.settings = get_settings()
    
    async def get_comprehensive_health(self) -> Dict[str, Any]:
        """Get comprehensive health status of NiFi cluster."""
        
        health_status = {
            "overall_status": "unknown",
            "timestamp": datetime.utcnow().isoformat(),
            "services": {},
            "workflows": {},
            "system_metrics": {}
        }
        
        try:
            # Check NiFi API health
            nifi_health = await self._check_nifi_api_health()
            health_status["services"]["nifi"] = nifi_health
            
            # Check NiFi Registry health
            registry_health = await self._check_registry_health()
            health_status["services"]["nifi_registry"] = registry_health
            
            # Get system metrics
            system_metrics = await self._get_system_metrics()
            health_status["system_metrics"] = system_metrics
            
            # Get workflow status summary
            workflow_summary = await self._get_workflow_summary()
            health_status["workflows"] = workflow_summary
            
            # Determine overall status
            service_statuses = [
                nifi_health["status"],
                registry_health["status"]
            ]
            
            if all(status == "healthy" for status in service_statuses):
                health_status["overall_status"] = "healthy"
            elif any(status == "unhealthy" for status in service_statuses):
                health_status["overall_status"] = "unhealthy"
            else:
                health_status["overall_status"] = "degraded"
                
        except Exception as e:
            health_status["overall_status"] = "error"
            health_status["error"] = str(e)
        
        return health_status
    
    async def _check_nifi_api_health(self) -> Dict[str, Any]:
        """Check NiFi API health."""
        try:
            async with NiFiAPIClient(
                self.settings.nifi_api_url,
                self.settings.nifi_service_token
            ) as nifi_client:
                
                start_time = datetime.utcnow()
                about_info = await nifi_client.health_check()
                response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
                
                # Get cluster summary
                cluster_summary = await nifi_client.get_cluster_summary()
                
                # Get system diagnostics
                system_diag = await nifi_client.get_system_diagnostics()
                
                return {
                    "status": "healthy",
                    "response_time_ms": int(response_time),
                    "api_version": about_info.get("version", "unknown"),
                    "cluster_nodes": cluster_summary.get("connectedNodeCount", 1),
                    "cluster_status": cluster_summary.get("clustered", False),
                    "active_threads": system_diag.get("aggregateSnapshot", {}).get("activeThreadCount", 0),
                    "heap_utilization": system_diag.get("aggregateSnapshot", {}).get("heapUtilization", "0%")
                }
                
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "response_time_ms": None
            }
    
    async def _check_registry_health(self) -> Dict[str, Any]:
        """Check NiFi Registry health."""
        try:
            async with NiFiRegistryClient(
                self.settings.nifi_registry_url,
                self.settings.nifi_service_token
            ) as registry_client:
                
                start_time = datetime.utcnow()
                about_info = await registry_client.health_check()
                response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
                
                # Get buckets count
                buckets = await registry_client.list_buckets()
                
                return {
                    "status": "healthy",
                    "response_time_ms": int(response_time),
                    "version": about_info.get("version", "unknown"),
                    "buckets_count": len(buckets)
                }
                
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "response_time_ms": None
            }
    
    async def _get_system_metrics(self) -> Dict[str, Any]:
        """Get system performance metrics."""
        try:
            async with NiFiAPIClient(
                self.settings.nifi_api_url,
                self.settings.nifi_service_token
            ) as nifi_client:
                
                system_diag = await nifi_client.get_system_diagnostics()
                snapshot = system_diag.get("aggregateSnapshot", {})
                
                return {
                    "cpu_usage_percent": self._parse_percentage(snapshot.get("processorLoadAverage", "0%")),
                    "memory_usage_percent": self._parse_percentage(snapshot.get("heapUtilization", "0%")),
                    "heap_used_bytes": snapshot.get("heapUsed", 0),
                    "heap_max_bytes": snapshot.get("heapMax", 0),
                    "active_threads": snapshot.get("activeThreadCount", 0),
                    "flowfile_repository_usage": snapshot.get("flowFileRepositoryStorageUsage", {}),
                    "content_repository_usage": snapshot.get("contentRepositoryStorageUsage", [])
                }
                
        except Exception:
            return {
                "cpu_usage_percent": 0,
                "memory_usage_percent": 0,
                "error": "Unable to fetch system metrics"
            }
    
    async def _get_workflow_summary(self) -> Dict[str, Any]:
        """Get summary of workflow statuses."""
        # This would query the database for workflow counts
        # Implementation depends on having WorkflowStatusService
        return {
            "total_count": 0,
            "active_count": 0,
            "paused_count": 0,
            "error_count": 0,
            "not_deployed_count": 0
        }
    
    def _parse_percentage(self, percentage_str: str) -> float:
        """Parse percentage string to float."""
        try:
            return float(percentage_str.rstrip('%'))
        except (ValueError, AttributeError):
            return 0.0
```

## 🔧 Implementation Priority

### Phase 1: Core NiFi Connectivity (Week 1-2)
1. **NiFi API Client**: Basic process group and parameter management
2. **NiFi Registry Client**: Flow deployment and versioning
3. **Basic Health Checks**: Connectivity validation
4. **Configuration**: Environment variables and settings

### Phase 2: Workflow Deployment (Week 3-4)
1. **Deployment Service**: Core workflow deployment logic
2. **Template to Registry**: Convert templates to NiFi flows
3. **Parameter Injection**: Dynamic configuration handling
4. **Basic Lifecycle**: Deploy, start, stop, undeploy

### Phase 3: Advanced Features (Week 5-6)
1. **Health Monitoring**: Comprehensive system monitoring
2. **Metrics Collection**: Performance data gathering
3. **Error Handling**: Robust failure recovery
4. **Flow Versioning**: Template version management

### Phase 4: Integration & Testing (Week 7-8)
1. **API Integration**: Connect services to endpoints
2. **Comprehensive Testing**: Integration and E2E tests
3. **Documentation**: API and deployment guides
4. **Performance Optimization**: Scalability improvements

## 📋 Current Status: 0% Implementation

**Missing Components:**
- ❌ **NiFi API Client**: Complete implementation needed
- ❌ **NiFi Registry Client**: Complete implementation needed  
- ❌ **Deployment Services**: Complete implementation needed
- ❌ **Health Monitoring**: Complete implementation needed
- ❌ **Configuration**: NiFi settings and Docker setup needed
- ❌ **Testing**: No NiFi integration tests exist

**Critical Dependency**: This entire integration layer must be implemented before workflow execution endpoints can function. The workflow execution APIs documented in `36-missing-api-specifications.md` depend on this NiFi integration layer being in place.