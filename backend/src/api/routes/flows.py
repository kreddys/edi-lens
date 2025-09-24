"""API routes for deployment-first flow management."""

from __future__ import annotations

import time
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from starlette.status import HTTP_200_OK, HTTP_201_CREATED

from src.api.dependencies import get_workflow_orchestrator
from src.core.logging import get_logger, audit_logger
from src.models.flow_models import (
    DeployAndStoreFlowRequest,
    DeployAndStoreFlowResponse,
    FlowStatusResponse,
    UpdateDeployedFlowRequest,
    VersionControlOperationResponse,
)
from src.services.workflow_orchestrator import WorkflowOrchestrator

log = get_logger(__name__)

router = APIRouter(prefix="/flows", tags=["flows"])


@router.post("/deploy-and-store", response_model=DeployAndStoreFlowResponse, status_code=HTTP_201_CREATED)
async def deploy_and_store_flow(
    request: DeployAndStoreFlowRequest,
    http_request: Request,
    orchestrator: WorkflowOrchestrator = Depends(get_workflow_orchestrator),
) -> DeployAndStoreFlowResponse:
    """
    Deploy flow to NiFi and store in Registry with version control.
    This is the main endpoint for the deployment-first workflow.
    """
    start_time = time.time()
    flow_name = request.flow_name or request.flow_definition.name

    log.info("Starting deploy-and-store for flow '%s' in bucket '%s'", flow_name, request.bucket_id)
    log.debug("Flow definition: %d processors, %d connections",
             len(request.flow_definition.processors),
             len(request.flow_definition.connections))
    log.debug("Parameters: %d items", len(request.parameters))

    try:
        result = await orchestrator.deploy_and_register_flow(
            flow_definition=request.flow_definition.model_dump(),
            flow_name=flow_name,
            bucket_name=request.bucket_id,  # Assuming bucket_id is actually bucket name for now
            parameters=request.parameters,
            comments=request.flow_description,
            parent_group_id=request.parent_group_id,
        )

        execution_time = (time.time() - start_time) * 1000

        if result.get("success"):
            log.info("Successfully deployed and stored flow '%s' in %.2fms", flow_name, execution_time)

            # Audit log success
            audit_logger.log_api_call(
                method=http_request.method,
                endpoint=str(http_request.url.path),
                request_data={"bucket_id": request.bucket_id, "flow_name": flow_name},
                response_status=201,
                execution_time_ms=execution_time
            )

            return DeployAndStoreFlowResponse(
                success=True,
                stage=result.get("stage"),
                flow_id=result.get("registry_upload", {}).get("flow_id"),
                version=result.get("registry_upload", {}).get("version"),
                process_group_id=result.get("process_group_id"),
                parameter_context_id=result.get("nifi_deployment", {}).get("parameter_context_id"),
                message="Flow deployed and stored successfully",
                deployment_summary=result.get("nifi_deployment", {}).get("summary", {}),
            )
        else:
            log.warning("Deploy-and-store failed at stage %s: %s",
                       result.get("stage"), result.get("error", {}).get("user_message"))

            # Audit log for business logic failures
            audit_logger.log_api_call(
                method=http_request.method,
                endpoint=str(http_request.url.path),
                request_data={"bucket_id": request.bucket_id, "flow_name": flow_name},
                response_status=400,
                execution_time_ms=execution_time
            )

            raise HTTPException(
                status_code=400,
                detail=result.get("error", {}) if result.get("error") else "Deploy-and-store failed",
            )

    except HTTPException:
        raise
    except Exception as exc:
        execution_time = (time.time() - start_time) * 1000
        log.error("Unexpected error in deploy-and-store for '%s' after %.2fms: %s",
                 flow_name, execution_time, exc)

        # Audit log for system errors
        audit_logger.log_api_call(
            method=http_request.method,
            endpoint=str(http_request.url.path),
            request_data={"bucket_id": request.bucket_id, "flow_name": flow_name},
            response_status=500,
            execution_time_ms=execution_time
        )

        raise HTTPException(
            status_code=500,
            detail={
                "error_type": "INTERNAL_SERVER_ERROR",
                "user_message": "An unexpected error occurred",
                "action_required": "Contact system administrator",
            },
        ) from exc


