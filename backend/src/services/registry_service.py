"""
Registry Service for NiFi Registry integration.

This service implements the Registry-first architecture where NiFi Registry
is the source of truth for flow definitions, and the database stores only
references and metadata.
"""

import logging
import uuid
from typing import Dict, Any, Optional, List, Tuple
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from src.core.config import settings
from src.models.registry_models import RegistryTemplate, WorkflowInstance, RegistryBucket
from src.nifi.clients.registry_client import NiFiRegistryClient
from src.nifi.clients.nifi_client import NiFiAPIClient
from src.nifi.services.registry_integration_service import RegistryIntegrationService

log = logging.getLogger(__name__)


class RegistryServiceError(Exception):
    """Exception raised for Registry service errors."""
    pass


class RegistryService:
    """Service for managing NiFi Registry integration."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    # === Template Management ===
    
    async def create_template(
        self,
        name: str,
        description: str,
        flow_definition: Dict[str, Any],
        scope: str = "GLOBAL",
        tenant_id: Optional[str] = None,
        created_by: Optional[str] = None
    ) -> RegistryTemplate:
        """
        Create a new template in NiFi Registry and store reference in database.
        
        Args:
            name: Template name
            description: Template description
            flow_definition: NiFi flow definition (processors, connections, etc.)
            scope: GLOBAL or TENANT
            tenant_id: Required if scope is TENANT
            created_by: User who created the template
            
        Returns:
            RegistryTemplate with Registry IDs populated
        """
        try:
            # 1. Validate scope and tenant_id
            if scope == "TENANT" and not tenant_id:
                raise ValueError("tenant_id is required for TENANT scope templates")
            
            # 2. Get or create bucket
            bucket = await self._ensure_bucket_exists(scope, tenant_id)
            
            # 3. Check if flow already exists and create if needed
            async with NiFiRegistryClient(settings.NIFI_REGISTRY_URL) as registry_client:
                # Check if flow already exists in Registry bucket
                existing_flows = await registry_client.list_flows(str(bucket.bucket_id))
                registry_flow = None
                
                for flow in existing_flows:
                    if flow["name"] == name:
                        registry_flow = flow
                        break
                
                # Create flow if it doesn't exist
                if not registry_flow:
                    registry_flow = await registry_client.create_flow(
                        bucket_id=str(bucket.bucket_id),
                        flow_name=name,
                        flow_description=description or f"Template: {name}"
                    )
                
                flow_id = UUID(registry_flow["identifier"])
                
                # Check if flow already has versions and create initial version if needed
                try:
                    # Try to get existing versions
                    existing_versions = await registry_client.list_flow_versions(
                        bucket_id=str(bucket.bucket_id),
                        flow_id=str(flow_id)
                    )
                    
                    # If no versions exist, create initial version
                    if not existing_versions:
                        version_data = {
                            "flowContents": flow_definition,
                            "parameterContexts": {},
                            "externalControllerServices": {}
                        }
                        
                        await registry_client.create_flow_version(
                            bucket_id=str(bucket.bucket_id),
                            flow_id=str(flow_id),
                            version_data=version_data,
                            comments="Initial version created via EDI Lens"
                        )
                        log.info(f"Created initial version for flow {flow_id}")
                    else:
                        log.info(f"Flow {flow_id} already has {len(existing_versions)} version(s)")
                        
                except Exception as version_error:
                    # If getting versions fails, try creating one (might be first version)
                    log.debug(f"Could not get existing versions, attempting to create: {version_error}")
                    try:
                        version_data = {
                            "flowContents": flow_definition,
                            "parameterContexts": {},
                            "externalControllerServices": {}
                        }
                        
                        await registry_client.create_flow_version(
                            bucket_id=str(bucket.bucket_id),
                            flow_id=str(flow_id),
                            version_data=version_data,
                            comments="Initial version created via EDI Lens"
                        )
                        log.info(f"Created initial version for flow {flow_id}")
                    except Exception as create_error:
                        log.info(f"Flow {flow_id} already has versions (409 expected): {create_error}")
                
                log.info(f"Ensured flow {flow_id} exists in Registry bucket {bucket.bucket_id}")
            
            # 4. Store reference in database (with idempotency check)
            # Check if database record already exists
            existing_db_template = await self.session.execute(
                select(RegistryTemplate).where(RegistryTemplate.template_id == flow_id)
            )
            db_template = existing_db_template.scalar_one_or_none()
            
            if db_template:
                log.info(f"Template reference {flow_id} already exists in database")
                return db_template
            
            # Create new database record
            template = RegistryTemplate(
                template_id=flow_id,
                bucket_id=bucket.bucket_id,
                current_version=1,
                name=name,
                description=description,
                scope=scope,
                tenant_id=tenant_id,
                created_by=created_by
            )
            
            self.session.add(template)
            await self.session.commit()
            await self.session.refresh(template)
            
            log.info(f"Created template reference {template.template_id} in database")
            return template
            
        except Exception as e:
            await self.session.rollback()
            log.error(f"Failed to create template: {str(e)}")
            raise RegistryServiceError(f"Failed to create template: {str(e)}")
    
    async def update_template(
        self,
        template_id: UUID,
        flow_definition: Dict[str, Any],
        comments: str = "Updated via EDI Lens",
        updated_by: Optional[str] = None
    ) -> RegistryTemplate:
        """
        Update template by creating a new version in Registry.
        
        Args:
            template_id: Template ID (Registry flow ID)
            flow_definition: Updated flow definition
            comments: Version comments
            updated_by: User who updated the template
            
        Returns:
            Updated RegistryTemplate
        """
        try:
            # 1. Get template from database
            template = await self.get_template(template_id)
            if not template:
                raise ValueError(f"Template {template_id} not found")
            
            # 2. Get current highest version number
            async with NiFiRegistryClient(settings.NIFI_REGISTRY_URL) as registry_client:
                # Get existing versions to determine next version number
                existing_versions = await registry_client.list_flow_versions(
                    bucket_id=str(template.bucket_id),
                    flow_id=str(template.template_id)
                )
                
                # Calculate next version number
                if existing_versions:
                    max_version = max(v["version"] for v in existing_versions)
                    next_version = max_version + 1
                else:
                    next_version = 1
                
                # Create new version in Registry
                version_data = {
                    "flowContents": flow_definition,
                    "parameterContexts": {},
                    "externalControllerServices": {}
                }
                
                new_version = await registry_client.create_flow_version(
                    bucket_id=str(template.bucket_id),
                    flow_id=str(template.template_id),
                    version_data=version_data,
                    comments=comments
                )
                
                # Get version number from response (should match our calculated next_version)
                if "snapshotMetadata" in new_version:
                    new_version_number = new_version["snapshotMetadata"]["version"]
                elif "version" in new_version:
                    new_version_number = new_version["version"]
                else:
                    # Fallback to our calculated version
                    new_version_number = next_version
                    
                log.info(f"Created version {new_version_number} for template {template_id}")
            
            # 3. Update template current version
            template.current_version = new_version_number
            
            self.session.add(template)
            await self.session.commit()
            await self.session.refresh(template)
            
            return template
            
        except Exception as e:
            await self.session.rollback()
            log.error(f"Failed to update template {template_id}: {str(e)}")
            raise RegistryServiceError(f"Failed to update template: {str(e)}")
    
    async def get_template(self, template_id: UUID) -> Optional[RegistryTemplate]:
        """Get template by ID."""
        query = select(RegistryTemplate).where(RegistryTemplate.template_id == template_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def list_templates(
        self,
        scope: Optional[str] = None,
        tenant_id: Optional[str] = None,
        status: str = "ACTIVE"
    ) -> List[RegistryTemplate]:
        """List templates with optional filtering."""
        query = select(RegistryTemplate).where(RegistryTemplate.status == status)
        
        if scope:
            query = query.where(RegistryTemplate.scope == scope)
        
        if tenant_id:
            query = query.where(RegistryTemplate.tenant_id == tenant_id)
        
        query = query.order_by(RegistryTemplate.created_at.desc())
        
        result = await self.session.execute(query)
        return result.scalars().all()
    
    async def get_template_flow_definition(
        self,
        template_id: UUID,
        version: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get flow definition from Registry.
        
        Args:
            template_id: Template ID (Registry flow ID)
            version: Specific version, or None for current version
            
        Returns:
            Flow definition from Registry
        """
        try:
            template = await self.get_template(template_id)
            if not template:
                raise ValueError(f"Template {template_id} not found")
            
            version_to_get = version or template.current_version
            
            async with NiFiRegistryClient(settings.NIFI_REGISTRY_URL) as registry_client:
                flow_version = await registry_client.get_flow_version(
                    bucket_id=str(template.bucket_id),
                    flow_id=str(template.template_id),
                    version=version_to_get
                )
                
                return flow_version["flowContents"]
                
        except Exception as e:
            log.error(f"Failed to get flow definition for template {template_id}: {str(e)}")
            raise RegistryServiceError(f"Failed to get flow definition: {str(e)}")
    
    # === Workflow Instance Management ===
    
    async def create_workflow_instance(
        self,
        template_id: UUID,
        name: str,
        tenant_id: str,
        configuration: Dict[str, Any],
        description: Optional[str] = None,
        template_version: Optional[int] = None,
        created_by: Optional[str] = None
    ) -> WorkflowInstance:
        """
        Create a workflow instance (not yet deployed to NiFi).
        
        Args:
            template_id: Template to instantiate
            name: Workflow instance name
            tenant_id: Tenant ID
            configuration: Instance configuration parameters
            description: Optional description
            template_version: Specific template version, or None for current
            created_by: User who created the instance
            
        Returns:
            WorkflowInstance in CREATED status
        """
        try:
            # 1. Validate template exists
            template = await self.get_template(template_id)
            if not template:
                raise ValueError(f"Template {template_id} not found")
            
            # 2. Determine version to use
            version_to_use = template_version or template.current_version
            
            # 3. Create workflow instance
            workflow = WorkflowInstance(
                name=name,
                description=description,
                tenant_id=tenant_id,
                template_id=template_id,
                template_version=version_to_use,
                configuration=configuration,
                created_by=created_by,
                status="CREATED"
            )
            
            self.session.add(workflow)
            await self.session.commit()
            await self.session.refresh(workflow)
            
            # 4. Increment template usage count
            template.increment_usage_count()
            self.session.add(template)
            await self.session.commit()
            
            # No need to load template relationship since we handle serialization manually
            
            log.info(f"Created workflow instance {workflow.workflow_id}")
            return workflow
            
        except Exception as e:
            await self.session.rollback()
            log.error(f"Failed to create workflow instance: {str(e)}")
            raise RegistryServiceError(f"Failed to create workflow instance: {str(e)}")
    
    async def deploy_workflow_instance(
        self,
        workflow_id: UUID,
        registry_client_id: Optional[str] = None
    ) -> WorkflowInstance:
        """
        Deploy workflow instance to NiFi using Registry version control.
        
        Args:
            workflow_id: Workflow instance ID
            registry_client_id: NiFi registry client ID (will be auto-detected if None)
            
        Returns:
            WorkflowInstance with deployment information
        """
        try:
            # 1. Get workflow instance with template
            query = select(WorkflowInstance).options(
                selectinload(WorkflowInstance.template)
            ).where(WorkflowInstance.workflow_id == workflow_id)
            result = await self.session.execute(query)
            workflow = result.scalar_one_or_none()
            
            if not workflow:
                raise ValueError(f"Workflow instance {workflow_id} not found")
            
            if workflow.is_deployed:
                raise ValueError(f"Workflow {workflow_id} is already deployed")
            
            # 2. Deploy to NiFi using Registry
            async with NiFiAPIClient(
                settings.NIFI_URL,
                username=settings.NIFI_USERNAME,
                password=settings.NIFI_PASSWORD
            ) as nifi_client:
                
                # Get root process group
                root_pg = await nifi_client.get_process_group("root")
                root_pg_id = root_pg["component"]["id"]
                
                # Create parameter context for configuration
                param_context = await self._create_parameter_context(workflow, nifi_client)
                
                # Deploy from Registry using version control
                integration_service = RegistryIntegrationService()
                
                # Ensure Registry client is set up in NiFi
                await integration_service.setup_registry_integration()
                
                # Deploy from Registry
                process_group = await integration_service.deploy_from_registry(
                    nifi_client=nifi_client,
                    parent_group_id=root_pg_id,
                    bucket_id=str(workflow.template.bucket_id),
                    flow_id=str(workflow.template_id),
                    flow_version=workflow.template_version,
                    process_group_name=f"{workflow.name}-{workflow.workflow_id}",
                    position={"x": 100, "y": 100}
                )
                
                # Update workflow with deployment info
                workflow.mark_deployed(
                    process_group_id=process_group["component"]["id"],
                    parameter_context_id=param_context["component"]["id"] if param_context else None
                )
                workflow.nifi_registry_client_id = registry_client_id
                
                self.session.add(workflow)
                await self.session.commit()
                await self.session.refresh(workflow)
                
                log.info(f"Deployed workflow {workflow_id} to NiFi process group {workflow.nifi_process_group_id}")
                return workflow
                
        except Exception as e:
            await self.session.rollback()
            log.error(f"Failed to deploy workflow {workflow_id}: {str(e)}")
            raise RegistryServiceError(f"Failed to deploy workflow: {str(e)}")
    
    async def get_workflow_instance(self, workflow_id: UUID) -> Optional[WorkflowInstance]:
        """Get workflow instance by ID."""
        query = select(WorkflowInstance).options(
            selectinload(WorkflowInstance.template)
        ).where(WorkflowInstance.workflow_id == workflow_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def list_workflow_instances(
        self,
        tenant_id: Optional[str] = None,
        template_id: Optional[UUID] = None,
        status: Optional[str] = None
    ) -> List[WorkflowInstance]:
        """List workflow instances with optional filtering."""
        query = select(WorkflowInstance).options(selectinload(WorkflowInstance.template))
        
        if tenant_id:
            query = query.where(WorkflowInstance.tenant_id == tenant_id)
        
        if template_id:
            query = query.where(WorkflowInstance.template_id == template_id)
        
        if status:
            query = query.where(WorkflowInstance.status == status)
        
        query = query.order_by(WorkflowInstance.created_at.desc())
        
        result = await self.session.execute(query)
        return result.scalars().all()
    
    # === Helper Methods ===
    
    async def _ensure_bucket_exists(
        self,
        scope: str,
        tenant_id: Optional[str] = None
    ) -> RegistryBucket:
        """Ensure Registry bucket exists for the given scope and tenant."""
        
        # Check if bucket already exists in database
        query = select(RegistryBucket).where(
            RegistryBucket.scope == scope,
            RegistryBucket.tenant_id == tenant_id
        )
        result = await self.session.execute(query)
        existing_bucket = result.scalar_one_or_none()
        
        if existing_bucket:
            return existing_bucket
        
        # Create bucket in Registry
        bucket_name = f"edi-lens-{scope.lower()}"
        if tenant_id:
            bucket_name += f"-{tenant_id}"
        
        async with NiFiRegistryClient(settings.NIFI_REGISTRY_URL) as registry_client:
            # Check if bucket exists in Registry
            buckets = await registry_client.list_buckets()
            existing_registry_bucket = next(
                (b for b in buckets if b["name"] == bucket_name), None
            )
            
            if existing_registry_bucket:
                bucket_id = UUID(existing_registry_bucket["identifier"])
            else:
                # Create new bucket
                registry_bucket = await registry_client.create_bucket(
                    name=bucket_name,
                    description=f"EDI Lens {scope} templates" + (f" for tenant {tenant_id}" if tenant_id else "")
                )
                bucket_id = UUID(registry_bucket["identifier"])
        
        # Store bucket reference in database
        bucket = RegistryBucket(
            bucket_id=bucket_id,
            name=bucket_name,
            description=f"EDI Lens {scope} templates",
            scope=scope,
            tenant_id=tenant_id
        )
        
        self.session.add(bucket)
        await self.session.commit()
        await self.session.refresh(bucket)
        
        log.info(f"Created bucket {bucket_name} ({bucket_id})")
        return bucket
    
    async def _create_parameter_context(
        self,
        workflow: WorkflowInstance,
        nifi_client: NiFiAPIClient
    ) -> Optional[Dict[str, Any]]:
        """Create parameter context for workflow configuration."""
        if not workflow.configuration:
            return None
        
        # Convert configuration to NiFi parameters
        parameters = []
        for key, value in workflow.configuration.items():
            parameters.append({
                "name": key,
                "value": str(value) if value is not None else "",
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
    
    async def _deploy_from_registry(
        self,
        workflow: WorkflowInstance,
        nifi_client: NiFiAPIClient,
        parent_group_id: str,
        registry_client_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Deploy process group from Registry using version control."""
        
        # For now, we'll create a simple process group and then set up version control
        # In a full implementation, this would use NiFi's version control APIs
        
        # Create process group
        process_group = await nifi_client.create_process_group(
            parent_group_id=parent_group_id,
            name=f"{workflow.name}-{workflow.workflow_id}",
            position={"x": 100, "y": 100}
        )
        
        # TODO: Implement proper Registry-based deployment using NiFi's version control APIs
        # This would involve:
        # 1. Setting up version control on the process group
        # 2. Importing the flow from Registry
        # 3. Configuring parameter contexts
        
        log.info(f"Created process group {process_group['component']['id']} for workflow {workflow.workflow_id}")
        return process_group