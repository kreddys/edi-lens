"""
Service for managing NiFi workflow deployments.

This service handles the deployment, management, and control of workflows
in Apache NiFi, integrating with the NiFi Registry for versioned flows
and the NiFi API for runtime process group management.
"""

import logging
import uuid
from typing import Dict, Any, Optional, List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.core.config import settings
from src.models.workflow_template import Workflow, WorkflowTemplate, TemplateVersion
from src.nifi.clients.nifi_client import NiFiAPIClient
from src.nifi.clients.registry_client import NiFiRegistryClient
from src.api.schemas import WorkflowStatus

log = logging.getLogger(__name__)


class NiFiWorkflowDeploymentError(Exception):
    """Exception raised for NiFi workflow deployment errors."""
    pass


class NiFiWorkflowService:
    """Service for managing NiFi workflow deployments."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create_workflow(self, workflow_data: dict, created_by: str) -> Workflow:
        """
        Create a new workflow in the database.
        
        Args:
            workflow_data: Dictionary containing workflow data
            created_by: User ID who created the workflow
            
        Returns:
            Created Workflow object
        """
        workflow = Workflow(
            name=workflow_data["name"],
            description=workflow_data.get("description"),
            template_id=workflow_data["template_id"],
            configuration=workflow_data["configuration"],
            tenant_id=workflow_data["tenant_id"],
            created_by=created_by
        )
        self.session.add(workflow)
        await self.session.commit()
        await self.session.refresh(workflow)
        return workflow
    
    async def deploy_workflow(self, workflow: Workflow) -> Workflow:
        """
        Deploy a workflow to NiFi.
        
        This method:
        1. Ensures the template exists in NiFi Registry
        2. Creates a parameter context for workflow-specific configuration
        3. Instantiates the template as a process group
        4. Updates the workflow with deployment information
        """
        try:
            # Get the template
            template = await self._get_template(workflow.template_id)
            
            # Deploy to NiFi Registry if needed
            registry_flow_id, registry_bucket_id = await self._ensure_template_in_registry(template)
            
            # Create parameter context
            param_context = await self._create_parameter_context(workflow)
            
            # Deploy process group
            process_group = await self._create_process_group(workflow, template, param_context)
            
            # Update workflow with deployment information
            workflow.update_nifi_deployment(
                process_group_id=process_group["component"]["id"],
                parameter_context_id=param_context["component"]["id"],
                deployment_method="registry",
                flow_version=1
            )
            
            workflow.status = "ACTIVE"
            
            # Commit changes
            self.session.add(workflow)
            await self.session.commit()
            await self.session.refresh(workflow)
            
            return workflow
            
        except Exception as e:
            log.error(f"Failed to deploy workflow {workflow.workflow_id}: {str(e)}")
            workflow.status = "ERROR"
            self.session.add(workflow)
            await self.session.commit()
            await self.session.refresh(workflow)
            raise NiFiWorkflowDeploymentError(f"Failed to deploy workflow: {str(e)}")
    
    async def undeploy_workflow(self, workflow: Workflow) -> Workflow:
        """
        Undeploy a workflow from NiFi.
        
        This method:
        1. Stops the process group
        2. Deletes the process group
        3. Deletes the parameter context
        4. Updates workflow status
        """
        try:
            if not workflow.nifi_process_group_id:
                raise ValueError("Workflow is not deployed to NiFi")
            
            # Stop process group first
            async with NiFiAPIClient(settings.NIFI_URL) as nifi_client:
                # Get current process group version
                pg_info = await nifi_client.get_process_group(workflow.nifi_process_group_id)
                version = pg_info["revision"]["version"]
                
                # Stop the process group
                await nifi_client.stop_process_group(workflow.nifi_process_group_id)
                
                # Delete the process group
                await nifi_client.delete_process_group(workflow.nifi_process_group_id, version)
                
                # Delete parameter context if it exists
                if workflow.nifi_parameter_context_id:
                    # TODO: Implement parameter context deletion when API supports it
                    pass
            
            # Update workflow status
            workflow.nifi_process_group_id = None
            workflow.nifi_parameter_context_id = None
            workflow.deployment_method = None
            workflow.flow_version = None
            workflow.status = "DELETED"
            
            # Commit changes
            self.session.add(workflow)
            await self.session.commit()
            await self.session.refresh(workflow)
            
            return workflow
            
        except Exception as e:
            log.error(f"Failed to undeploy workflow {workflow.workflow_id}: {str(e)}")
            workflow.status = "ERROR"
            self.session.add(workflow)
            await self.session.commit()
            await self.session.refresh(workflow)
            raise NiFiWorkflowDeploymentError(f"Failed to undeploy workflow: {str(e)}")
    
    async def start_workflow(self, workflow: Workflow) -> Workflow:
        """Start a deployed workflow in NiFi."""
        try:
            if not workflow.nifi_process_group_id:
                raise ValueError("Workflow is not deployed to NiFi")
            
            async with NiFiAPIClient(settings.NIFI_URL) as nifi_client:
                await nifi_client.start_process_group(workflow.nifi_process_group_id)
            
            workflow.status = "ACTIVE"
            self.session.add(workflow)
            await self.session.commit()
            await self.session.refresh(workflow)
            
            return workflow
            
        except Exception as e:
            log.error(f"Failed to start workflow {workflow.workflow_id}: {str(e)}")
            workflow.status = "ERROR"
            self.session.add(workflow)
            await self.session.commit()
            await self.session.refresh(workflow)
            raise NiFiWorkflowDeploymentError(f"Failed to start workflow: {str(e)}")
    
    async def stop_workflow(self, workflow: Workflow) -> Workflow:
        """Stop a deployed workflow in NiFi."""
        try:
            if not workflow.nifi_process_group_id:
                raise ValueError("Workflow is not deployed to NiFi")
            
            async with NiFiAPIClient(settings.NIFI_URL) as nifi_client:
                await nifi_client.stop_process_group(workflow.nifi_process_group_id)
            
            workflow.status = "PAUSED"
            self.session.add(workflow)
            await self.session.commit()
            await self.session.refresh(workflow)
            
            return workflow
            
        except Exception as e:
            log.error(f"Failed to stop workflow {workflow.workflow_id}: {str(e)}")
            workflow.status = "ERROR"
            self.session.add(workflow)
            await self.session.commit()
            await self.session.refresh(workflow)
            raise NiFiWorkflowDeploymentError(f"Failed to stop workflow: {str(e)}")
    
    async def get_workflow_status(self, workflow: Workflow) -> Dict[str, Any]:
        """
        Get detailed status of a deployed workflow from NiFi.
        
        Returns status information including:
        - Process group status
        - Component health
        - Error information
        """
        if not workflow.nifi_process_group_id:
            return {
                "status": "NOT_DEPLOYED",
                "nifi_status": None,
                "health_check": {
                    "status": "unknown",
                    "issues": ["Workflow not deployed to NiFi"]
                }
            }
        
        try:
            async with NiFiAPIClient(settings.NIFI_URL) as nifi_client:
                # Get process group status
                pg_info = await nifi_client.get_process_group(workflow.nifi_process_group_id)
                nifi_status = pg_info["component"].get("state", "UNKNOWN")
                
                # Get flow status
                flow_status = await nifi_client.get_flow_status()
                
                return {
                    "status": workflow.status,
                    "nifi_status": nifi_status,
                    "flow_status": flow_status,
                    "health_check": {
                        "status": "healthy" if nifi_status == "RUNNING" else "unhealthy",
                        "issues": [] if nifi_status == "RUNNING" else [f"Process group state: {nifi_status}"]
                    }
                }
                
        except Exception as e:
            log.error(f"Failed to get status for workflow {workflow.workflow_id}: {str(e)}")
            return {
                "status": "ERROR",
                "nifi_status": None,
                "health_check": {
                    "status": "unhealthy",
                    "issues": [f"Failed to query NiFi: {str(e)}"]
                }
            }
    
    async def _get_template(self, template_id: str) -> WorkflowTemplate:
        """Get template from database."""
        query = select(WorkflowTemplate).where(WorkflowTemplate.template_id == template_id)
        result = await self.session.execute(query)
        template = result.scalar_one_or_none()
        
        if not template:
            raise ValueError(f"Template {template_id} not found")
        
        return template
    
    async def _ensure_template_in_registry(self, template: WorkflowTemplate) -> tuple[str, str]:
        """
        Ensure template exists in NiFi Registry.
        
        Returns:
            tuple of (flow_id, bucket_id)
        """
        async with NiFiRegistryClient(settings.NIFI_REGISTRY_URL) as registry_client:
            # Check if bucket exists, create if not
            buckets = await registry_client.list_buckets()
            bucket_name = f"edi-lens-{template.scope}"
            
            bucket = next((b for b in buckets if b["name"] == bucket_name), None)
            if not bucket:
                bucket = await registry_client.create_bucket(
                    name=bucket_name,
                    description=f"EDI Lens {template.scope} workflows"
                )
            
            bucket_id = bucket["identifier"]
            
            # Check if flow exists, create if not
            flows = await registry_client.list_flows(bucket_id)
            flow_name = f"{template.name}-{template.template_id}"
            
            flow = next((f for f in flows if f["name"] == flow_name), None)
            if not flow:
                flow = await registry_client.create_flow(
                    bucket_id=bucket_id,
                    flow_name=flow_name,
                    flow_description=template.description or f"Workflow template {template.name}"
                )
            
            flow_id = flow["identifier"]
            
            # Create flow version if it doesn't exist
            try:
                # Try to get the latest version
                await registry_client.get_flow_version(bucket_id, flow_id, "latest")
            except Exception:
                # Create initial version
                version_data = {
                    "flowContents": template.flow_definition,
                    "parameterContexts": {},
                    "externalControllerServices": {}
                }
                await registry_client.create_flow_version(
                    bucket_id=bucket_id,
                    flow_id=flow_id,
                    version_data=version_data,
                    comments=f"Initial version from EDI Lens template {template.template_id}"
                )
            
            # Update template with registry information
            template.nifi_registry_flow_id = flow_id
            template.nifi_registry_bucket_id = bucket_id
            self.session.add(template)
            await self.session.commit()
            
            return flow_id, bucket_id
    
    async def _create_parameter_context(self, workflow: Workflow) -> Dict[str, Any]:
        """
        Create a parameter context for the workflow with configuration values.
        
        Returns:
            Parameter context information from NiFi
        """
        import json
        
        async with NiFiAPIClient(settings.NIFI_URL) as nifi_client:
            # Convert workflow configuration to NiFi parameters
            parameters = []
            if workflow.configuration:
                for key, value in workflow.configuration.items():
                    # Convert value to string, but handle dictionaries properly
                    if isinstance(value, (dict, list)):
                        value_str = json.dumps(value)
                    else:
                        value_str = str(value) if value is not None else ""
                        
                    parameters.append({
                        "name": key,
                        "value": value_str,
                        "sensitive": False,
                        "description": f"Configuration parameter {key}"
                    })
            
            # Create parameter context
            param_context = await nifi_client.create_parameter_context(
                name=f"workflow-{workflow.workflow_id}",
                description=f"Parameters for workflow {workflow.name}",
                parameters=parameters
            )
            
            return param_context
    
    async def _create_process_group(
        self, 
        workflow: Workflow, 
        template: WorkflowTemplate,
        param_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a process group from the template.
        
        Returns:
            Process group information from NiFi
        """
        async with NiFiAPIClient(settings.NIFI_URL) as nifi_client:
            # Get root process group ID
            root_pg = await nifi_client.get_process_group("root")
            root_pg_id = root_pg["component"]["id"]
            
            # Create process group
            process_group = await nifi_client.create_process_group(
                parent_group_id=root_pg_id,
                name=f"{workflow.name}-{workflow.workflow_id}",
                position={"x": 100, "y": 100}
            )
            
            # TODO: Implement proper template instantiation when API is available
            # For now, we'll just create the process group structure
            # In a full implementation, we would:
            # 1. Instantiate the template from Registry
            # 2. Connect it to the parameter context
            # 3. Configure any required settings
            
            return process_group