"""Flow execution control operations."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from starlette.status import HTTP_200_OK

from src.api.dependencies import get_workflow_orchestrator
from src.core.logging import get_logger, audit_logger
from src.models.v1.flows import (
    ExecutionRequest,
    ExecutionResponse,
    FlowStatus
)
from src.services.workflow_orchestrator import WorkflowOrchestrator

log = get_logger(__name__)

router = APIRouter(prefix="/flows/{flow_id}/executions", tags=["flow-executions"])


@router.post("/start", response_model=ExecutionResponse, status_code=HTTP_200_OK)
async def start_flow(
    flow_id: str = Path(..., description="Flow ID"),
    force: bool = Query(False, description="Force start even if components are invalid"),
    orchestrator: WorkflowOrchestrator = Depends(get_workflow_orchestrator),
) -> ExecutionResponse:
    """Start flow execution."""
    try:
        start_time = time.time()
        log.info("Starting flow execution: %s (force=%s)", flow_id, force)
        
        # Check if flow exists
        try:
            overview = await orchestrator.get_flow_overview(flow_id)
            if not overview:
                raise HTTPException(
                    status_code=404,
                    detail={
                        "error_type": "FLOW_NOT_FOUND",
                        "message": f"Flow {flow_id} not found"
                    }
                )
        except Exception:
            raise HTTPException(
                status_code=404,
                detail={
                    "error_type": "FLOW_NOT_FOUND", 
                    "message": f"Flow {flow_id} not found"
                }
            )
        
        # Check current status
        flow_status = overview.get("flow_status", {}) or {}
        current_status = flow_status.get("overall_status", "unknown")
        
        if current_status == "running":
            return ExecutionResponse(
                success=True,
                message="Flow is already running",
                status=FlowStatus.RUNNING,
                details={
                    "running_processors": flow_status.get("running_processors", 0),
                    "total_processors": flow_status.get("total_processors", 0)
                }
            )
        
        # Check for invalid components if not forcing
        invalid_count = flow_status.get("invalid_processors", 0)
        if not force and invalid_count > 0:
            raise HTTPException(
                status_code=400,
                detail={
                    "error_type": "INVALID_COMPONENTS",
                    "message": f"Flow has {invalid_count} invalid components",
                    "action_required": "Fix invalid components or use force=true"
                }
            )
        
        # Start the flow
        result = await orchestrator.nifi_flow_mgmt.start_flow(flow_id)
        
        if result.get("success"):
            duration = time.time() - start_time
            log.info("Successfully started flow %s in %.2fs", flow_id, duration)
            audit_logger.log_flow_operation(
                "flow_started",
                bucket_id="unknown",
                flow_id=flow_id,
                details={"force": force, "duration_ms": duration * 1000}
            )
            
            return ExecutionResponse(
                success=True,
                message="Flow started successfully",
                status=FlowStatus.RUNNING,
                details=result.get("details", {})
            )
        else:
            raise HTTPException(
                status_code=400,
                detail={
                    "error_type": "START_FAILED",
                    "message": result.get("message", "Failed to start flow"),
                    "details": result.get("details", {})
                }
            )
            
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("Failed to start flow %s", flow_id)
        raise HTTPException(
            status_code=500,
            detail={
                "error_type": "START_ERROR",
                "message": "Failed to start flow execution",
                "details": str(exc)
            }
        ) from exc


@router.post("/stop", response_model=ExecutionResponse, status_code=HTTP_200_OK)
async def stop_flow(
    flow_id: str = Path(..., description="Flow ID"),
    force: bool = Query(False, description="Force stop immediately"),
    orchestrator: WorkflowOrchestrator = Depends(get_workflow_orchestrator),
) -> ExecutionResponse:
    """Stop flow execution."""
    try:
        start_time = time.time()
        log.info("Stopping flow execution: %s (force=%s)", flow_id, force)
        
        # Check if flow exists
        try:
            overview = await orchestrator.get_flow_overview(flow_id)
            if not overview:
                raise HTTPException(
                    status_code=404,
                    detail={
                        "error_type": "FLOW_NOT_FOUND",
                        "message": f"Flow {flow_id} not found"
                    }
                )
        except Exception:
            raise HTTPException(
                status_code=404,
                detail={
                    "error_type": "FLOW_NOT_FOUND",
                    "message": f"Flow {flow_id} not found"
                }
            )
        
        # Check current status
        flow_status = overview.get("flow_status", {}) or {}
        current_status = flow_status.get("overall_status", "unknown")
        
        if current_status == "stopped":
            return ExecutionResponse(
                success=True,
                message="Flow is already stopped",
                status=FlowStatus.STOPPED,
                details={
                    "stopped_processors": flow_status.get("stopped_processors", 0),
                    "total_processors": flow_status.get("total_processors", 0)
                }
            )
        
        # Stop the flow
        result = await orchestrator.nifi_flow_mgmt.stop_flow(flow_id)
        
        if result.get("success"):
            duration = time.time() - start_time
            log.info("Successfully stopped flow %s in %.2fs", flow_id, duration)
            audit_logger.log_flow_operation(
                "flow_stopped", 
                bucket_id="unknown",
                flow_id=flow_id,
                details={"force": force, "duration_ms": duration * 1000}
            )
            
            return ExecutionResponse(
                success=True,
                message="Flow stopped successfully", 
                status=FlowStatus.STOPPED,
                details=result.get("details", {})
            )
        else:
            raise HTTPException(
                status_code=400,
                detail={
                    "error_type": "STOP_FAILED",
                    "message": result.get("message", "Failed to stop flow"),
                    "details": result.get("details", {})
                }
            )
            
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("Failed to stop flow %s", flow_id)
        raise HTTPException(
            status_code=500,
            detail={
                "error_type": "STOP_ERROR",
                "message": "Failed to stop flow execution",
                "details": str(exc)
            }
        ) from exc


@router.get("/status", response_model=ExecutionResponse, status_code=HTTP_200_OK)
async def get_execution_status(
    flow_id: str = Path(..., description="Flow ID"),
    orchestrator: WorkflowOrchestrator = Depends(get_workflow_orchestrator),
) -> ExecutionResponse:
    """Get flow execution status."""
    try:
        log.debug("Getting execution status for flow: %s", flow_id)
        
        try:
            overview = await orchestrator.get_flow_overview(flow_id)
            if not overview:
                raise HTTPException(
                    status_code=404,
                    detail={
                        "error_type": "FLOW_NOT_FOUND",
                        "message": f"Flow {flow_id} not found"
                    }
                )
        except Exception:
            raise HTTPException(
                status_code=404,
                detail={
                    "error_type": "FLOW_NOT_FOUND",
                    "message": f"Flow {flow_id} not found"
                }
            )
        
        flow_status = overview.get("flow_status", {}) or {}
        overall_status = flow_status.get("overall_status", "unknown")
        
        mapped_status = FlowStatus.RUNNING if overall_status == "running" else \
                      FlowStatus.STOPPED if overall_status == "stopped" else \
                      FlowStatus.INVALID if overall_status == "invalid" else \
                      FlowStatus.UNKNOWN
        
        return ExecutionResponse(
            success=True,
            message=f"Flow is {overall_status}",
            status=mapped_status,
            details={
                "total_processors": flow_status.get("total_processors", 0),
                "running_processors": flow_status.get("running_processors", 0),
                "stopped_processors": flow_status.get("stopped_processors", 0),
                "invalid_processors": flow_status.get("invalid_processors", 0),
                "overall_status": overall_status
            }
        )
        
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("Failed to get execution status for flow %s", flow_id)
        raise HTTPException(
            status_code=500,
            detail={
                "error_type": "STATUS_ERROR",
                "message": "Failed to get execution status",
                "details": str(exc)
            }
        ) from exc