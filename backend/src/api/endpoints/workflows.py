"""
API endpoints for workflow management.
"""

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth import require_permission, AuthContext
from src.core.database import get_db
from src.services.workflow_service import WorkflowService, WorkflowServiceError
from src.api.schemas import (
    WorkflowResponse, WorkflowCreateRequest, RegistryTemplateResponse,
    WorkflowActionRequest, WorkflowStatusResponse, WorkflowExecutionRequest, WorkflowExecutionResponse
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/workflows", tags=["Workflows"])


def create_workflow_response(workflow, include_template=False) -> WorkflowResponse:
    """Helper function to create WorkflowResponse manually to avoid SQLAlchemy serialization issues."""
    # Create the response model manually to avoid accessing relationships unnecessarily
    workflow_dict = {
        "workflow_id": workflow.workflow_id,
        "name": workflow.name,
        "description": workflow.description,
        "tenant_id": workflow.tenant_id,
        "template_id": workflow.template_id,
        "template_version": workflow.template_version,
        "configuration": workflow.configuration,
        "nifi_process_group_id": workflow.nifi_process_group_id,
        "nifi_parameter_context_id": workflow.nifi_parameter_context_id,
        "nifi_registry_client_id": workflow.nifi_registry_client_id,
        "version_control_info": workflow.version_control_info,
        "status": workflow.status,
        "is_deployed": workflow.is_deployed,  # Add the is_deployed field
        "created_by": workflow.created_by,
        "created_at": workflow.created_at,
        "updated_at": workflow.updated_at,
        "deployed_at": workflow.deployed_at,
        "last_started_at": workflow.last_started_at,
        "last_stopped_at": workflow.last_stopped_at,
        "template": None
    }
    
    # Handle template relationship if needed
    if include_template and hasattr(workflow, 'template') and workflow.template is not None:
        try:
            # Create template response manually to avoid async relationship issues
            template_dict = {
                "template_id": workflow.template.template_id,
                "bucket_id": workflow.template.bucket_id,
                "current_version": workflow.template.current_version,
                "name": workflow.template.name,
                "description": workflow.template.description,
                "scope": workflow.template.scope,
                "tenant_id": workflow.template.tenant_id,
                "status": workflow.template.status,
                "is_featured": workflow.template.is_featured,
                "usage_count": workflow.template.usage_count,
                "created_by": workflow.template.created_by,
                "created_at": workflow.template.created_at,
                "updated_at": workflow.template.updated_at,
                "deprecated_at": workflow.template.deprecated_at
            }
            workflow_dict["template"] = RegistryTemplateResponse(**template_dict)
        except Exception as e:
            log.warning(f"Could not serialize template for workflow {workflow.workflow_id}: {e}")

    return WorkflowResponse(**workflow_dict)


@router.get("/", response_model=List[WorkflowResponse])
async def list_workflows(
    template_id: Optional[str] = None,
    status: Optional[str] = None,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(require_permission("workflow:read"))
):
    """List workflows accessible to the current user."""
    try:
        workflow_service = WorkflowService(session)
        workflows = await workflow_service.list_workflows(
            template_id=template_id,
            status=status,
            tenant_id=auth_context.tenant_id
        )
        return [create_workflow_response(wf, include_template=True) for wf in workflows]
    except Exception as e:
        log.error(f"Error listing workflows: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list workflows")


@router.post("/", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
async def create_workflow(
    workflow_data: WorkflowCreateRequest,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(require_permission("workflow:write"))
):
    """Create a new workflow instance from a template."""
    try:
        workflow_service = WorkflowService(session)
        workflow = await workflow_service.create_workflow(
            template_id=workflow_data.template_id,
            name=workflow_data.name,
            tenant_id=auth_context.tenant_id,
            configuration=workflow_data.configuration,
            description=workflow_data.description
        )
        return create_workflow_response(workflow)
    except WorkflowServiceError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    except Exception as e:
        log.error(f"Unexpected error creating workflow: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create workflow")


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: UUID,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(require_permission("workflow:read"))
):
    """Get workflow by ID."""
    try:
        workflow_service = WorkflowService(session)
        workflow = await workflow_service.get_workflow(workflow_id)
        if not workflow or workflow.tenant_id != auth_context.tenant_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
        return create_workflow_response(workflow, include_template=True)
    except Exception as e:
        log.error(f"Error getting workflow {workflow_id}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get workflow")


@router.post("/{workflow_id}/deploy", response_model=WorkflowResponse)
async def deploy_workflow(
    workflow_id: UUID,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(require_permission("workflow:write"))
):
    """Deploy a workflow to NiFi."""
    try:
        workflow_service = WorkflowService(session)
        workflow = await workflow_service.deploy_workflow(workflow_id)
        return create_workflow_response(workflow)
    except WorkflowServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        log.error(f"Error deploying workflow {workflow_id}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to deploy workflow")


@router.post("/{workflow_id}/actions", response_model=WorkflowResponse)
async def control_workflow(
    workflow_id: UUID,
    action: WorkflowActionRequest,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(require_permission("workflow:write"))
):
    """Control a workflow (pause, resume, restart)."""
    try:
        workflow_service = WorkflowService(session)
        workflow = await workflow_service.control_workflow(workflow_id, action.action)
        return create_workflow_response(workflow)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        log.error(f"Error controlling workflow {workflow_id}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to control workflow")


@router.get("/{workflow_id}/status", response_model=WorkflowStatusResponse)
async def get_workflow_status(
    workflow_id: UUID,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(require_permission("workflow:read"))
):
    """Get detailed status of a workflow."""
    try:
        workflow_service = WorkflowService(session)
        status_info = await workflow_service.get_workflow_status(str(workflow_id), auth_context)
        return WorkflowStatusResponse(**status_info)
    except Exception as e:
        log.error(f"Error getting workflow status {workflow_id}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get workflow status")


@router.post("/{workflow_id}/execute", response_model=WorkflowExecutionResponse)
async def execute_workflow(
    workflow_id: UUID,
    execution_request: WorkflowExecutionRequest,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(require_permission("workflow:execute"))
):
    """Execute a workflow with provided content."""
    try:
        workflow_service = WorkflowService(session)
        result = await workflow_service.execute_workflow(str(workflow_id), execution_request, auth_context)
        return WorkflowExecutionResponse.from_orm(result)
    except Exception as e:
        log.error(f"Error executing workflow {workflow_id}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to execute workflow")


@router.post("/{workflow_id}/stop", response_model=WorkflowResponse)
async def stop_workflow(
    workflow_id: UUID,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(require_permission("workflow:write"))
):
    """Stop a running workflow."""
    try:
        workflow_service = WorkflowService(session)
        workflow = await workflow_service.stop_workflow(workflow_id)
        return create_workflow_response(workflow)
    except Exception as e:
        log.error(f"Error stopping workflow {workflow_id}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to stop workflow")


@router.delete("/{workflow_id}/deployment")
async def undeploy_workflow(
    workflow_id: UUID,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(require_permission("workflow:write"))
):
    """Undeploy a workflow from NiFi."""
    try:
        workflow_service = WorkflowService(session)
        workflow = await workflow_service.undeploy_workflow(workflow_id)
        return {
            "workflow_id": str(workflow_id),
            "message": "Workflow undeployed successfully",
            "status": workflow.status
        }
    except Exception as e:
        log.error(f"Error undeploying workflow {workflow_id}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to undeploy workflow")
