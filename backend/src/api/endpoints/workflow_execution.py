"""
Workflow Execution API endpoints.

This module provides REST API endpoints for executing and managing workflows,
including triggering batch processing, monitoring execution status, and managing
workflow lifecycle operations.
"""

import logging
from typing import Dict, Any, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.core.database import get_db, AsyncSessionLocal
from src.core.auth import get_current_user, AuthContext, require_permission
from src.models.workflow_template import Workflow
from src.services.nifi_workflow_service import NiFiWorkflowService, NiFiWorkflowDeploymentError
from src.api.schemas import WorkflowExecutionRequest, WorkflowExecutionResponse, WorkflowStatus
from src.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workflows", tags=["workflow-execution"])


@router.post("/{workflow_id}/execute", response_model=WorkflowExecutionResponse)
async def execute_workflow(
    workflow_id: str,
    execution_request: WorkflowExecutionRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(require_permission("workflow:execute"))
):
    """
    Execute a workflow by deploying it to NiFi and starting it.
    
    This endpoint:
    1. Validates the workflow exists and user has access
    2. Deploys the workflow to NiFi if not already deployed
    3. Starts the workflow execution
    4. Returns execution status and monitoring information
    """
    try:
        # Get workflow from database
        workflow = await _get_workflow(session, workflow_id, auth_context.tenant_id)
        
        # Initialize NiFi workflow service
        nifi_service = NiFiWorkflowService(session)
        
        # Deploy workflow if not already deployed
        if not workflow.nifi_process_group_id:
            logger.info(f"Deploying workflow {workflow_id} to NiFi")
            workflow = await nifi_service.deploy_workflow(workflow)
        
        # Start the workflow
        logger.info(f"Starting workflow {workflow_id}")
        workflow = await nifi_service.start_workflow(workflow)
        
        # Get current status
        status_info = await nifi_service.get_workflow_status(workflow)
        
        # Schedule background monitoring if requested
        if execution_request.enable_monitoring:
            background_tasks.add_task(
                _monitor_workflow_execution,
                workflow_id,
                auth_context.tenant_id,
                execution_request.monitoring_interval_seconds
            )
        
        return WorkflowExecutionResponse(
            workflow_id=workflow_id,
            execution_id=execution_request.request_id or str(workflow.workflow_id),
            status=WorkflowStatus.RUNNING,
            nifi_process_group_id=workflow.nifi_process_group_id,
            nifi_status=status_info.get("nifi_status"),
            deployment_method=workflow.deployment_method,
            started_at=workflow.updated_at,
            message="Workflow started successfully",
            monitoring_enabled=execution_request.enable_monitoring
        )
        
    except NiFiWorkflowDeploymentError as e:
        logger.error(f"Failed to deploy workflow {workflow_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Workflow deployment failed: {str(e)}")
    except Exception as e:
        logger.error(f"Failed to execute workflow {workflow_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Workflow execution failed: {str(e)}")


@router.post("/{workflow_id}/stop", response_model=WorkflowExecutionResponse)
async def stop_workflow(
    workflow_id: str,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(require_permission("workflow:execute"))
):
    """Stop a running workflow."""
    try:
        # Get workflow from database
        workflow = await _get_workflow(session, workflow_id, auth_context.tenant_id)
        
        if not workflow.nifi_process_group_id:
            raise HTTPException(status_code=400, detail="Workflow is not deployed to NiFi")
        
        # Initialize NiFi workflow service and stop workflow
        nifi_service = NiFiWorkflowService(session)
        workflow = await nifi_service.stop_workflow(workflow)
        
        # Get current status
        status_info = await nifi_service.get_workflow_status(workflow)
        
        return WorkflowExecutionResponse(
            workflow_id=workflow_id,
            execution_id=str(workflow.workflow_id),
            status=WorkflowStatus.STOPPED,
            nifi_process_group_id=workflow.nifi_process_group_id,
            nifi_status=status_info.get("nifi_status"),
            deployment_method=workflow.deployment_method,
            stopped_at=workflow.updated_at,
            message="Workflow stopped successfully"
        )
        
    except Exception as e:
        logger.error(f"Failed to stop workflow {workflow_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to stop workflow: {str(e)}")


@router.get("/{workflow_id}/status", response_model=WorkflowExecutionResponse)
async def get_workflow_status(
    workflow_id: str,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(require_permission("workflow:read"))
):
    """Get the current status of a workflow."""
    try:
        # Get workflow from database
        workflow = await _get_workflow(session, workflow_id, auth_context.tenant_id)
        
        # Initialize NiFi workflow service and get status
        nifi_service = NiFiWorkflowService(session)
        status_info = await nifi_service.get_workflow_status(workflow)
        
        # Map database status to API status
        api_status = _map_workflow_status(workflow.status, status_info.get("nifi_status"))
        
        return WorkflowExecutionResponse(
            workflow_id=workflow_id,
            execution_id=str(workflow.workflow_id),
            status=api_status,
            nifi_process_group_id=workflow.nifi_process_group_id,
            nifi_status=status_info.get("nifi_status"),
            deployment_method=workflow.deployment_method,
            health_check=status_info.get("health_check"),
            message=f"Workflow status: {workflow.status}"
        )
        
    except Exception as e:
        logger.error(f"Failed to get workflow status {workflow_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get workflow status: {str(e)}")