@router.get("/{process_group_id}/status", response_model=FlowStatusResponse)
async def get_flow_status(
    process_group_id: str = Path(..., description="Process Group ID"),
    orchestrator: WorkflowOrchestrator = Depends(get_workflow_orchestrator),
) -> FlowStatusResponse:
    """Get status of a deployed flow."""
    try:
        overview = await orchestrator.get_flow_overview(process_group_id)
        flow_status = overview.get("flow_status", {}) or {}

        return FlowStatusResponse(
            process_group_id=overview.get("process_group_id", process_group_id),
            status=flow_status.get("overall_status", "unknown"),
            processor_count=flow_status.get("total_processors", 0),
            running_count=flow_status.get("running_processors", 0),
            stopped_count=flow_status.get("stopped_processors", 0),
            invalid_count=flow_status.get("invalid_processors", 0),
            version_control=overview.get("version_control_info"),
        )

    except HTTPException:
        raise
    except Exception as exc:
        log.exception("Failed to get flow status for %s", process_group_id)
        raise HTTPException(
            status_code=500,
            detail={
                "error_type": "STATUS_FAILED",
                "user_message": f"Failed to get flow status: {exc}",
                "action_required": "Check process group ID and try again",
            },
        ) from exc


@router.post("/{process_group_id}/start", status_code=HTTP_200_OK)
async def start_flow(
    process_group_id: str = Path(..., description="Process Group ID"),
    orchestrator: WorkflowOrchestrator = Depends(get_workflow_orchestrator),
) -> Dict[str, str]:
    """Start all processors in a deployed flow."""
    try:
        result = await orchestrator.start_flow_workflow(process_group_id)

        if result.get("success"):
            return {"message": "Flow started successfully", "process_group_id": process_group_id}
        else:
            raise HTTPException(
                status_code=400,
                detail=result.get("start_result", {}),
            )

    except HTTPException:
        raise
    except Exception as exc:
        log.exception("Failed to start flow %s", process_group_id)
        raise HTTPException(
            status_code=500,
            detail={
                "error_type": "START_FAILED",
                "user_message": f"Failed to start flow: {exc}",
                "action_required": "Check flow status and try again",
            },
        ) from exc


@router.post("/{process_group_id}/stop", status_code=HTTP_200_OK)
async def stop_flow(
    process_group_id: str = Path(..., description="Process Group ID"),
    orchestrator: WorkflowOrchestrator = Depends(get_workflow_orchestrator),
) -> Dict[str, str]:
    """Stop all processors in a deployed flow."""
    try:
        result = await orchestrator.stop_flow_workflow(process_group_id)

        if result.get("success"):
            return {"message": "Flow stopped successfully", "process_group_id": process_group_id}
        else:
            raise HTTPException(
                status_code=400,
                detail=result.get("stop_result", {}),
            )

    except HTTPException:
        raise
    except Exception as exc:
        log.exception("Failed to stop flow %s", process_group_id)
        raise HTTPException(
            status_code=500,
            detail={
                "error_type": "STOP_FAILED",
                "user_message": f"Failed to stop flow: {exc}",
                "action_required": "Check flow status and try again",
            },
        ) from exc


@router.delete("/{process_group_id}")
async def delete_flow(
    process_group_id: str = Path(..., description="Process Group ID"),
    remove_from_registry: bool = Query(False, description="Also remove from Registry"),
    orchestrator: WorkflowOrchestrator = Depends(get_workflow_orchestrator),
):
    """Delete a deployed flow and optionally remove from Registry."""
    try:
        result = await orchestrator.delete_flow_workflow(process_group_id, remove_from_registry)

        if result.get("success"):
            return {
                "message": "Flow deleted successfully",
                "process_group_id": process_group_id,
                "removed_from_registry": remove_from_registry,
            }
        else:
            raise HTTPException(
                status_code=400,
                detail=result.get("nifi_delete", {}),
            )

    except HTTPException:
        raise
    except Exception as exc:
        log.exception("Failed to delete flow %s", process_group_id)
        raise HTTPException(
            status_code=500,
            detail={
                "error_type": "DELETE_FAILED",
                "user_message": f"Failed to delete flow: {exc}",
                "action_required": "Check process group ID and try again",
            },
        ) from exc


