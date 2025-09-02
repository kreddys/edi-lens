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
import json

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
                # Ensure Registry client is set up in NiFi
                await self.setup_registry_integration()
                
                # Deploy from Registry
                process_group = await self.deploy_from_registry(
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
    
    # === Registry Integration Methods ===
    
    async def setup_registry_integration(self) -> Dict[str, Any]:
        """
        Set up NiFi Registry integration by registering the Registry client with NiFi.
        
        Returns:
            Registry client information from NiFi
        """
        try:
            async with NiFiAPIClient(
                settings.NIFI_URL,
                username=settings.NIFI_USERNAME,
                password=settings.NIFI_PASSWORD
            ) as nifi_client:
                
                # Check if registry client already exists
                existing_clients = await self._list_registry_clients(nifi_client)
                registry_client = None
                
                for client in existing_clients:
                    component = client.get("component", {})
                    # Check various possible fields where the URL might be stored
                    if (component.get("uri") == settings.NIFI_REGISTRY_URL or
                        component.get("properties", {}).get("url") == settings.NIFI_REGISTRY_URL or
                        component.get("properties", {}).get("URL") == settings.NIFI_REGISTRY_URL or
                        "EDI Lens Registry" in component.get("name", "")):
                        registry_client = client
                        break
                
                if registry_client:
                    log.info(f"Registry client already exists: {registry_client['component']['name']}")
                    return registry_client
                
                # Create new registry client
                registry_client = await self._create_registry_client(nifi_client)
                log.info(f"Created registry client: {registry_client['component']['name']}")
                return registry_client
                
        except Exception as e:
            log.error(f"Failed to setup registry integration: {str(e)}")
            raise RegistryServiceError(f"Failed to setup registry integration: {str(e)}")
    
    async def deploy_from_registry(
        self,
        nifi_client: NiFiAPIClient,
        parent_group_id: str,
        bucket_id: str,
        flow_id: str,
        flow_version: int,
        process_group_name: str,
        position: Dict[str, int] = None
    ) -> Dict[str, Any]:
        """
        Deploy a process group from Registry using NiFi's version control.
        
        Args:
            nifi_client: NiFi API client
            parent_group_id: Parent process group ID
            bucket_id: Registry bucket ID
            flow_id: Registry flow ID
            flow_version: Flow version to deploy
            process_group_name: Name for the process group
            position: Position for the process group
            
        Returns:
            Created process group information
        """
        try:
            # 1. Get registry client ID
            registry_clients = await self._list_registry_clients(nifi_client)
            registry_client = None
            
            for client in registry_clients:
                component = client.get("component", {})
                name = component.get("name", "")
                
                # Check URI in various locations
                uri = (component.get("uri") or 
                      component.get("url") or
                      component.get("properties", {}).get("url") or
                      component.get("properties", {}).get("URL"))
                        
                # Match by URI or by name
                if (uri == settings.NIFI_REGISTRY_URL or 
                    "EDI Lens Registry" in name):
                    registry_client = client
                    log.info(f"Found matching registry client: {name} with URI: {uri}")
                    break
            
            if not registry_client:
                raise ValueError("Registry client not found. Run setup_registry_integration() first.")
            
            registry_client_id = registry_client["component"]["id"]
            
            # 2. Get the flow snapshot from Registry
            async with NiFiRegistryClient(settings.NIFI_REGISTRY_URL) as registry_client:
                flow_snapshot = await registry_client.get_flow_version(
                    bucket_id=bucket_id,
                    flow_id=flow_id,
                    version=flow_version
                )
            
            log.debug(f"Retrieved flow snapshot with {len(flow_snapshot.get('flowContents', {}).get('processors', []))} processors")
            
            # 3. Try direct import using the process-groups/import endpoint
            import_data = {
                "disconnectedNodeAcknowledged": False,
                "groupName": process_group_name,
                "positionDTO": position or {"x": 100, "y": 100},
                "revisionDTO": {"version": 0},
                "flowSnapshot": flow_snapshot
            }
            
            log.debug(f"Attempting direct import from Registry")
            
            import_response = await nifi_client.session.post(
                f"{nifi_client.nifi_url}/process-groups/{parent_group_id}/process-groups/import",
                json=import_data
            )
            
            log.debug(f"Import response status: {import_response.status}")
            
            if import_response.status == 200:
                # Success! Process group imported with content
                process_group = await import_response.json()
                log.info(f"Successfully imported process group {process_group['component']['id']} with content from Registry")
                
                # Try to set up version control on the imported process group
                await self._setup_version_control(
                    nifi_client, process_group, registry_client_id, 
                    bucket_id, flow_id, flow_version
                )
                
                return process_group
            else:
                # Fallback: Create empty process group and populate manually
                log.warning(f"Direct import failed ({import_response.status}), using fallback approach")
                
                # Create empty process group
                pg_data = {
                    "revision": {"version": 0},
                    "component": {
                        "name": process_group_name,
                        "position": position or {"x": 100, "y": 100}
                    }
                }
                
                response = await nifi_client.session.post(
                    f"{nifi_client.nifi_url}/process-groups/{parent_group_id}/process-groups",
                    json=pg_data
                )
                response.raise_for_status()
                process_group = await response.json()
                
                log.info(f"Created empty process group {process_group['component']['id']}")
                
                # Populate with Registry content
                await self._populate_process_group_from_registry(
                    nifi_client, process_group, flow_snapshot
                )
                
                # Try to set up version control
                await self._setup_version_control(
                    nifi_client, process_group, registry_client_id, 
                    bucket_id, flow_id, flow_version
                )
                
                return process_group
            
        except Exception as e:
            log.error(f"Failed to deploy from Registry: {str(e)}")
            raise RegistryServiceError(f"Failed to deploy from Registry: {str(e)}")
    
    async def change_flow_version(
        self,
        nifi_client: NiFiAPIClient,
        process_group_id: str,
        new_version: int
    ) -> Dict[str, Any]:
        """
        Change the version of a version-controlled process group.
        
        Args:
            nifi_client: NiFi API client
            process_group_id: Process group ID
            new_version: New version to deploy
            
        Returns:
            Updated process group information
        """
        try:
            # Get current process group info
            pg_info = await nifi_client.get_process_group(process_group_id)
            version_control_info = pg_info["component"].get("versionControlInformation")
            
            if not version_control_info:
                raise ValueError(f"Process group {process_group_id} is not version controlled")
            
            # Get the flow snapshot for the new version
            async with NiFiRegistryClient(settings.NIFI_REGISTRY_URL) as registry_client:
                flow_snapshot = await registry_client.get_flow_version(
                    bucket_id=version_control_info["bucketId"],
                    flow_id=version_control_info["flowId"],
                    version=new_version
                )
            
            # Update version using PUT endpoint
            update_data = {
                "processGroupRevision": pg_info["revision"],
                "versionedFlowSnapshot": flow_snapshot,
                "disconnectedNodeAcknowledged": False
            }
            
            response = await nifi_client.session.put(
                f"{nifi_client.nifi_url}/versions/process-groups/{process_group_id}",
                json=update_data
            )
            response.raise_for_status()
            result = await response.json()
            
            log.info(f"Changed process group {process_group_id} to version {new_version}")
            return result
            
        except Exception as e:
            log.error(f"Failed to change flow version: {str(e)}")
            raise RegistryServiceError(f"Failed to change flow version: {str(e)}")
    
    async def _setup_version_control(
        self,
        nifi_client: NiFiAPIClient,
        process_group: Dict[str, Any],
        registry_client_id: str,
        bucket_id: str,
        flow_id: str,
        flow_version: int
    ) -> bool:
        """Set up version control on a process group."""
        try:
            start_version_control_data = {
                "processGroupRevision": process_group["revision"],
                "versionControlInformation": {
                    "registryId": registry_client_id,
                    "bucketId": bucket_id,
                    "flowId": flow_id,
                    "version": flow_version,
                    "storageLocation": bucket_id
                },
                "disconnectedNodeAcknowledged": False
            }
            
            log.debug(f"Setting up version control on process group {process_group['component']['id']}")
            
            vc_response = await nifi_client.session.post(
                f"{nifi_client.nifi_url}/versions/process-groups/{process_group['component']['id']}",
                json=start_version_control_data
            )
            
            log.debug(f"Version control response status: {vc_response.status}")
            
            if vc_response.status == 200:
                log.info(f"Successfully set up version control for process group {process_group['component']['id']}")
                return True
            else:
                vc_response_text = await vc_response.text()
                log.warning(f"Version control setup returned {vc_response.status}: {vc_response_text}")
                return False
                
        except Exception as e:
            log.warning(f"Failed to set up version control: {str(e)}")
            return False
    
    async def _populate_process_group_from_registry(
        self,
        nifi_client: NiFiAPIClient,
        process_group: Dict[str, Any],
        flow_snapshot: Dict[str, Any]
    ) -> None:
        """Manually populate a process group with content from a Registry flow snapshot."""
        try:
            flow_contents = flow_snapshot.get("flowContents", {})
            pg_id = process_group["component"]["id"]
            
            log.info(f"Manually populating process group {pg_id} with Registry content")
            
            # Create processors from the flow
            processors = flow_contents.get("processors", [])
            processor_id_map = {}  # Map Registry IDs to NiFi IDs
            
            for processor in processors:
                processor_data = {
                    "revision": {"version": 0},
                    "component": {
                        "name": processor.get("name", "Unknown Processor"),
                        "type": processor.get("type", "org.apache.nifi.processors.standard.LogMessage"),
                        "position": processor.get("position", {"x": 100, "y": 100}),
                        "config": {
                            "properties": processor.get("properties", {}),
                            "schedulingStrategy": processor.get("schedulingStrategy", "TIMER_DRIVEN"),
                            "schedulingPeriod": processor.get("schedulingPeriod", "1 sec"),
                            "concurrentlySchedulableTaskCount": processor.get("concurrentlySchedulableTaskCount", 1),
                            "bulletinLevel": processor.get("bulletinLevel", "WARN")
                        }
                    }
                }
                
                try:
                    response = await nifi_client.session.post(
                        f"{nifi_client.nifi_url}/process-groups/{pg_id}/processors",
                        json=processor_data
                    )
                    if response.status == 201:
                        created_processor = await response.json()
                        processor_id_map[processor.get("identifier")] = created_processor["component"]["id"]
                        log.debug(f"Created processor: {created_processor['component']['name']}")
                    else:
                        log.warning(f"Failed to create processor {processor.get('name')}: {response.status}")
                except Exception as proc_error:
                    log.warning(f"Error creating processor {processor.get('name')}: {str(proc_error)}")
            
            # Create connections from the flow
            connections = flow_contents.get("connections", [])
            for connection in connections:
                try:
                    source_id = processor_id_map.get(connection.get("source", {}).get("id"))
                    dest_id = processor_id_map.get(connection.get("destination", {}).get("id"))
                    
                    if source_id and dest_id:
                        connection_data = {
                            "revision": {"version": 0},
                            "component": {
                                "name": connection.get("name", ""),
                                "source": {
                                    "id": source_id,
                                    "groupId": pg_id,
                                    "type": "PROCESSOR"
                                },
                                "destination": {
                                    "id": dest_id,
                                    "groupId": pg_id,
                                    "type": "PROCESSOR"
                                },
                                "selectedRelationships": connection.get("selectedRelationships", ["success"])
                            }
                        }
                        
                        response = await nifi_client.session.post(
                            f"{nifi_client.nifi_url}/process-groups/{pg_id}/connections",
                            json=connection_data
                        )
                        if response.status == 201:
                            log.debug(f"Created connection from {source_id} to {dest_id}")
                        else:
                            log.warning(f"Failed to create connection: {response.status}")
                    else:
                        log.warning(f"Could not map connection source/destination IDs")
                        
                except Exception as conn_error:
                    log.warning(f"Error creating connection: {str(conn_error)}")
            
            log.info(f"Populated process group with {len(processors)} processors and {len(connections)} connections")
            
        except Exception as e:
            log.warning(f"Failed to manually populate process group: {str(e)}")
    
    async def _list_registry_clients(self, nifi_client: NiFiAPIClient) -> list:
        """List all registry clients in NiFi."""
        response = await nifi_client.session.get(f"{nifi_client.nifi_url}/controller/registry-clients")
        response.raise_for_status()
        data = await response.json()
        return data.get("registries", [])
    
    async def _create_registry_client(self, nifi_client: NiFiAPIClient) -> Dict[str, Any]:
        """Create a new registry client in NiFi."""
        registry_data = {
            "revision": {"version": 0},
            "component": {
                "name": "EDI Lens Registry",
                "type": "org.apache.nifi.registry.flow.NifiRegistryFlowRegistryClient",
                "properties": {
                    "url": settings.NIFI_REGISTRY_URL
                },
                "description": "EDI Lens NiFi Registry for workflow templates"
            }
        }
        
        response = await nifi_client.session.post(
            f"{nifi_client.nifi_url}/controller/registry-clients",
            json=registry_data
        )
        response.raise_for_status()
        return await response.json()