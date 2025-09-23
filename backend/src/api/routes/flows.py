"""API routes for deployment-first flow management."""

from __future__ import annotations

import time
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from starlette.status import HTTP_200_OK, HTTP_201_CREATED

from src.api.dependencies import get_flow_service
from src.core.logging import get_logger, audit_logger
from src.models.flow_models import (
    DeployAndStoreFlowRequest,
    DeployAndStoreFlowResponse,
    FlowStatusResponse,
    UpdateDeployedFlowRequest,
    VersionControlOperationResponse,
)
from src.services.flow_service import FlowService

log = get_logger(__name__)

router = APIRouter(prefix="/flows", tags=["flows"])


@router.post("/deploy-and-store", response_model=DeployAndStoreFlowResponse, status_code=HTTP_201_CREATED)
async def deploy_and_store_flow(
    request: DeployAndStoreFlowRequest,
    http_request: Request,
    flow_service: FlowService = Depends(get_flow_service),
) -> DeployAndStoreFlowResponse:
    """
    Deploy flow to NiFi and store in Registry with version control.
    This is the main endpoint for the deployment-first workflow.
    """
    start_time = time.time()
    flow_name = request.flow_definition.name

    log.info("Starting deploy-and-store for flow '%s' in bucket '%s'", flow_name, request.bucket_id)
    log.debug("Flow definition: %d processors, %d connections",
             len(request.flow_definition.processors),
             len(request.flow_definition.connections))
    log.debug("Parameters: %d items", len(request.parameters))

    try:
        result = await flow_service.deploy_and_store_flow(
            bucket_id=request.bucket_id,
            flow_definition=request.flow_definition.model_dump(),
            parameters=request.parameters,
            parent_group_id=request.parent_group_id,
            flow_name=request.flow_name,
            flow_description=request.flow_description,
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
                flow_id=result.get("flow_id"),
                version=result.get("version"),
                process_group_id=result.get("process_group_id"),
                parameter_context_id=result.get("parameter_context_id"),
                message="Flow deployed and stored successfully",
                deployment_summary=result.get("deployment_result", {}).get("summary", {}),
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
    flow_service: FlowService = Depends(get_flow_service),
) -> FlowStatusResponse:
    """Get status of a deployed flow."""
    try:
        result = await flow_service.get_flow_status(process_group_id)

        if result.get("success"):
            return FlowStatusResponse(**{k: v for k, v in result.items() if k != "success"})
        else:
            raise HTTPException(
                status_code=404 if "not found" in str(result.get("error", {})).lower() else 500,
                detail=result.get("error", {}),
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
    flow_service: FlowService = Depends(get_flow_service),
) -> Dict[str, str]:
    """Start all processors in a deployed flow."""
    try:
        result = await flow_service.start_flow(process_group_id)

        if result.get("success"):
            return {"message": "Flow started successfully", "process_group_id": process_group_id}
        else:
            raise HTTPException(
                status_code=400,
                detail=result.get("error", {}),
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
    flow_service: FlowService = Depends(get_flow_service),
) -> Dict[str, str]:
    """Stop all processors in a deployed flow."""
    try:
        result = await flow_service.stop_flow(process_group_id)

        if result.get("success"):
            return {"message": "Flow stopped successfully", "process_group_id": process_group_id}
        else:
            raise HTTPException(
                status_code=400,
                detail=result.get("error", {}),
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
    flow_service: FlowService = Depends(get_flow_service),
):
    """Delete a deployed flow and optionally remove from Registry."""
    try:
        result = await flow_service.delete_flow(process_group_id, remove_from_registry)

        if result.get("success"):
            return {
                "message": "Flow deleted successfully",
                "process_group_id": process_group_id,
                "removed_from_registry": remove_from_registry,
            }
        else:
            raise HTTPException(
                status_code=400,
                detail=result.get("error", {}),
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
    flow_service: FlowService = Depends(get_flow_service),
) -> VersionControlOperationResponse:
    """Update a deployed flow and optionally commit changes to Registry."""
    try:
        result = await flow_service.update_deployed_flow(
            process_group_id=process_group_id,
            flow_definition=request.flow_definition.model_dump() if request.flow_definition else None,
            parameters=request.parameters,
            commit_changes=request.commit_changes,
            comments=request.comments,
        )

        if result.get("success"):
            return VersionControlOperationResponse(
                success=True,
                process_group_id=process_group_id,
                message="Flow updated successfully",
                committed=result.get("committed", False),
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=result.get("error", {}),
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
    flow_service: FlowService = Depends(get_flow_service),
) -> VersionControlOperationResponse:
    """Commit local changes to Registry."""
    try:
        result = await flow_service.commit_changes(process_group_id, comments)

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
                detail=result.get("error", {}),
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
    flow_service: FlowService = Depends(get_flow_service),
) -> VersionControlOperationResponse:
    """Update flow from latest version in Registry."""
    try:
        result = await flow_service.update_from_registry(process_group_id)

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
                detail=result.get("error", {}),
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
    flow_service: FlowService = Depends(get_flow_service),
) -> VersionControlOperationResponse:
    """Revert local changes to Registry version."""
    try:
        result = await flow_service.revert_changes(process_group_id)

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
                detail=result.get("error", {}),
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
    flow_service: FlowService = Depends(get_flow_service),
) -> Dict:
    """Get local modifications for a version controlled flow."""
    try:
        result = await flow_service.get_local_modifications(process_group_id)

        if result.get("success"):
            return result.get("local_modifications", {})
        else:
            raise HTTPException(
                status_code=400,
                detail=result.get("error", {}),
            )

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
    flow_service: FlowService = Depends(get_flow_service),
) -> List[Dict]:
    """List available Registry buckets."""
    try:
        buckets = await flow_service.list_buckets()
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
    flow_service: FlowService = Depends(get_flow_service),
) -> List[Dict]:
    """List flows in a Registry bucket."""
    try:
        flows = await flow_service.list_flows(bucket_id)
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
    flow_service: FlowService = Depends(get_flow_service),
) -> Dict:
    """Get flow definition from Registry."""
    try:
        flow = await flow_service.get_flow_from_registry(bucket_id, flow_id, version)
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