@router.put("/{process_group_id}", response_model=VersionControlOperationResponse)
async def update_deployed_flow(
    request: UpdateDeployedFlowRequest,
    process_group_id: str = Path(..., description="Process Group ID"),
    orchestrator: WorkflowOrchestrator = Depends(get_workflow_orchestrator),
) -> VersionControlOperationResponse:
    """Update a deployed flow and optionally commit changes to Registry."""
    try:
        # This endpoint would need a custom implementation combining multiple orchestrator services
        # For now, return a not implemented response
        raise HTTPException(
            status_code=501,
            detail={
                "error_type": "NOT_IMPLEMENTED",
                "user_message": "Update deployed flow endpoint needs to be reimplemented with new architecture",
                "action_required": "Use separate endpoints for flow updates and version control operations",
            },
        )


    except HTTPException:
        raise
    except Exception as exc:
        log.exception("Failed to update flow %s", process_group_id)
        raise HTTPException(
            status_code=500,
            detail={
                "error_type": "UPDATE_FAILED",
                "user_message": f"Failed to update flow: {exc}",
                "action_required": "Check process group ID and try again",
            },
        ) from exc


# Version Control Operations
@router.post("/{process_group_id}/version-control/commit", response_model=VersionControlOperationResponse)
async def commit_changes(
    process_group_id: str = Path(..., description="Process Group ID"),
    comments: str = Query("Updated flow", description="Commit comments"),
    orchestrator: WorkflowOrchestrator = Depends(get_workflow_orchestrator),
) -> VersionControlOperationResponse:
    """Commit local changes to Registry."""
    try:
        result = await orchestrator.integration_bridge.sync_flow_with_registry(
            process_group_id=process_group_id,
            action="push"
        )

        if result.get("success"):
            return VersionControlOperationResponse(
                success=True,
                process_group_id=process_group_id,
                message="Changes committed successfully",
                committed=True,
            )
        else:
            raise HTTPException(
                status_code=400,
                detail={"message": result.get("message", "Commit failed")},
            )

    except HTTPException:
        raise
    except Exception as exc:
        log.exception("Failed to commit changes for flow %s", process_group_id)
        raise HTTPException(
            status_code=500,
            detail={
                "error_type": "COMMIT_FAILED",
                "user_message": f"Failed to commit changes: {exc}",
                "action_required": "Check version control status and try again",
            },
        ) from exc


@router.post("/{process_group_id}/version-control/update", response_model=VersionControlOperationResponse)
async def update_from_registry(
    process_group_id: str = Path(..., description="Process Group ID"),
    orchestrator: WorkflowOrchestrator = Depends(get_workflow_orchestrator),
) -> VersionControlOperationResponse:
    """Update flow from latest version in Registry."""
    try:
        result = await orchestrator.integration_bridge.sync_flow_with_registry(
            process_group_id=process_group_id,
            action="pull"
        )

        if result.get("success"):
            return VersionControlOperationResponse(
                success=True,
                process_group_id=process_group_id,
                message="Flow updated from Registry successfully",
                committed=False,
            )
        else:
            raise HTTPException(
                status_code=400,
                detail={"message": result.get("message", "Update failed")},
            )

    except HTTPException:
        raise
    except Exception as exc:
        log.exception("Failed to update flow %s from Registry", process_group_id)
        raise HTTPException(
            status_code=500,
            detail={
                "error_type": "UPDATE_FROM_REGISTRY_FAILED",
                "user_message": f"Failed to update from Registry: {exc}",
                "action_required": "Check version control status and try again",
            },
        ) from exc


@router.post("/{process_group_id}/version-control/revert", response_model=VersionControlOperationResponse)
async def revert_changes(
    process_group_id: str = Path(..., description="Process Group ID"),
    orchestrator: WorkflowOrchestrator = Depends(get_workflow_orchestrator),
) -> VersionControlOperationResponse:
    """Revert local changes to Registry version."""
    try:
        # Disconnect and re-import from Registry to revert changes
        result = await orchestrator.integration_bridge.sync_flow_with_registry(
            process_group_id=process_group_id,
            action="pull"
        )

        if result.get("success"):
            return VersionControlOperationResponse(
                success=True,
                process_group_id=process_group_id,
                message="Changes reverted successfully",
                committed=False,
            )
        else:
            raise HTTPException(
                status_code=400,
                detail={"message": result.get("message", "Revert failed")},
            )

    except HTTPException:
        raise
    except Exception as exc:
        log.exception("Failed to revert changes for flow %s", process_group_id)
        raise HTTPException(
            status_code=500,
            detail={
                "error_type": "REVERT_FAILED",
                "user_message": f"Failed to revert changes: {exc}",
                "action_required": "Check version control status and try again",
            },
        ) from exc


