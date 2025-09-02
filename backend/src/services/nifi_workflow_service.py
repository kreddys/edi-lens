"""
Service for managing NiFi workflow deployments.

This service handles the deployment, management, and control of workflows
in Apache NiFi, integrating with the NiFi Registry for versioned flows
and the NiFi API for runtime process group management.
"""

import logging
import uuid
import asyncio
from typing import Dict, Any, Optional, List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.core.config import settings
from src.models.workflow_template import Workflow
from src.models.registry_models import RegistryTemplate
from src.nifi.clients.nifi_client import NiFiAPIClient
from src.nifi.clients.registry_client import NiFiRegistryClient
from src.api.schemas import WorkflowStatus
from src.services.registry_service import RegistryService

log = logging.getLogger(__name__)


class NiFiWorkflowDeploymentError(Exception):
    """Exception raised for NiFi workflow deployment errors."""
    pass


class NiFiWorkflowService:
    """Service for managing NiFi workflow deployments."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.registry_service = RegistryService(session)
    
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
            
            # Use Registry service to deploy from Registry
            async with NiFiAPIClient(
                settings.NIFI_URL,
                username=settings.NIFI_USERNAME,
                password=settings.NIFI_PASSWORD
            ) as nifi_client:
                # Get root process group
                root_pg = await nifi_client.get_process_group("root")
                root_pg_id = root_pg["component"]["id"]
                
                # Deploy from Registry using the consolidated service
                process_group = await self.registry_service.deploy_from_registry(
                    nifi_client=nifi_client,
                    parent_group_id=root_pg_id,
                    bucket_id=str(template.bucket_id),
                    flow_id=str(template.template_id),
                    flow_version=template.current_version,
                    process_group_name=f"{workflow.name}-{workflow.workflow_id}",
                    position={"x": 100, "y": 100}
                )
                
                # Create parameter context for workflow configuration
                param_context = await self._create_parameter_context(workflow)
            
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

            async with NiFiAPIClient(
                settings.NIFI_URL,
                username=settings.NIFI_USERNAME,
                password=settings.NIFI_PASSWORD
            ) as nifi_client:
                # Stop the process group first to ensure it can be deleted
                await nifi_client.stop_process_group(workflow.nifi_process_group_id)
                
                # Add a small delay to allow NiFi to process the state change
                await asyncio.sleep(1)

                # Refetch the process group to get the latest revision after stopping
                pg_info = await nifi_client.get_process_group(workflow.nifi_process_group_id)
                version = pg_info["revision"]["version"]

                # Delete the process group with the latest version
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
            
            async with NiFiAPIClient(
                settings.NIFI_URL,
                username=settings.NIFI_USERNAME,
                password=settings.NIFI_PASSWORD
            ) as nifi_client:
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
            
            async with NiFiAPIClient(
                settings.NIFI_URL,
                username=settings.NIFI_USERNAME,
                password=settings.NIFI_PASSWORD
            ) as nifi_client:
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
                "workflow_id": str(workflow.workflow_id),
                "status": "NOT_DEPLOYED",
                "is_deployed": workflow.is_deployed,
                "nifi_status": None,
                "health_check": {
                    "status": "unknown",
                    "issues": ["Workflow not deployed to NiFi"]
                }
            }
        
        try:
            async with NiFiAPIClient(
                settings.NIFI_URL,
                username=settings.NIFI_USERNAME,
                password=settings.NIFI_PASSWORD
            ) as nifi_client:
                # Get process group status
                pg_info = await nifi_client.get_process_group(workflow.nifi_process_group_id)
                nifi_status = pg_info["component"].get("state", "UNKNOWN")
                
                # Get flow status
                flow_status = await nifi_client.get_flow_status()
                
                return {
                    "workflow_id": str(workflow.workflow_id),
                    "status": workflow.status,
                    "is_deployed": workflow.is_deployed,
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
                "workflow_id": str(workflow.workflow_id),
                "status": "ERROR",
                "is_deployed": workflow.is_deployed,
                "nifi_status": None,
                "health_check": {
                    "status": "unhealthy",
                    "issues": [f"Failed to query NiFi: {str(e)}"]
                }
            }
    
    async def _get_template(self, template_id: str) -> RegistryTemplate:
        """Get template from Registry-first database."""
        query = select(RegistryTemplate).where(RegistryTemplate.template_id == template_id)
        result = await self.session.execute(query)
        template = result.scalar_one_or_none()
        
        if not template:
            raise ValueError(f"Template {template_id} not found")
        
        return template
    
    async def _ensure_template_in_registry(self, template: RegistryTemplate) -> tuple[str, str]:
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
        
        async with NiFiAPIClient(
            settings.NIFI_URL,
            username=settings.NIFI_USERNAME,
            password=settings.NIFI_PASSWORD
        ) as nifi_client:
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
        template: RegistryTemplate,
        param_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a process group from the template.
        
        Returns:
            Process group information from NiFi
        """
        async with NiFiAPIClient(
            settings.NIFI_URL,
            username=settings.NIFI_USERNAME,
            password=settings.NIFI_PASSWORD
        ) as nifi_client:
            # Get root process group ID
            root_pg = await nifi_client.get_process_group("root")
            root_pg_id = root_pg["component"]["id"]
            
            # Create process group
            process_group = await nifi_client.create_process_group(
                parent_group_id=root_pg_id,
                name=f"{workflow.name}-{workflow.workflow_id}",
                position={"x": 100, "y": 100}
            )
            
            # Instantiate the template flow definition
            await self._instantiate_template_flow(
                nifi_client, 
                process_group["component"]["id"], 
                template, 
                workflow,
                param_context
            )
            
            return process_group
    
    async def _instantiate_template_flow(
        self,
        nifi_client,
        process_group_id: str,
        template: RegistryTemplate,
        workflow: Workflow,
        param_context: Dict[str, Any]
    ):
        """
        Instantiate processors and connections from template flow definition.
        """
        import yaml
        import re
        
        # Get flow definition from template model
        flow_definition = template.flow_definition or {}
        
        if not flow_definition:
            raise ValueError(f"Template {template.template_id} has no flow_definition")
        
        # Create a mapping of parameter values for substitution
        param_values = {}
        if workflow.configuration:
            param_values.update(workflow.configuration)
        param_values["tenant_id"] = workflow.tenant_id
        
        # Store processor IDs for connection creation
        processor_ids = {}
        
        # Create processors
        processors = flow_definition.get("processors", [])
        log.info(f"Creating {len(processors)} processors for workflow {workflow.workflow_id}")
        
        for processor_def in processors:
            log.info(f"Creating processor: {processor_def['name']} (type: {processor_def['type']})")
            
            # Generic parameter substitution function
            def substitute_params(obj):
                """Recursively substitute parameters in any data structure."""
                if isinstance(obj, str):
                    # Replace #{param_name} with actual values
                    substituted_value = re.sub(
                        r'#\{([^}]+)\}',
                        lambda m: str(param_values.get(m.group(1), m.group(0))),
                        obj
                    )
                    # Special handling for boolean values - ensure they're lowercase
                    # Check if this looks like a boolean string
                    lower_val = substituted_value.lower()
                    if lower_val in ["true", "false"]:
                        return lower_val
                    return substituted_value
                elif isinstance(obj, dict):
                    return {k: substitute_params(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [substitute_params(item) for item in obj]
                else:
                    return obj
            
            # Substitute parameters in all processor configuration
            substituted_def = substitute_params(processor_def)
            
            # Extract properties and scheduling after substitution
            properties = substituted_def.get("properties", {})
            scheduling = substituted_def.get("scheduling", {})
            
            log.info(f"Processor {processor_def['name']} properties after substitution: {properties}")
            log.info(f"Processor {processor_def['name']} scheduling after substitution: {scheduling}")
            
            # Create processor with properties and scheduling configuration
            try:
                processor = await nifi_client.create_processor(
                    parent_group_id=process_group_id,
                    processor_type=processor_def["type"],
                    name=processor_def["name"],
                    position=processor_def.get("position", {"x": 100, "y": 100}),
                    properties=properties if properties else None,
                    scheduling=scheduling if scheduling else None
                )
            except Exception as e:
                log.error(f"Failed to create processor '{processor_def['name']}' of type '{processor_def['type']}': {str(e)}")
                log.error(f"Processor properties: {properties}")
                log.error(f"Processor scheduling: {scheduling}")
                raise Exception(f"Failed to create processor '{processor_def['name']}': {str(e)}") from e
            
            processor_id = processor["component"]["id"]
            
            processor_ids[processor_def.get("identifier", processor_def.get("id"))] = processor["component"]["id"]
            log.info(f"Created processor {processor_def['name']} ({processor_def.get('identifier', processor_def.get('id'))}) with ID {processor_id}")
        
        # Create connections
        connections = flow_definition.get("connections", [])
        log.info(f"Creating {len(connections)} connections for workflow {workflow.workflow_id}")
        
        for conn_def in connections:
            source_id = processor_ids.get(conn_def["source"]["id"])
            destination_id = processor_ids.get(conn_def["destination"]["id"])
            
            if not source_id or not destination_id:
                log.warning(f"Skipping connection {conn_def.get('identifier', conn_def.get('id', 'unknown'))} - missing processor IDs")
                continue
            
            # Create connection
            connection = await nifi_client.create_connection(
                source_id=source_id,
                source_type="PROCESSOR",
                destination_id=destination_id,
                destination_type="PROCESSOR",
                relationships=conn_def.get("selectedRelationships", []),
                parent_group_id=process_group_id,
                name=conn_def.get("name"),
                back_pressure_object_threshold=conn_def.get("backPressureObjectThreshold", 1000),
                back_pressure_data_size_threshold=conn_def.get("backPressureDataSizeThreshold", "1 GB"),
                flow_file_expiration=conn_def.get("flowFileExpiration", "0 sec")
            )
            
            log.info(f"Created connection {conn_def['name']} ({conn_def.get('identifier', conn_def.get('id', 'unknown'))})")
        
        log.info(f"Successfully instantiated template flow for workflow {workflow.workflow_id}")