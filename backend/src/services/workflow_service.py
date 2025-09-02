"""
Workflow Service for managing workflow instances and their lifecycle.

This service handles all workflow operations including CRUD, deployment to NiFi,
lifecycle management, execution, and status monitoring.
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from src.core.config import settings
from src.core.auth import AuthContext
from src.models.workflow_models import Workflow
from src.models.registry_models import RegistryTemplate
from src.services.template_service import TemplateService, TemplateServiceError
from src.services.nifi_service import NiFiService, NiFiServiceError
from src.nifi.clients.nifi_client import NiFiAPIClient
from src.api.schemas import (
    WorkflowExecutionRequest, WorkflowExecutionResponse,
    ValidationFinding, FindingLocation
)

log = logging.getLogger(__name__)


class WorkflowServiceError(Exception):
    """Exception raised for Workflow service errors."""
    pass


class WorkflowExecutionResult:
    """Result of workflow execution."""
    
    def __init__(
        self,
        valid: bool,
        outputs: List[Dict[str, Any]],
        processing_time_ms: int = 0,
        request_id: Optional[str] = None,
        workflow_id: str = "",
        processed_at: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.valid = valid
        self.outputs = outputs
        self.processing_time_ms = processing_time_ms
        self.request_id = request_id
        self.workflow_id = workflow_id
        self.processed_at = processed_at or datetime.utcnow()
        self.metadata = metadata or {}


class WorkflowService:
    """Service for managing workflows and their lifecycle."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.template_service = TemplateService(session)
        self.nifi_service = NiFiService()

    # === Workflow CRUD Operations ===

    async def create_workflow(
        self,
        template_id: UUID,
        name: str,
        tenant_id: str,
        description: Optional[str] = None,
        configuration: Optional[Dict[str, Any]] = None
    ) -> Workflow:
        """Create a new workflow instance from a template."""
        try:
            # Verify template exists
            template = await self.template_service.get_template(template_id)
            if not template:
                raise WorkflowServiceError(f"Template {template_id} not found")
            
            # Create workflow instance
            workflow = Workflow(
                workflow_id=uuid.uuid4(),
                template_id=str(template_id),
                template_version=template.current_version,
                name=name,
                description=description or f"Workflow instance of {template.name}",
                tenant_id=tenant_id,
                configuration=configuration or {},
                status="CREATED"
            )
            
            self.session.add(workflow)
            await self.session.commit()
            await self.session.refresh(workflow)
            
            log.info(f"Created workflow {name} ({workflow.workflow_id}) from template {template_id}")
            return workflow
            
        except Exception as e:
            await self.session.rollback()
            log.error(f"Failed to create workflow {name}: {str(e)}")
            raise WorkflowServiceError(f"Failed to create workflow: {str(e)}")

    async def get_workflow(self, workflow_id: UUID) -> Optional[Workflow]:
        """Get a workflow by ID."""
        query = select(Workflow).where(Workflow.workflow_id == workflow_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_workflows(
        self,
        tenant_id: Optional[str] = None,
        template_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Workflow]:
        """List workflows with optional filtering."""
        query = select(Workflow)
        
        if tenant_id:
            query = query.where(Workflow.tenant_id == tenant_id)
        
        if template_id:
            query = query.where(Workflow.template_id == template_id)
            
        if status:
            query = query.where(Workflow.status == status)
        
        query = query.offset(offset).limit(limit)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def update_workflow(
        self,
        workflow_id: UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
        configuration: Optional[Dict[str, Any]] = None
    ) -> Workflow:
        """Update a workflow instance."""
        try:
            workflow = await self.get_workflow(workflow_id)
            if not workflow:
                raise WorkflowServiceError(f"Workflow {workflow_id} not found")
            
            if workflow.is_deployed:
                raise WorkflowServiceError("Cannot update deployed workflow. Undeploy first.")
            
            if name is not None:
                workflow.name = name
            if description is not None:
                workflow.description = description
            if configuration is not None:
                workflow.configuration = configuration
            
            workflow.updated_at = datetime.utcnow()
            
            await self.session.commit()
            await self.session.refresh(workflow)
            
            return workflow
            
        except Exception as e:
            await self.session.rollback()
            log.error(f"Failed to update workflow {workflow_id}: {str(e)}")
            raise WorkflowServiceError(f"Failed to update workflow: {str(e)}")

    async def delete_workflow(self, workflow_id: UUID) -> bool:
        """Delete a workflow instance."""
        try:
            workflow = await self.get_workflow(workflow_id)
            if not workflow:
                return False
            
            if workflow.is_deployed:
                raise WorkflowServiceError("Cannot delete deployed workflow. Undeploy first.")
            
            await self.session.delete(workflow)
            await self.session.commit()
            
            log.info(f"Deleted workflow {workflow_id}")
            return True
            
        except Exception as e:
            await self.session.rollback()
            log.error(f"Failed to delete workflow {workflow_id}: {str(e)}")
            raise WorkflowServiceError(f"Failed to delete workflow: {str(e)}")

    # === Workflow Lifecycle Management ===

    async def deploy_workflow(self, workflow_id: UUID) -> Workflow:
        """Deploy a workflow instance to NiFi using Registry version control."""
        try:
            workflow = await self.get_workflow(workflow_id)
            if not workflow:
                raise WorkflowServiceError(f"Workflow {workflow_id} not found")

            if workflow.is_deployed:
                raise WorkflowServiceError(f"Workflow {workflow_id} is already deployed")

            # Get template info
            template = await self.template_service.get_template(UUID(workflow.template_id))
            if not template:
                raise WorkflowServiceError(f"Template {workflow.template_id} not found")

            async with NiFiAPIClient(
                settings.NIFI_URL,
                username=settings.NIFI_USERNAME,
                password=settings.NIFI_PASSWORD
            ) as nifi_client:
                root_pg = await nifi_client.get_process_group("root")
                root_pg_id = root_pg["component"]["id"]

                # Create parameter context for workflow configuration
                param_context = await self.nifi_service.create_parameter_context(
                    workflow, nifi_client
                )

                # Deploy process group from Registry
                process_group = await self.nifi_service.deploy_from_registry(
                    nifi_client=nifi_client,
                    parent_group_id=root_pg_id,
                    bucket_id=str(template.bucket.bucket_id),
                    flow_id=str(template.registry_flow_id),
                    process_group_name=f"{workflow.name}-{workflow.workflow_id}",
                    position={"x": 100, "y": 100}
                )

                # Update workflow with NiFi IDs
                workflow.nifi_process_group_id = process_group["id"]
                workflow.nifi_parameter_context_id = param_context["id"]
                workflow.status = "ACTIVE"
                workflow.deployed_at = datetime.utcnow()

            await self.session.commit()
            await self.session.refresh(workflow)

            log.info(f"Deployed workflow {workflow_id} to NiFi")
            return workflow

        except Exception as e:
            await self.session.rollback()
            log.error(f"Failed to deploy workflow {workflow_id}: {str(e)}")
            raise WorkflowServiceError(f"Failed to deploy workflow: {str(e)}")

    async def undeploy_workflow(self, workflow_id: UUID) -> Workflow:
        """Undeploy a workflow from NiFi."""
        try:
            workflow = await self.get_workflow(workflow_id)
            if not workflow:
                raise WorkflowServiceError(f"Workflow {workflow_id} not found")

            if not workflow.is_deployed:
                raise WorkflowServiceError(f"Workflow {workflow_id} is not deployed")

            async with NiFiAPIClient(
                settings.NIFI_URL,
                username=settings.NIFI_USERNAME,
                password=settings.NIFI_PASSWORD
            ) as nifi_client:
                # Stop process group first
                if workflow.nifi_process_group_id:
                    await self.nifi_service.stop_process_group(
                        workflow.nifi_process_group_id, nifi_client
                    )
                    
                    # Delete process group
                    await self.nifi_service.delete_process_group(
                        workflow.nifi_process_group_id, nifi_client
                    )

                # Delete parameter context
                if workflow.nifi_parameter_context_id:
                    await self.nifi_service.delete_parameter_context(
                        workflow.nifi_parameter_context_id, nifi_client
                    )

            # Update workflow with NiFi IDs
            workflow.nifi_process_group_id = None
            workflow.nifi_parameter_context_id = None
            workflow.status = "DELETED"
            workflow.undeployed_at = datetime.utcnow()

            await self.session.commit()
            await self.session.refresh(workflow)

            log.info(f"Undeployed workflow {workflow_id} from NiFi")
            return workflow

        except Exception as e:
            await self.session.rollback()
            log.error(f"Failed to undeploy workflow {workflow_id}: {str(e)}")
            raise WorkflowServiceError(f"Failed to undeploy workflow: {str(e)}")

    async def control_workflow(self, workflow_id: UUID, action: str) -> Workflow:
        """Control workflow lifecycle (start, stop, pause, resume, restart)."""
        try:
            workflow = await self.get_workflow(workflow_id)
            if not workflow:
                raise WorkflowServiceError(f"Workflow {workflow_id} not found")

            if not workflow.is_deployed or not workflow.nifi_process_group_id:
                raise WorkflowServiceError(f"Workflow {workflow_id} is not deployed")

            async with NiFiAPIClient(
                settings.NIFI_URL,
                username=settings.NIFI_USERNAME,
                password=settings.NIFI_PASSWORD
            ) as nifi_client:
                if action in ["start", "resume"]:
                    await self.nifi_service.start_process_group(
                        workflow.nifi_process_group_id, nifi_client
                    )
                    workflow.status = "ACTIVE"
                    
                elif action in ["stop", "pause"]:
                    await self.nifi_service.stop_process_group(
                        workflow.nifi_process_group_id, nifi_client
                    )
                    workflow.status = "PAUSED"
                    
                elif action == "restart":
                    # Stop then start
                    await self.nifi_service.stop_process_group(
                        workflow.nifi_process_group_id, nifi_client
                    )
                    await self.nifi_service.start_process_group(
                        workflow.nifi_process_group_id, nifi_client
                    )
                    workflow.status = "ACTIVE"
                    
                else:
                    raise WorkflowServiceError(f"Unknown action: {action}")

            await self.session.commit()
            await self.session.refresh(workflow)

            log.info(f"Applied {action} to workflow {workflow_id}")
            return workflow

        except Exception as e:
            await self.session.rollback()
            log.error(f"Failed to {action} workflow {workflow_id}: {str(e)}")
            raise WorkflowServiceError(f"Failed to {action} workflow: {str(e)}")

    # === Workflow Execution ===

    async def execute_workflow(
        self, 
        workflow_id: str,
        execution_request: WorkflowExecutionRequest,
        auth_context: AuthContext
    ) -> WorkflowExecutionResult:
        """Execute workflow with content."""
        start_time = datetime.utcnow()
        
        try:
            # Load workflow and template
            workflow = await self._get_workflow(workflow_id, auth_context.tenant_id)
            template = await self.template_service.get_template(UUID(workflow.template_id))
            
            if not template:
                raise WorkflowServiceError(f"Template {workflow.template_id} not found")
            
            # Validate workflow is ready for execution
            await self._validate_workflow_readiness(workflow, template, auth_context)
            
            # Process content through deployed NiFi workflow
            if workflow.is_deployed and workflow.nifi_process_group_id:
                processing_result = await self._process_content_nifi(
                    workflow, template, execution_request
                )
            else:
                raise WorkflowServiceError("Workflow must be deployed before execution")
            
            # Calculate processing time
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            # Return execution result
            return WorkflowExecutionResult(
                valid=processing_result["valid"],
                outputs=processing_result["outputs"],
                processing_time_ms=int(processing_time),
                request_id=execution_request.request_id,
                workflow_id=workflow_id,
                processed_at=datetime.utcnow(),
                metadata=processing_result.get("metadata", {})
            )

        except Exception as e:
            log.error(f"Failed to execute workflow {workflow_id}: {str(e)}")
            raise WorkflowServiceError(f"Failed to execute workflow: {str(e)}")

    async def _process_content_nifi(
        self,
        workflow: Workflow,
        template: RegistryTemplate,
        execution_request: WorkflowExecutionRequest
    ) -> Dict[str, Any]:
        """Process content through deployed NiFi workflow."""
        try:
            async with NiFiAPIClient(
                settings.NIFI_URL,
                username=settings.NIFI_USERNAME,
                password=settings.NIFI_PASSWORD
            ) as nifi_client:
                # This would implement actual NiFi content processing
                # For now, we'll return a structured response indicating NiFi processing
                return {
                    "valid": True,
                    "outputs": [
                        {
                            "type": "processing_result",
                            "content": f"Processed through NiFi workflow {workflow.nifi_process_group_id}",
                            "format": execution_request.file_type
                        }
                    ],
                    "metadata": {
                        "processing_method": "nifi",
                        "workflow_id": str(workflow.workflow_id),
                        "template_id": workflow.template_id,
                        "nifi_process_group_id": workflow.nifi_process_group_id
                    }
                }
                
        except Exception as e:
            log.error(f"NiFi processing failed for workflow {workflow.workflow_id}: {str(e)}")
            raise WorkflowServiceError(f"NiFi processing failed: {str(e)}")

    # === Workflow Status ===

    async def get_workflow_status(
        self,
        workflow_id: str,
        auth_context: AuthContext
    ) -> Dict[str, Any]:
        """Get comprehensive workflow status."""
        try:
            workflow = await self._get_workflow(workflow_id, auth_context.tenant_id)
            
            base_status = {
                "workflow_id": str(workflow.workflow_id),
                "status": workflow.status,
                "is_deployed": workflow.is_deployed,
                "template_id": workflow.template_id,
                "name": workflow.name,
                "created_at": workflow.created_at.isoformat() if workflow.created_at else None,
                "deployed_at": workflow.deployed_at.isoformat() if workflow.deployed_at else None,
                "updated_at": workflow.updated_at.isoformat() if workflow.updated_at else None,
            }

            if workflow.is_deployed and workflow.nifi_process_group_id:
                try:
                    nifi_status = await self.nifi_service.get_process_group_status(
                        workflow.nifi_process_group_id
                    )
                    base_status.update(nifi_status)
                except NiFiServiceError as e:
                    log.error(f"Could not get NiFi status for workflow {workflow_id}: {e}")
                    base_status["nifi_status"] = "UNKNOWN"
                    base_status["nifi_error"] = str(e)

            return base_status

        except Exception as e:
            log.error(f"Failed to get status for workflow {workflow_id}: {str(e)}")
            raise WorkflowServiceError(f"Failed to get workflow status: {str(e)}")

    # === Private Helper Methods ===

    async def _get_workflow(self, workflow_id: str, tenant_id: str) -> Workflow:
        """Get workflow with tenant validation."""
        query = select(Workflow).where(
            Workflow.workflow_id == UUID(workflow_id),
            Workflow.tenant_id == tenant_id
        )
        result = await self.session.execute(query)
        workflow = result.scalar_one_or_none()

        if not workflow:
            raise WorkflowServiceError(f"Workflow {workflow_id} not found or access denied")

        return workflow

    async def _validate_workflow_readiness(
        self, 
        workflow: Workflow, 
        template: RegistryTemplate,
        auth_context: AuthContext
    ):
        """Validate that workflow is ready for execution."""
        if workflow.status not in ["ACTIVE", "PAUSED"]:
            raise WorkflowServiceError(f"Workflow status '{workflow.status}' not ready for execution")
        
        if not workflow.is_deployed:
            raise WorkflowServiceError("Workflow must be deployed before execution")
        
        if not workflow.nifi_process_group_id:
            raise WorkflowServiceError("Workflow missing NiFi process group ID")
        
        # Validate tenant access
        if workflow.tenant_id != auth_context.tenant_id:
            raise WorkflowServiceError("Access denied to workflow")