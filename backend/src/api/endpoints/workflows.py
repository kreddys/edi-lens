"""
API endpoints for workflow management.
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.api.schemas import (
    WorkflowCreate, WorkflowUpdate, WorkflowResponse, WorkflowListResponse,
    WorkflowActionRequest
)
from src.core.auth import require_permission, AuthContext
from src.core.database import get_db
from src.models.workflow_template import Workflow, WorkflowTemplate

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
    workflow = await get_workflow(workflow_id, session, auth_context)
    update_data = workflow_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(workflow, key, value)
    session.add(workflow)
    await session.commit()
    await session.refresh(workflow)
    return WorkflowResponse.model_validate(workflow)

@router.delete("/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workflow(
    workflow_id: UUID,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(require_permission("workflow:write"))
):
    """Delete a workflow."""
    workflow = await get_workflow(workflow_id, session, auth_context)
    await session.delete(workflow)
    await session.commit()

@router.post("/{workflow_id}/actions", response_model=WorkflowResponse)
async def control_workflow(
    workflow_id: UUID,
    action: WorkflowActionRequest,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(require_permission("workflow:write"))
):
    """Control a workflow (e.g., pause, resume)."""
    workflow = await get_workflow(workflow_id, session, auth_context)
    # This is a placeholder for the actual action logic
    if action.action == "pause":
        workflow.status = "PAUSED"
    elif action.action == "resume":
        workflow.status = "ACTIVE"
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid action")
    
    session.add(workflow)
    await session.commit()
    await session.refresh(workflow)
    return WorkflowResponse.model_validate(workflow)
