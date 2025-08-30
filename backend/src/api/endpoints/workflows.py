"""
API endpoints for workflow management.
"""

import logging
import uuid
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.api.schemas import (
    WorkflowCreate, WorkflowUpdate, WorkflowResponse, WorkflowListResponse,
    WorkflowActionRequest, WorkflowExecutionRequest, WorkflowExecutionResponse,
    WorkflowStatus,
    WorkflowStatusResponse
)
from src.core.auth import require_permission, AuthContext
from src.core.config import settings
from src.core.database import get_db
from src.models.workflow_template import Workflow, WorkflowTemplate
from src.services.workflow_execution_service import WorkflowExecutionService, WorkflowStatusService
from src.services.nifi_workflow_service import NiFiWorkflowService, NiFiWorkflowDeploymentError

log = logging.getLogger(__name__)
router = APIRouter(prefix="/workflows", tags=["workflows"])


@router.get("/", response_model=WorkflowListResponse)
async def list_workflows(
    tenant_id: str,
    template_id: Optional[str] = Query(None, description="Filter by template ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    tags: Optional[List[str]] = Query(None, description="Filter by tags"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    session: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(require_permission("workflow:read"))
):
    """List workflows for a tenant."""
    # Basic implementation, will be expanded
    query = select(Workflow).where(Workflow.tenant_id == tenant_id)
    result = await session.execute(query)
    workflows = result.scalars().all()
    return WorkflowListResponse(
        workflows=[WorkflowResponse.model_validate(wf) for wf in workflows],
        total=len(workflows),
        page=1,
        page_size=len(workflows)
    )

@router.post("/", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
async def create_workflow(
    workflow_data: WorkflowCreate,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(require_permission("workflow:write"))
):
    """Create a new workflow."""
    # Basic implementation, will be expanded
    template_query = select(WorkflowTemplate).where(WorkflowTemplate.template_id == workflow_data.template_id)
    template_result = await session.execute(template_query)
    template = template_result.scalar_one_or_none()

    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    workflow = Workflow(
        tenant_id=auth_context.tenant_id,
        **workflow_data.model_dump()
    )
    session.add(workflow)
    await session.commit()
    await session.refresh(workflow)
    return WorkflowResponse.model_validate(workflow)

@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: UUID,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(require_permission("workflow:read"))
):
    """Get a specific workflow by ID."""
    log.debug(f"[APP-SIDE] get_workflow endpoint: querying for workflow_id={workflow_id}")
    query = select(Workflow).where(Workflow.workflow_id == workflow_id)
    result = await session.execute(query)
    workflow = result.scalar_one_or_none()
    if not workflow or workflow.tenant_id != auth_context.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
    return WorkflowResponse.model_validate(workflow)

@router.put("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: UUID,
    workflow_data: WorkflowUpdate,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(require_permission("workflow:write"))
):
    """Update an existing workflow."""
    # Get the raw database model, not the response schema
    query = select(Workflow).where(Workflow.workflow_id == workflow_id)
    result = await session.execute(query)
    workflow = result.scalar_one_or_none()
    if not workflow or workflow.tenant_id != auth_context.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
    
    update_data = workflow_data.model_dump(exclude_unset=True)
    
    # Only update database columns, not computed properties
    valid_columns = {
        'name', 'description', 'tags', 'configuration', 'status'
    }
    
    for key, value in update_data.items():
        if key in valid_columns:
            setattr(workflow, key, value)
    
    await session.commit()
    await session.refresh(workflow)
    return WorkflowResponse.model_validate(workflow)

@router.delete("/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workflow(
    workflow_id: UUID,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(require_permission("workflow:write"))
):
    """Delete a workflow with complete NiFi resource cleanup."""
    log.info(f"Deleting workflow {workflow_id} for tenant {auth_context.tenant_id}")
    
    # Get the workflow database model directly
    query = select(Workflow).where(Workflow.workflow_id == workflow_id)
    result = await session.execute(query)
    workflow = result.scalar_one_or_none()
    if not workflow or workflow.tenant_id != auth_context.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
    
    # Clean up NiFi resources if workflow is deployed
    if workflow.is_deployed:
        log.info(f"Cleaning up NiFi resources for workflow {workflow_id}")
        from src.nifi.clients.nifi_client import NiFiAPIClient
        from src.core.config import settings
        
        try:
            async with NiFiAPIClient(
                nifi_url=settings.NIFI_URL,
                username=settings.nifi_username,
                password=settings.nifi_password
            ) as nifi_client:
                # Stop the process group first
                if workflow.nifi_process_group_id:
                    try:
                        await nifi_client.stop_process_group(workflow.nifi_process_group_id)
                        log.info(f"Stopped NiFi process group {workflow.nifi_process_group_id}")
                    except Exception as e:
                        log.warning(f"Could not stop process group {workflow.nifi_process_group_id}: {e}")
                
                # Delete the process group
                if workflow.nifi_process_group_id:
                    try:
                        await nifi_client.delete_process_group(workflow.nifi_process_group_id)
                        log.info(f"Deleted NiFi process group {workflow.nifi_process_group_id}")
                    except Exception as e:
                        log.warning(f"Could not delete process group {workflow.nifi_process_group_id}: {e}")
                
                # Delete the parameter context
                if workflow.nifi_parameter_context_id:
                    try:
                        await nifi_client.delete_parameter_context(workflow.nifi_parameter_context_id)
                        log.info(f"Deleted NiFi parameter context {workflow.nifi_parameter_context_id}")
                    except Exception as e:
                        log.warning(f"Could not delete parameter context {workflow.nifi_parameter_context_id}: {e}")
                        
        except Exception as e:
            log.error(f"Error during NiFi resource cleanup for workflow {workflow_id}: {e}")
            # Continue with database deletion even if NiFi cleanup fails
    
    # Delete from database
    await session.delete(workflow)
    await session.commit()
    log.info(f"Successfully deleted workflow {workflow_id}")

@router.post("/{workflow_id}/actions", response_model=WorkflowResponse)
async def control_workflow(
    workflow_id: UUID,
    action: WorkflowActionRequest,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(require_permission("workflow:write"))
):
    """Control a workflow (e.g., pause, resume)."""
    workflow = await get_workflow(workflow_id, session, auth_context)
    
    # For deployed workflows, use NiFi service
    if workflow.is_deployed and workflow.nifi_process_group_id:
        nifi_service = NiFiWorkflowService(session)
        try:
            if action.action == "pause":
                workflow = await nifi_service.stop_workflow(workflow)
            elif action.action == "resume":
                workflow = await nifi_service.start_workflow(workflow)
            elif action.action == "restart":
                # Stop then start
                workflow = await nifi_service.stop_workflow(workflow)
                workflow = await nifi_service.start_workflow(workflow)
            else:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid action")
        except NiFiWorkflowDeploymentError as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    else:
        # For non-deployed workflows, use local control
        if action.action == "pause":
            workflow.status = "PAUSED"
        elif action.action == "resume":
            workflow.status = "ACTIVE"
        elif action.action == "restart":
            workflow.status = "ACTIVE"
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid action")
        
        session.add(workflow)
        await session.commit()
        await session.refresh(workflow)
    
    return WorkflowResponse.model_validate(workflow)


# ==============================================================================
# Workflow Execution Endpoints  
# ==============================================================================

@router.post("/{workflow_id}/process", response_model=WorkflowExecutionResponse)
async def execute_workflow(
    workflow_id: UUID,
    execution_request: WorkflowExecutionRequest,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(require_permission("workflow:execute"))
) -> WorkflowExecutionResponse:
    """Execute workflow with provided EDI content in real-time."""
    log.debug(f"[APP-SIDE] execute_workflow endpoint: processing request for workflow_id={workflow_id}")
    try:
        execution_service = WorkflowExecutionService(session)
        result = await execution_service.execute_workflow(
            workflow_id,
            execution_request,
            auth_context
        )
        
        # Get workflow for response metadata
        workflow = await execution_service._get_workflow(workflow_id, auth_context.tenant_id)
        
        # Convert WorkflowExecutionResult to WorkflowExecutionResponse
        # Extract validation results from outputs
        validation_results = []
        
        # Look for validation results in the outputs
        for output in result.outputs:
            if output.get("name") == "validation_results":
                # If validation results are stored as content, extract them
                content = output.get("content")
                if content and isinstance(content, list):
                    validation_results.extend(content)
                elif content and isinstance(content, str):
                    # Try to parse if it's a JSON string
                    try:
                        import json
                        parsed = json.loads(content)
                        if isinstance(parsed, list):
                            validation_results.extend(parsed)
                    except:
                        pass
        
        return WorkflowExecutionResponse(
            workflow_id=str(result.workflow_id),
            execution_id=result.request_id or str(uuid.uuid4()),
            status=WorkflowStatus.RUNNING if result.valid else WorkflowStatus.FAILED,
            nifi_process_group_id=workflow.nifi_process_group_id,
            nifi_status="RUNNING" if workflow.is_deployed else "NOT_DEPLOYED",
            deployment_method="registry" if workflow.is_deployed else None,
            started_at=result.processed_at,
            stopped_at=result.processed_at,
            message=f"Workflow execution {'completed successfully' if result.valid else 'failed'}",
            monitoring_enabled=execution_request.enable_monitoring,
            health_check={
                "status": "healthy" if result.valid else "unhealthy",
                "processing_time_ms": result.processing_time_ms,
                "outputs_count": len(result.outputs)
            }
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Workflow execution failed: {str(e)}"
        )


@router.get("/{workflow_id}/status", response_model=WorkflowStatusResponse)
async def get_workflow_status(
    workflow_id: UUID,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(require_permission("workflow:read"))
) -> WorkflowStatusResponse:
    """Get detailed workflow status including NiFi deployment information."""
    
    try:
        # Debug logging
        log.debug(f"Getting status for workflow {workflow_id} for user {auth_context.username} in tenant {auth_context.tenant_id}")
        status_service = WorkflowStatusService(session)
        status_data = await status_service.get_detailed_status(
            workflow_id,
            auth_context
        )
        
        return WorkflowStatusResponse(**status_data)
        
    except ValueError as e:
        log.debug(f"ValueError in get_workflow_status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        log.error(f"Exception in get_workflow_status: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get workflow status: {str(e)}"
        )


# ==============================================================================
# Dedicated Workflow Control Endpoints
# ==============================================================================

@router.post("/{workflow_id}/deploy", response_model=WorkflowResponse)
async def deploy_workflow(
    workflow_id: UUID,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(require_permission("workflow:write"))
) -> WorkflowResponse:
    """Deploy a workflow to NiFi."""
    
    # Get the workflow model object directly
    query = select(Workflow).where(Workflow.workflow_id == workflow_id)
    result = await session.execute(query)
    workflow = result.scalar_one_or_none()
    if not workflow or workflow.tenant_id != auth_context.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
    
    # Check if already deployed
    if workflow.is_deployed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Workflow is already deployed"
        )
    
    # Deploy using NiFi service
    nifi_service = NiFiWorkflowService(session)
    try:
        workflow = await nifi_service.deploy_workflow(workflow)
    except NiFiWorkflowDeploymentError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    
    return WorkflowResponse.model_validate(workflow)


