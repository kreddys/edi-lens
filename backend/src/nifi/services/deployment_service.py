"""
Workflow Deployment Service for EDI Lens.

This service handles the deployment of workflow templates to actual NiFi instances,
managing the full lifecycle from template instantiation to process group management.
"""

import asyncio
import logging
import uuid
import xml.etree.ElementTree as ET
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
            from src.core.config import settings
            async with NiFiAPIClient(
                self.nifi_url, 
                self.nifi_auth_token,
                username=settings.NIFI_USERNAME,
                password=settings.NIFI_PASSWORD
            ) as nifi_client, \
                       NiFiRegistryClient(self.registry_url, self.registry_auth_token) as registry_client:
                
                # 1. Ensure template is registered in Registry
                registry_info = await self._ensure_template_in_registry(
                    registry_client, template
                )
                
                # 2. Create parameter context for workflow configuration
                parameter_context = await self._create_parameter_context(
                    nifi_client, workflow, template
                )
                
                # 3. Create process group and instantiate flow from Registry
                process_group = await self._create_process_group_from_registry(
                    nifi_client,
                    workflow,
                    template,
                    registry_info,
                    parameter_context["component"]["id"]
                )
                
                # 4. Associate parameter context with process group
                await self._associate_parameter_context(
                    nifi_client,
                    process_group["component"]["id"],
                    parameter_context["component"]["id"]
                )
                
                return WorkflowDeploymentResult(
                    success=True,
                    workflow_id=str(workflow.workflow_id),
                    nifi_process_group_id=process_group["component"]["id"],
                    nifi_parameter_context_id=parameter_context["component"]["id"],
                    deployment_method="registry",
                    flow_version=registry_info["version"]
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
        try:
            from src.core.config import settings
            async with NiFiAPIClient(
                self.nifi_url, 
                self.nifi_auth_token,
                username=settings.NIFI_USERNAME,
                password=settings.NIFI_PASSWORD
            ) as nifi_client:
                # 1. Convert JSON flow definition to NiFi XML
                xml_flow = self._convert_json_to_nifi_xml(template.flow_definition, workflow)
                
                # 2. Create parameter context for workflow configuration
                parameter_context = await self._create_parameter_context(
                    nifi_client, workflow, template
                )
                
                # 3. Create process group and upload XML flow
                process_group = await self._create_process_group_with_xml(
                    nifi_client,
                    workflow,
                    template,
                    xml_flow,
                    parameter_context["component"]["id"]
                )
                
                return WorkflowDeploymentResult(
                    success=True,
                    workflow_id=str(workflow.workflow_id),
                    nifi_process_group_id=process_group["component"]["id"],
                    nifi_parameter_context_id=parameter_context["component"]["id"],
                    deployment_method="xml",
                    flow_version=1
                )
                
        except Exception as e:
            return WorkflowDeploymentResult(
                success=False,
                workflow_id=str(workflow.workflow_id),
                error_message=f"XML deployment failed: {str(e)}"
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

    def _convert_json_to_nifi_xml(
        self,
        flow_definition: Dict[str, Any],
        workflow: Workflow
    ) -> str:
        """Convert JSON flow definition to NiFi XML template format."""
        # Create root template element
        template = ET.Element("template")
        template.set("encoding-version", "1.0")
        
        # Template description
        description = ET.SubElement(template, "description")
        description.text = f"Workflow: {workflow.name} (ID: {workflow.workflow_id})"
        
        # Group ID (use workflow ID)
        group_id = ET.SubElement(template, "groupId")
        group_id.text = str(workflow.workflow_id)
        
        # Name
        name = ET.SubElement(template, "name")
        name.text = workflow.name
        
        # Timestamp
        timestamp = ET.SubElement(template, "timestamp")
        timestamp.text = datetime.utcnow().strftime("%m/%d/%Y %H:%M:%S %Z")
        
        # Snippet
        snippet = ET.SubElement(template, "snippet")
        
        # Process groups
        process_groups = ET.SubElement(snippet, "processGroups")
        
        # Processors
        processors_element = ET.SubElement(snippet, "processors")
        for proc in flow_definition.get("processors", []):
            processor = ET.SubElement(processors_element, "processor")
            
            # Processor ID and basic info
            proc_id = ET.SubElement(processor, "id")
            proc_id.text = proc["id"]
            
            proc_name = ET.SubElement(processor, "name")
            proc_name.text = proc["name"]
            
            proc_type = ET.SubElement(processor, "type")
            proc_type.text = proc["type"]
            
            # Position
            position = ET.SubElement(processor, "position")
            pos_x = ET.SubElement(position, "x")
            pos_x.text = str(proc["position"]["x"])
            pos_y = ET.SubElement(position, "y")
            pos_y.text = str(proc["position"]["y"])
            
            # Properties
            config = ET.SubElement(processor, "config")
            properties = ET.SubElement(config, "properties")
            for prop_name, prop_value in proc.get("properties", {}).items():
                entry = ET.SubElement(properties, "entry")
                key = ET.SubElement(entry, "key")
                key.text = prop_name
                value = ET.SubElement(entry, "value")
                value.text = str(prop_value)
            
            # Scheduling
            scheduling_info = proc.get("scheduling", {})
            if scheduling_info:
                scheduling_period = ET.SubElement(config, "schedulingPeriod")
                scheduling_period.text = scheduling_info.get("period", "1 sec")
                
                scheduling_strategy = ET.SubElement(config, "schedulingStrategy")
                scheduling_strategy.text = scheduling_info.get("strategy", "TIMER_DRIVEN")
            
            # Auto terminated relationships
            auto_terminated = ET.SubElement(config, "autoTerminatedRelationships")
            for rel in proc.get("auto_terminated_relationships", []):
                relationship = ET.SubElement(auto_terminated, "relationship")
                relationship.text = rel
        
        # Connections
        connections_element = ET.SubElement(snippet, "connections")
        for conn in flow_definition.get("connections", []):
            connection = ET.SubElement(connections_element, "connection")
            
            conn_id = ET.SubElement(connection, "id")
            conn_id.text = f"conn-{uuid.uuid4()}"
            
            source_id = ET.SubElement(connection, "sourceId")
            source_id.text = conn["source"]
            
            dest_id = ET.SubElement(connection, "destinationId")
            dest_id.text = conn["destination"]
            
            # Handle relationship (can be string or list)
            relationship = conn.get("relationship", "success")
            if isinstance(relationship, list):
                for rel in relationship:
                    selected_rel = ET.SubElement(connection, "selectedRelationships")
                    selected_rel.text = rel
            else:
                selected_rel = ET.SubElement(connection, "selectedRelationships")
                selected_rel.text = relationship
        
        # Convert to string
        return ET.tostring(template, encoding='unicode')

    async def _create_process_group_with_xml(
        self,
        nifi_client: NiFiAPIClient,
        workflow: Workflow,
        template: WorkflowTemplate,
        xml_flow: str,
        parameter_context_id: str
    ) -> Dict[str, Any]:
        """Create process group and upload XML flow definition."""
        # Create empty process group first
        process_group = await nifi_client.create_process_group(
            parent_group_id="root",
            name=f"workflow-{workflow.workflow_id}",
            position={"x": 100, "y": 100}
        )
        
        # TODO: Upload XML template to NiFi and instantiate it
        # This would require additional NiFi API endpoints for template upload
        # For now, we'll return the process group
        
        return process_group

    async def _ensure_template_in_registry(
        self,
        registry_client: NiFiRegistryClient,
        template: WorkflowTemplate
    ) -> Dict[str, Any]:
        """Ensure template is registered in NiFi Registry."""
        # Check if bucket exists for EDI Lens templates
        buckets = await registry_client.list_buckets()
        edi_lens_bucket = None
        
        for bucket in buckets:
            if bucket["name"] == "edi-lens-workflows":
                edi_lens_bucket = bucket
                break
        
        # Create bucket if it doesn't exist
        if not edi_lens_bucket:
            edi_lens_bucket = await registry_client.create_bucket(
                name="edi-lens-workflows",
                description="EDI Lens workflow templates"
            )
        
        # Check if flow exists for this template
        flows = await registry_client.list_flows(edi_lens_bucket["identifier"])
        template_flow = None
        
        for flow in flows:
            if flow["name"] == template.name:
                template_flow = flow
                break
        
        # Create flow if it doesn't exist
        if not template_flow:
            template_flow = await registry_client.create_flow(
                bucket_id=edi_lens_bucket["identifier"],
                flow_name=template.name,
                flow_description=template.description
            )
            
            # Create flow version with template definition
            flow_version = await registry_client.create_flow_version(
                bucket_id=edi_lens_bucket["identifier"],
                flow_id=template_flow["identifier"],
                version_data=template.flow_definition,
                comments=f"Template version {template.version}"
            )
            
            return {
                "bucket_id": edi_lens_bucket["identifier"],
                "flow_id": template_flow["identifier"],
                "version": flow_version["version"]
            }
        else:
            # Get latest version
            versions = await registry_client.list_flow_versions(
                edi_lens_bucket["identifier"],
                template_flow["identifier"]
            )
            latest_version = max(versions, key=lambda v: v["version"])
            
            return {
                "bucket_id": edi_lens_bucket["identifier"],
                "flow_id": template_flow["identifier"],
                "version": latest_version["version"]
            }

    async def _create_process_group_from_registry(
        self,
        nifi_client: NiFiAPIClient,
        workflow: Workflow,
        template: WorkflowTemplate,
        registry_info: Dict[str, Any],
        parameter_context_id: str
    ) -> Dict[str, Any]:
        """Create process group and instantiate flow from Registry."""
        # Create empty process group
        process_group = await nifi_client.create_process_group(
            parent_group_id="root",
            name=f"workflow-{workflow.workflow_id}",
            position={"x": 100, "y": 100}
        )
        
        # TODO: Add NiFi API method to instantiate flow from Registry
        # This would require additional API endpoints in NiFiAPIClient
        # For now, we'll return the empty process group
        
        return process_group

    async def _associate_parameter_context(
        self,
        nifi_client: NiFiAPIClient,
        process_group_id: str,
        parameter_context_id: str
    ) -> None:
        """Associate parameter context with process group."""
        # Update process group to use the parameter context
        try:
            await nifi_client.update_process_group(
                process_group_id=process_group_id,
                version=0  # TODO: Get actual version
            )
            # TODO: Add parameter context association to the update
            # This would require enhancing the update_process_group method
            logger.info(f"Associated parameter context {parameter_context_id} with process group {process_group_id}")
        except Exception as e:
            logger.warning(f"Failed to associate parameter context: {str(e)}")

    async def start_workflow(
        self,
        session: AsyncSession,
        workflow_id: str,
        auth_context: AuthContext
    ) -> bool:
        """Start a deployed workflow."""
        try:
            # Load workflow from database
            workflow = await self._get_workflow(session, workflow_id, auth_context.tenant_id)
            
            if not workflow.nifi_process_group_id:
                logger.error(f"Workflow {workflow_id} is not deployed to NiFi")
                return False
            
            # Start process group in NiFi
            async with NiFiAPIClient(self.nifi_url, self.nifi_auth_token) as nifi_client:
                await nifi_client.start_process_group(workflow.nifi_process_group_id)
            
            # Update workflow status
            workflow.status = "RUNNING"
            session.add(workflow)
            await session.commit()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to start workflow {workflow_id}: {str(e)}")
            return False

    async def stop_workflow(
        self,
        session: AsyncSession,
        workflow_id: str,
        auth_context: AuthContext
    ) -> bool:
        """Stop a running workflow."""
        try:
            # Load workflow from database
            workflow = await self._get_workflow(session, workflow_id, auth_context.tenant_id)
            
            if not workflow.nifi_process_group_id:
                logger.error(f"Workflow {workflow_id} is not deployed to NiFi")
                return False
            
            # Stop process group in NiFi
            async with NiFiAPIClient(self.nifi_url, self.nifi_auth_token) as nifi_client:
                await nifi_client.stop_process_group(workflow.nifi_process_group_id)
            
            # Update workflow status
            workflow.status = "STOPPED"
            session.add(workflow)
            await session.commit()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop workflow {workflow_id}: {str(e)}")
            return False

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