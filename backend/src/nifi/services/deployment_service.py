"""
Workflow Deployment Service for EDI Lens.

This service handles the deployment of workflow templates to actual NiFi instances,
managing the full lifecycle from template instantiation to process group management.
"""

import asyncio
import logging
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.nifi.clients.nifi_client import NiFiAPIClient
from src.nifi.clients.registry_client import NiFiRegistryClient
from src.models.workflow_template import Workflow, WorkflowTemplate
from src.core.auth import AuthContext

logger = logging.getLogger(__name__)


class WorkflowDeploymentResult:
    """Result of workflow deployment operation."""
    
    def __init__(
        self,
        success: bool,
        workflow_id: str,
        nifi_process_group_id: Optional[str] = None,
        nifi_parameter_context_id: Optional[str] = None,
        deployment_method: str = "registry",
        flow_version: Optional[int] = None,
        error_message: Optional[str] = None,
        deployment_time_ms: int = 0
    ):
        self.success = success
        self.workflow_id = workflow_id
        self.nifi_process_group_id = nifi_process_group_id
        self.nifi_parameter_context_id = nifi_parameter_context_id
        self.deployment_method = deployment_method
        self.flow_version = flow_version
        self.error_message = error_message
        self.deployment_time_ms = deployment_time_ms
        self.deployed_at = datetime.utcnow()