@router.post("/{workflow_id}/undeploy", response_model=WorkflowResponse)
async def undeploy_workflow(
    workflow_id: UUID,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(require_permission("workflow:write"))
) -> WorkflowResponse:
    """Undeploy a workflow from NiFi."""
    
    # Get the workflow model object directly
    query = select(Workflow).where(Workflow.workflow_id == workflow_id)
    result = await session.execute(query)
    workflow = result.scalar_one_or_none()
    if not workflow or workflow.tenant_id != auth_context.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
    
    # Check if deployed
    if not workflow.is_deployed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Workflow is not deployed"
        )
    
    # Undeploy using NiFi service
    nifi_service = NiFiWorkflowService(session)
    try:
        workflow = await nifi_service.undeploy_workflow(workflow)
    except NiFiWorkflowDeploymentError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    
    return WorkflowResponse.model_validate(workflow)


@router.post("/{workflow_id}/pause", response_model=WorkflowResponse)
async def pause_workflow(
    workflow_id: UUID,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(require_permission("workflow:write"))
) -> WorkflowResponse:
    """Pause a workflow (stop processing)."""
    
    # Get the workflow model object directly
    query = select(Workflow).where(Workflow.workflow_id == workflow_id)
    result = await session.execute(query)
    workflow = result.scalar_one_or_none()
    if not workflow or workflow.tenant_id != auth_context.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
    
    if workflow.status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot pause workflow in {workflow.status} state"
        )
    
    # For deployed workflows, use NiFi service
    if workflow.is_deployed and workflow.nifi_process_group_id:
        nifi_service = NiFiWorkflowService(session)
        try:
            workflow = await nifi_service.stop_workflow(workflow)
        except NiFiWorkflowDeploymentError as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    else:
        # For non-deployed workflows, use local control
        workflow.status = "PAUSED"
        session.add(workflow)
        await session.commit()
        await session.refresh(workflow)
    
    return WorkflowResponse.model_validate(workflow)