@router.get("/{process_group_id}/version-control/modifications")
async def get_local_modifications(
    process_group_id: str = Path(..., description="Process Group ID"),
    orchestrator: WorkflowOrchestrator = Depends(get_workflow_orchestrator),
) -> Dict:
    """Get local modifications for a version controlled flow."""
    try:
        result = await orchestrator.integration_bridge.compare_with_registry(process_group_id)

        return {
            "has_local_changes": result.get("has_local_changes", False),
            "differences": result.get("differences", {}),
            "current_version": result.get("current_version"),
            "latest_version": result.get("latest_version"),
            "is_latest": result.get("is_latest", True)
        }

    except HTTPException:
        raise
    except Exception as exc:
        log.exception("Failed to get local modifications for flow %s", process_group_id)
        raise HTTPException(
            status_code=500,
            detail={
                "error_type": "MODIFICATIONS_FAILED",
                "user_message": f"Failed to get local modifications: {exc}",
                "action_required": "Check version control status and try again",
            },
        ) from exc


# Registry passthrough endpoints (for compatibility)
@router.get("/registry/buckets")
async def list_buckets(
    orchestrator: WorkflowOrchestrator = Depends(get_workflow_orchestrator),
) -> List[Dict]:
    """List available Registry buckets."""
    try:
        buckets = await orchestrator.registry_bucket_mgmt.list_buckets()
        return buckets
    except Exception as exc:
        log.exception("Failed to list buckets")
        raise HTTPException(
            status_code=500,
            detail={
                "error_type": "BUCKET_LIST_FAILED",
                "user_message": "Failed to retrieve bucket list",
                "action_required": "Please try again or contact support",
            },
        ) from exc


@router.get("/registry/buckets/{bucket_id}/flows")
async def list_flows_in_bucket(
    bucket_id: str = Path(..., description="Registry bucket ID"),
    orchestrator: WorkflowOrchestrator = Depends(get_workflow_orchestrator),
) -> List[Dict]:
    """List flows in a Registry bucket."""
    try:
        flows = await orchestrator.registry_flow_mgmt.list_flows_in_bucket(bucket_id)
        return flows
    except Exception as exc:
        log.exception("Failed to list flows in bucket %s", bucket_id)
        raise HTTPException(
            status_code=500,
            detail={
                "error_type": "FLOW_LIST_FAILED",
                "user_message": f"Failed to retrieve flows from bucket {bucket_id}",
                "action_required": "Verify bucket exists and try again",
            },
        ) from exc


@router.get("/registry/buckets/{bucket_id}/flows/{flow_id}")
async def get_flow_from_registry(
    bucket_id: str = Path(..., description="Registry bucket ID"),
    flow_id: str = Path(..., description="Flow ID"),
    version: Optional[int] = Query(None, description="Specific version (latest if not specified)"),
    orchestrator: WorkflowOrchestrator = Depends(get_workflow_orchestrator),
) -> Dict:
    """Get flow definition from Registry."""
    try:
        if version:
            flow = await orchestrator.registry_version_mgmt.get_flow_version(bucket_id, flow_id, version)
        else:
            flow = await orchestrator.registry_version_mgmt.get_latest_flow_version(bucket_id, flow_id)
        return flow
    except Exception as exc:
        log.exception("Failed to get flow %s/%s", bucket_id, flow_id)
        raise HTTPException(
            status_code=404 if "not found" in str(exc).lower() else 500,
            detail={
                "error_type": "FLOW_NOT_FOUND" if "not found" in str(exc).lower() else "FLOW_GET_FAILED",
                "user_message": f"Flow {flow_id} not found" if "not found" in str(exc).lower() else "Failed to retrieve flow",
                "action_required": "Verify flow ID and try again",
            },
        ) from exc