"""Flow deployment operations."""

from __future__ import annotations

import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from starlette.status import HTTP_200_OK, HTTP_201_CREATED, HTTP_204_NO_CONTENT

from src.api.dependencies import get_workflow_orchestrator
from src.core.logging import get_logger, audit_logger
from src.models.v1.flows import (
    DeploymentRequest,
    DeploymentResponse,
    DeploymentStatus
)
from src.services.workflow_orchestrator import WorkflowOrchestrator

log = get_logger(__name__)

router = APIRouter(prefix="/flows/{flow_id}/deployments", tags=["flow-deployments"])


@router.post("/", response_model=DeploymentResponse, status_code=HTTP_201_CREATED)
async def deploy_flow(
    deployment_data: DeploymentRequest,
    flow_id: str = Path(..., description="Flow ID"),
    orchestrator: WorkflowOrchestrator = Depends(get_workflow_orchestrator),
) -> DeploymentResponse:
    """Deploy a flow."""
    try:
        start_time = time.time()
        log.info("Deploying flow: %s", flow_id)
        
        # Check if flow exists (this is a simplified check)
        try:
            overview = await orchestrator.get_flow_overview(flow_id)
            if overview:
                # Flow is already deployed
                return DeploymentResponse(
                    success=True,
                    deployment_id=flow_id,
                    status=DeploymentStatus.DEPLOYED,
                    message="Flow is already deployed",
                    flow_id=overview.get("version_control_info", {}).get("flowId"),
                    version=overview.get("version_control_info", {}).get("version")
                )
        except Exception:
            pass  # Flow doesn't exist, which is expected for new deployments
        
        # For now, return not implemented since deployment is handled in flow creation
        raise HTTPException(
            status_code=501,
            detail={
                "error_type": "NOT_IMPLEMENTED", 
                "message": "Standalone deployment is not yet implemented",
                "action_required": "Use POST /api/v1/flows/ to create and deploy flows"
            }
        )
        
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("Failed to deploy flow %s", flow_id)
        raise HTTPException(
            status_code=500,
            detail={
                "error_type": "DEPLOYMENT_ERROR",
                "message": "Failed to deploy flow", 
                "details": str(exc)
            }
        ) from exc


@router.get("/", response_model=DeploymentResponse, status_code=HTTP_200_OK)
async def get_deployment_status(
    flow_id: str = Path(..., description="Flow ID"),
    orchestrator: WorkflowOrchestrator = Depends(get_workflow_orchestrator),
) -> DeploymentResponse:
    """Get deployment status of a flow."""
    try:
        log.debug("Getting deployment status for flow: %s", flow_id)
        
        try:
            overview = await orchestrator.get_flow_overview(flow_id)
            
            if not overview:
                return DeploymentResponse(
                    success=False,
                    deployment_id=flow_id,
                    status=DeploymentStatus.UNDEPLOYED,
                    message="Flow is not deployed"
                )
            
            # Extract deployment information
            version_control = overview.get("version_control_info", {}) or {}
            flow_status = overview.get("flow_status", {}) or {}
            
            return DeploymentResponse(
                success=True,
                deployment_id=flow_id,
                status=DeploymentStatus.DEPLOYED,
                message="Flow is deployed and ready",
                flow_id=version_control.get("flowId"),
                version=version_control.get("version"),
                summary={
                    "total_processors": flow_status.get("total_processors", 0),
                    "running_processors": flow_status.get("running_processors", 0),
                    "stopped_processors": flow_status.get("stopped_processors", 0),
                    "invalid_processors": flow_status.get("invalid_processors", 0),
                    "overall_status": flow_status.get("overall_status", "unknown")
                }
            )
            
        except Exception:
            return DeploymentResponse(
                success=False,
                deployment_id=flow_id,
                status=DeploymentStatus.UNDEPLOYED,
                message="Flow is not deployed or not accessible"
            )
            
    except Exception as exc:
        log.exception("Failed to get deployment status for flow %s", flow_id)
        raise HTTPException(
            status_code=500,
            detail={
                "error_type": "DEPLOYMENT_STATUS_ERROR",
                "message": "Failed to get deployment status",
                "details": str(exc)
            }
        ) from exc


@router.delete("/", status_code=HTTP_204_NO_CONTENT)
async def undeploy_flow(
    flow_id: str = Path(..., description="Flow ID"),
    force: bool = Query(False, description="Force undeployment even if flow is running"),
    orchestrator: WorkflowOrchestrator = Depends(get_workflow_orchestrator),
):
    """Undeploy a flow (same as delete flow)."""
    try:
        log.info("Undeploying flow: %s (force=%s)", flow_id, force)
        
        # Check if flow exists and is deployed
        try:
            overview = await orchestrator.get_flow_overview(flow_id)
            if not overview:
                raise HTTPException(
                    status_code=404,
                    detail={
                        "error_type": "FLOW_NOT_DEPLOYED",
                        "message": f"Flow {flow_id} is not deployed"
                    }
                )
        except Exception:
            raise HTTPException(
                status_code=404,
                detail={
                    "error_type": "FLOW_NOT_DEPLOYED",
                    "message": f"Flow {flow_id} is not deployed"
                }
            )
        
        # Check if flow is running and force is not set
        flow_status = overview.get("flow_status", {}) or {}
        if not force and flow_status.get("overall_status") == "running":
            raise HTTPException(
                status_code=400,
                detail={
                    "error_type": "FLOW_RUNNING",
                    "message": "Cannot undeploy running flow without force=true",
                    "action_required": "Stop the flow first or use force=true"
                }
            )
        
        # Undeploy the flow (same as delete)
        await orchestrator.nifi_flow_mgmt.delete_flow(flow_id)
        
        log.info("Successfully undeployed flow: %s", flow_id)
        audit_logger.log_user_action("flow_undeployed", {
            "flow_id": flow_id,
            "force": force
        })
        
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("Failed to undeploy flow %s", flow_id)
        raise HTTPException(
            status_code=500,
            detail={
                "error_type": "UNDEPLOY_ERROR",
                "message": "Failed to undeploy flow",
                "details": str(exc)
            }
        ) from exc