@router.post("/{workflow_id}/resume", response_model=WorkflowResponse)
async def resume_workflow(
    workflow_id: UUID,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(require_permission("workflow:write"))
) -> WorkflowResponse:
    """Resume a paused workflow."""
    
    # Get the workflow model object directly
    query = select(Workflow).where(Workflow.workflow_id == workflow_id)
    result = await session.execute(query)
    workflow = result.scalar_one_or_none()
    if not workflow or workflow.tenant_id != auth_context.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
    
    if workflow.status != "PAUSED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot resume workflow in {workflow.status} state"
        )
    
    # For deployed workflows, use NiFi service
    if workflow.is_deployed and workflow.nifi_process_group_id:
        nifi_service = NiFiWorkflowService(session)
        try:
            workflow = await nifi_service.start_workflow(workflow)
        except NiFiWorkflowDeploymentError as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    else:
        # For non-deployed workflows, use local control
        workflow.status = "ACTIVE"
        session.add(workflow)
        await session.commit()
        await session.refresh(workflow)
    
    return WorkflowResponse.model_validate(workflow)


@router.post("/{workflow_id}/restart", response_model=WorkflowResponse)
async def restart_workflow(
    workflow_id: UUID,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(require_permission("workflow:write"))
) -> WorkflowResponse:
    """Restart a workflow (stop and start)."""
    
    # Get the workflow model object directly
    query = select(Workflow).where(Workflow.workflow_id == workflow_id)
    result = await session.execute(query)
    workflow = result.scalar_one_or_none()
    if not workflow or workflow.tenant_id != auth_context.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
    
    if workflow.status not in ["ACTIVE", "PAUSED", "ERROR"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot restart workflow in {workflow.status} state"
        )
    
    # For deployed workflows, use NiFi service
    if workflow.is_deployed and workflow.nifi_process_group_id:
        nifi_service = NiFiWorkflowService(session)
        try:
            # Stop then start
            workflow = await nifi_service.stop_workflow(workflow)
            workflow = await nifi_service.start_workflow(workflow)
        except NiFiWorkflowDeploymentError as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    else:
        # For non-deployed workflows, use local control
        workflow.status = "ACTIVE"
        session.add(workflow)
        await session.commit()
        await session.refresh(workflow)
    
    return WorkflowResponse.model_validate(workflow)