@router.post("/{workflow_id}/restart", response_model=WorkflowExecutionResponse)
async def restart_workflow(
    workflow_id: str,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(require_permission("workflow:execute"))
):
    """Restart a workflow by stopping and starting it."""
    try:
        # Get workflow from database
        workflow = await _get_workflow(session, workflow_id, auth_context.tenant_id)
        
        # Initialize NiFi workflow service
        nifi_service = NiFiWorkflowService(session)
        
        # Stop workflow if running
        if workflow.nifi_process_group_id and workflow.status in ["ACTIVE", "RUNNING"]:
            await nifi_service.stop_workflow(workflow)
        
        # Start workflow
        workflow = await nifi_service.start_workflow(workflow)
        
        # Get current status
        status_info = await nifi_service.get_workflow_status(workflow)
        
        return WorkflowExecutionResponse(
            workflow_id=workflow_id,
            execution_id=str(workflow.workflow_id),
            status=WorkflowStatus.RUNNING,
            nifi_process_group_id=workflow.nifi_process_group_id,
            nifi_status=status_info.get("nifi_status"),
            deployment_method=workflow.deployment_method,
            restarted_at=workflow.updated_at,
            message="Workflow restarted successfully"
        )
        
    except Exception as e:
        logger.error(f"Failed to restart workflow {workflow_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to restart workflow: {str(e)}")


@router.delete("/{workflow_id}/deployment")
async def undeploy_workflow(
    workflow_id: str,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(require_permission("workflow:execute"))
):
    """Undeploy a workflow from NiFi."""
    try:
        # Get workflow from database
        workflow = await _get_workflow(session, workflow_id, auth_context.tenant_id)
        
        if not workflow.nifi_process_group_id:
            return {"message": "Workflow is not deployed to NiFi"}
        
        # Initialize NiFi workflow service and undeploy
        nifi_service = NiFiWorkflowService(session)
        workflow = await nifi_service.undeploy_workflow(workflow)
        
        return {
            "workflow_id": workflow_id,
            "message": "Workflow undeployed successfully",
            "status": workflow.status
        }
        
    except Exception as e:
        logger.error(f"Failed to undeploy workflow {workflow_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to undeploy workflow: {str(e)}")


# Helper functions

async def _get_workflow(session: AsyncSession, workflow_id: str, tenant_id: str) -> Workflow:
    """Get workflow from database with tenant validation."""
    query = select(Workflow).where(
        Workflow.workflow_id == workflow_id,
        Workflow.tenant_id == tenant_id
    )
    result = await session.execute(query)
    workflow = result.scalar_one_or_none()
    
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found or access denied")
    
    return workflow


def _map_workflow_status(db_status: str, nifi_status: Optional[str]) -> WorkflowStatus:
    """Map database and NiFi status to API status enum."""
    if db_status == "ACTIVE" and nifi_status == "RUNNING":
        return WorkflowStatus.RUNNING
    elif db_status == "PAUSED" or nifi_status == "STOPPED":
        return WorkflowStatus.STOPPED
    elif db_status == "ERROR":
        return WorkflowStatus.FAILED
    elif db_status == "PENDING":
        return WorkflowStatus.PENDING
    elif db_status == "DELETED":
        return WorkflowStatus.STOPPED
    else:
        return WorkflowStatus.UNKNOWN


async def _monitor_workflow_execution(
    workflow_id: str,
    tenant_id: str,
    interval_seconds: int = 30
):
    """Background task to monitor workflow execution."""
    import asyncio
    
    logger.info(f"Starting background monitoring for workflow {workflow_id} - NEW VERSION")
    
    try:
        # Monitor for a reasonable time (e.g., 1 hour)
        max_iterations = 120  # 1 hour with 30-second intervals
        iteration = 0
        
        while iteration < max_iterations:
            try:
                async with AsyncSessionLocal() as session:
                    workflow = await _get_workflow(session, workflow_id, tenant_id)
                    nifi_service = NiFiWorkflowService(session)
                    status_info = await nifi_service.get_workflow_status(workflow)
                    
                    logger.info(f"Workflow {workflow_id} status: {workflow.status}, NiFi: {status_info.get('nifi_status')}")
                    
                    # Stop monitoring if workflow is no longer running
                    if workflow.status in ["DELETED", "ERROR"] or status_info.get("nifi_status") == "STOPPED":
                        logger.info(f"Stopping monitoring for workflow {workflow_id} - final status: {workflow.status}")
                        break
                
                await asyncio.sleep(interval_seconds)
                iteration += 1
                
            except Exception as e:
                logger.error(f"Error monitoring workflow {workflow_id}: {str(e)}")
                await asyncio.sleep(interval_seconds)
                iteration += 1
                
    except Exception as e:
        logger.error(f"Background monitoring failed for workflow {workflow_id}: {str(e)}")