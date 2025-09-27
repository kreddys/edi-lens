"""Simple flow execution control operations."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException
from starlette.status import HTTP_200_OK

from src.api.dependencies import get_workflow_orchestrator
from src.core.logging import get_logger
from src.models.v1.flows import ExecutionRequest, ExecutionResponse
from src.services.workflow_orchestrator import WorkflowOrchestrator

log = get_logger(__name__)

router = APIRouter(prefix="/flows/executions", tags=["flow-executions"])


@router.post("/", response_model=ExecutionResponse, status_code=HTTP_200_OK)
async def control_flow(
    execution_data: ExecutionRequest,
    orchestrator: WorkflowOrchestrator = Depends(get_workflow_orchestrator),
) -> ExecutionResponse:
    """Start or stop flow execution by process group ID."""
    try:
        start_time = time.time()
        process_group_id = execution_data.process_group_id
        action = execution_data.action.lower()
        
        log.info("Flow execution control: %s action on %s", action, process_group_id)
        
        if action == "start":
            # Start all processors in the process group
            result = await orchestrator.start_flow_workflow(process_group_id)
            message = "Flow started successfully"
        elif action == "stop":
            # Stop all processors in the process group  
            result = await orchestrator.stop_flow_workflow(process_group_id)
            message = "Flow stopped successfully"
        else:
            raise HTTPException(
                status_code=400,
                detail={
                    "error_type": "INVALID_ACTION",
                    "message": f"Invalid action: {action}. Must be 'start' or 'stop'"
                }
            )
        
        execution_time = (time.time() - start_time) * 1000
        
        log.info("Flow execution control completed in %.2fms", execution_time)
        
        return ExecutionResponse(
            success=True,
            message=message,
            process_group_id=process_group_id,
            action=action,
            execution_time_ms=execution_time
        )
        
    except HTTPException:
        raise
    except Exception as exc:
        log.error("Flow execution control failed: %s", exc)
        raise HTTPException(
            status_code=500,
            detail={
                "error_type": "EXECUTION_FAILED",
                "message": f"Failed to {action} flow: {exc}"
            }
        ) from exc