class WorkflowDeploymentService:
    """Service for deploying workflows to NiFi instances."""
    
    def __init__(
        self,
        nifi_url: str,
        registry_url: str,
        nifi_auth_token: Optional[str] = None,
        registry_auth_token: Optional[str] = None
    ):
        self.nifi_url = nifi_url
        self.registry_url = registry_url
        self.nifi_auth_token = nifi_auth_token
        self.registry_auth_token = registry_auth_token

    async def deploy_workflow(
        self,
        session: AsyncSession,
        workflow_id: str,
        auth_context: AuthContext
    ) -> WorkflowDeploymentResult:
        """Deploy a workflow template to NiFi."""
        start_time = datetime.utcnow()
        
        try:
            # 1. Load workflow and template from database
            workflow = await self._get_workflow(session, workflow_id, auth_context.tenant_id)
            template = await self._get_template(session, workflow.template_id)
            
            # 2. Validate workflow is ready for deployment
            await self._validate_workflow_readiness(workflow, template)
            
            # 3. Deploy to NiFi based on deployment method
            if template.deployment_method == "registry":
                deployment_result = await self._deploy_via_registry(
                    workflow, template
                )
            else:
                # Fallback to XML deployment
                deployment_result = await self._deploy_via_xml(
                    workflow, template
                )
            
            # 4. Update workflow with deployment information
            if deployment_result.success:
                workflow.nifi_process_group_id = deployment_result.nifi_process_group_id
                workflow.nifi_parameter_context_id = deployment_result.nifi_parameter_context_id
                workflow.deployment_method = deployment_result.deployment_method
                workflow.flow_version = deployment_result.flow_version
                workflow.status = "ACTIVE"
                session.add(workflow)
                await session.commit()
            
            # 5. Calculate deployment time
            deployment_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            return WorkflowDeploymentResult(
                success=deployment_result.success,
                workflow_id=workflow_id,
                nifi_process_group_id=deployment_result.nifi_process_group_id,
                nifi_parameter_context_id=deployment_result.nifi_parameter_context_id,
                deployment_method=deployment_result.deployment_method,
                flow_version=deployment_result.flow_version,
                error_message=deployment_result.error_message,
                deployment_time_ms=int(deployment_time)
            )
            
        except Exception as e:
            deployment_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            return WorkflowDeploymentResult(
                success=False,
                workflow_id=workflow_id,
                error_message=f"Workflow deployment failed: {str(e)}",
                deployment_time_ms=int(deployment_time)
            )

    async def _get_workflow(
        self,
        session: AsyncSession,
        workflow_id: str,
        tenant_id: str
    ) -> Workflow:
        """Load workflow from database with tenant validation."""
        query = select(Workflow).where(
            Workflow.workflow_id == workflow_id,
            Workflow.tenant_id == tenant_id
        )
        result = await session.execute(query)
        workflow = result.scalar_one_or_none()
        
        if not workflow:
            raise ValueError(f"Workflow {workflow_id} not found or access denied")
        
        return workflow

    async def _get_template(
        self,
        session: AsyncSession,
        template_id: str
    ) -> WorkflowTemplate:
        """Load template from database."""
        query = select(WorkflowTemplate).where(
            WorkflowTemplate.template_id == template_id
        )
        result = await session.execute(query)
        template = result.scalar_one_or_none()
        
        if not template:
            raise ValueError(f"Template {template_id} not found")
        
        return template

    async def _validate_workflow_readiness(
        self,
        workflow: Workflow,
        template: WorkflowTemplate
    ) -> None:
        """Validate workflow can be deployed."""
        if workflow.status not in ["ACTIVE", "PENDING"]:
            raise ValueError(f"Workflow {workflow.workflow_id} is not in a deployable state (status: {workflow.status})")
        
        if template.status != "ACTIVE":
            raise ValueError(f"Template {template.template_id} is not active")

    async def _deploy_via_registry(
        self,
        workflow: Workflow,
        template: WorkflowTemplate
    ) -> WorkflowDeploymentResult:
        """Deploy workflow using NiFi Registry."""
        try:
            # Connect to both NiFi and Registry
            async with NiFiAPIClient(self.nifi_url, self.nifi_auth_token) as nifi_client, \
                       NiFiRegistryClient(self.registry_url, self.registry_auth_token) as registry_client:
                
                # 1. Create parameter context for workflow configuration
                parameter_context = await self._create_parameter_context(
                    nifi_client, workflow, template
                )
                
                # 2. Instantiate template in NiFi
                # For now, we'll assume the template already exists in Registry
                # In production, we would first deploy the template to Registry
                
                # 3. Create process group with parameter context
                process_group = await self._create_process_group(
                    nifi_client,
                    workflow,
                    template,
                    parameter_context["id"]
                )
                
                return WorkflowDeploymentResult(
                    success=True,
                    workflow_id=str(workflow.workflow_id),
                    nifi_process_group_id=process_group["id"],
                    nifi_parameter_context_id=parameter_context["id"],
                    deployment_method="registry",
                    flow_version=1  # TODO: Get actual version from template
                )
                
        except Exception as e:
            return WorkflowDeploymentResult(
                success=False,
                workflow_id=str(workflow.workflow_id),
                error_message=f"Registry deployment failed: {str(e)}"
            )

    async def _deploy_via_xml(
        self,
        workflow: Workflow,
        template: WorkflowTemplate
    ) -> WorkflowDeploymentResult:
        """Deploy workflow using XML flow definition."""
        # TODO: Implement XML deployment
        return WorkflowDeploymentResult(
            success=False,
            workflow_id=str(workflow.workflow_id),
            error_message="XML deployment not yet implemented"
        )

    async def _create_parameter_context(
        self,
        nifi_client: NiFiAPIClient,
        workflow: Workflow,
        template: WorkflowTemplate
    ) -> Dict[str, Any]:
        """Create parameter context with workflow configuration."""
        # Extract parameters from workflow configuration
        parameters = []
        config = workflow.configuration
        
        # Convert configuration to NiFi parameters
        for key, value in config.items():
            parameters.append({
                "name": key.upper(),
                "value": str(value),
                "description": f"Workflow configuration parameter: {key}",
                "sensitive": False
            })
        
        # Add tenant-specific parameters
        parameters.extend([
            {
                "name": "TENANT_ID",
                "value": workflow.tenant_id,
                "description": "Tenant identifier",
                "sensitive": False
            },
            {
                "name": "WORKFLOW_ID",
                "value": str(workflow.workflow_id),
                "description": "Workflow identifier",
                "sensitive": False
            }
        ])
        
        # Create parameter context
        context = await nifi_client.create_parameter_context(
            name=f"workflow-{workflow.workflow_id}-config",
            description=f"Configuration for workflow {workflow.name}",
            parameters=parameters
        )
        
        return context

    async def _create_process_group(
        self,
        nifi_client: NiFiAPIClient,
        workflow: Workflow,
        template: WorkflowTemplate,
        parameter_context_id: str
    ) -> Dict[str, Any]:
        """Create process group for workflow."""
        # Create process group
        process_group = await nifi_client.create_process_group(
            parent_group_id="root",  # TODO: Use proper parent group
            name=f"workflow-{workflow.workflow_id}",
            position={"x": 100, "y": 100}
        )
        
        # Associate parameter context with process group
        # This would typically be done by setting the parameter context on the process group
        # For now, we'll store the association in our database
        
        return process_group

    async def undeploy_workflow(
        self,
        session: AsyncSession,
        workflow_id: str,
        auth_context: AuthContext
    ) -> bool:
        """Undeploy a workflow from NiFi."""
        try:
            # 1. Load workflow from database
            workflow = await self._get_workflow(session, workflow_id, auth_context.tenant_id)
            
            # 2. Check if workflow is deployed
            if not workflow.nifi_process_group_id:
                logger.warning(f"Workflow {workflow_id} is not deployed to NiFi")
                return True
            
            # 3. Undeploy from NiFi
            async with NiFiAPIClient(self.nifi_url, self.nifi_auth_token) as nifi_client:
                # Delete process group
                if workflow.nifi_process_group_id:
                    await nifi_client.delete_process_group(
                        workflow.nifi_process_group_id
                    )
                
                # Delete parameter context
                if workflow.nifi_parameter_context_id:
                    # Note: NiFi doesn't have a direct delete parameter context API
                    # We would typically just leave it or mark it as inactive
                    pass
            
            # 4. Clear deployment information
            workflow.nifi_process_group_id = None
            workflow.nifi_parameter_context_id = None
            workflow.deployment_method = None
            workflow.flow_version = None
            workflow.status = "INACTIVE"
            session.add(workflow)
            await session.commit()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to undeploy workflow {workflow_id}: {str(e)}")
            return False

    async def restart_workflow(
        self,
        session: AsyncSession,
        workflow_id: str,
        auth_context: AuthContext
    ) -> WorkflowDeploymentResult:
        """Restart a deployed workflow."""
        # First undeploy
        await self.undeploy_workflow(session, workflow_id, auth_context)
        
        # Then redeploy
        return await self.deploy_workflow(session, workflow_id, auth_context)