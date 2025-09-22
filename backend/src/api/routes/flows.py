"""API routes for flow management."""

from __future__ import annotations

import logging
import time
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from starlette.status import HTTP_200_OK, HTTP_201_CREATED

from src.api.dependencies import get_flow_service
from src.core.logging import get_logger, audit_logger
from src.models.flow_models import (
    BucketListResponse,
    CreateFlowRequest,
    DeployFlowRequest,
    FlowCreationResponse,
    FlowDeploymentResponse,
    FlowListResponse,
    FlowStatusResponse,
    UpdateFlowRequest,
    UpdateParametersRequest,
)
from src.services.flow_service import FlowService

log = get_logger(__name__)

router = APIRouter(prefix="/flows", tags=["flows"])


@router.get("/buckets", response_model=BucketListResponse)
async def list_buckets(
    request: Request,
    flow_service: FlowService = Depends(get_flow_service),
) -> BucketListResponse:
    """List available Registry buckets."""
    start_time = time.time()
    
    log.info("Listing available Registry buckets")
    
    try:
        buckets = await flow_service.list_buckets()
        execution_time = (time.time() - start_time) * 1000
        
        log.info("Successfully retrieved %d buckets (%.2fms)", len(buckets), execution_time)
        
        # Audit log
        audit_logger.log_api_call(
            method=request.method,
            endpoint=str(request.url.path),
            response_status=200,
            execution_time_ms=execution_time
        )
        
        return BucketListResponse(buckets=buckets, total=len(buckets))
        
    except Exception as exc:
        execution_time = (time.time() - start_time) * 1000
        log.error("Failed to list buckets after %.2fms: %s", execution_time, exc)
        
        # Audit log for errors
        audit_logger.log_api_call(
            method=request.method,
            endpoint=str(request.url.path),
            response_status=500,
            execution_time_ms=execution_time
        )
        
        raise HTTPException(
            status_code=500,
            detail={
                "error_type": "BUCKET_LIST_FAILED",
                "user_message": "Failed to retrieve bucket list",
                "action_required": "Please try again or contact support",
            },
        ) from exc


@router.get("/{bucket_id}", response_model=FlowListResponse)
async def list_flows(
    bucket_id: str = Path(..., description="Registry bucket ID"),
    flow_service: FlowService = Depends(get_flow_service),
) -> FlowListResponse:
    """List flows in a bucket."""
    try:
        flows = await flow_service.list_flows(bucket_id)
        return FlowListResponse(flows=flows, total=len(flows))
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


@router.post("/", response_model=FlowCreationResponse, status_code=HTTP_201_CREATED)
async def create_flow(
    request: CreateFlowRequest,
    http_request: Request,
    flow_service: FlowService = Depends(get_flow_service),
) -> FlowCreationResponse:
    """Create a new flow in Registry."""
    start_time = time.time()
    flow_name = request.flow_definition.name
    
    log.info("Creating flow '%s' in bucket '%s'", flow_name, request.bucket_id)
    log.debug("Flow definition: %d processors, %d connections", 
             len(request.flow_definition.processors), 
             len(request.flow_definition.connections))
    log.debug("Parameters: %d items", len(request.parameters))
    
    try:
        result = await flow_service.create_flow(
            bucket_id=request.bucket_id,
            flow_definition=request.flow_definition.dict(),
            parameters=request.parameters,
        )
        
        execution_time = (time.time() - start_time) * 1000
        
        if result.get("success"):
            log.info("Successfully created flow '%s' (ID: %s) in %.2fms", 
                    flow_name, result.get("flow_id"), execution_time)
            
            # Audit log success
            audit_logger.log_api_call(
                method=http_request.method,
                endpoint=str(http_request.url.path),
                request_data={"bucket_id": request.bucket_id, "flow_name": flow_name},
                response_status=201,
                execution_time_ms=execution_time
            )
            
            return FlowCreationResponse(
                success=True,
                flow_id=result.get("flow_id"),
                version=result.get("version"),
                message="Flow created successfully",
            )
        else:
            log.warning("Flow creation failed: %s", result.get("error", {}).get("user_message"))
            
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
                detail=result.get("error", {}) if result.get("error") else "Flow creation failed",
            )
            
    except HTTPException:
        # Re-raise HTTP exceptions (they're already logged above)
        raise
    except Exception as exc:
        execution_time = (time.time() - start_time) * 1000
        log.error("Unexpected error creating flow '%s' after %.2fms: %s", 
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


@router.get("/{bucket_id}/{flow_id}", response_model=dict)
async def get_flow(
    bucket_id: str = Path(..., description="Registry bucket ID"),
    flow_id: str = Path(..., description="Flow ID"),
    version: Optional[int] = Query(None, description="Specific version (latest if not specified)"),
    flow_service: FlowService = Depends(get_flow_service),
) -> Dict:
    """Get flow definition and metadata."""
    try:
        flow = await flow_service.get_flow(bucket_id, flow_id, version)
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


@router.put("/{bucket_id}/{flow_id}", response_model=FlowCreationResponse)
async def update_flow(
    request: UpdateFlowRequest,
    bucket_id: str = Path(..., description="Registry bucket ID"),
    flow_id: str = Path(..., description="Flow ID"),
    flow_service: FlowService = Depends(get_flow_service),
) -> FlowCreationResponse:
    """Update an existing flow (creates new version)."""
    try:
        result = await flow_service.update_flow(
            bucket_id=bucket_id,
            flow_id=flow_id,
            flow_definition=request.flow_definition.dict() if request.flow_definition else None,
            parameters=request.parameters,
        )
        
        if result.success:
            return FlowCreationResponse(
                success=True,
                flow_id=result.flow_id,
                version=result.version,
                message="Flow updated successfully",
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=result.error.dict() if result.error else "Flow update failed",
            )
            
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("Unexpected error updating flow %s/%s", bucket_id, flow_id)
        raise HTTPException(
            status_code=500,
            detail={
                "error_type": "INTERNAL_SERVER_ERROR",
                "user_message": "An unexpected error occurred",
                "action_required": "Contact system administrator",
            },
        ) from exc


@router.delete("/{bucket_id}/{flow_id}")
async def delete_flow(
    bucket_id: str = Path(..., description="Registry bucket ID"),
    flow_id: str = Path(..., description="Flow ID"),
    flow_service: FlowService = Depends(get_flow_service),
):
    """Delete a flow and all its versions."""
    try:
        await flow_service.delete_flow(bucket_id, flow_id)
        return {"message": "Flow deleted successfully"}
    except Exception as exc:
        log.exception("Failed to delete flow %s/%s", bucket_id, flow_id)
        raise HTTPException(
            status_code=500,
            detail={
                "error_type": "FLOW_DELETE_FAILED",
                "user_message": f"Failed to delete flow {flow_id}",
                "action_required": "Please try again or contact support",
            },
        ) from exc


# Deployment Operations
@router.post("/{bucket_id}/{flow_id}/deploy", response_model=FlowDeploymentResponse)
async def deploy_flow(
    request: DeployFlowRequest,
    bucket_id: str = Path(..., description="Registry bucket ID"),
    flow_id: str = Path(..., description="Flow ID"),
    flow_service: FlowService = Depends(get_flow_service),
) -> FlowDeploymentResponse:
    """Deploy flow to NiFi canvas."""
    try:
        result = await flow_service.deploy_flow(
            bucket_id=bucket_id,
            flow_id=flow_id,
            parameters=request.parameters,
            version=request.version,
        )
        
        if result.success:
            return FlowDeploymentResponse(
                success=True,
                process_group_id=result.process_group_id,
                parameter_context_id=result.parameter_context_id,
                message="Flow deployed successfully",
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=result.error.dict() if result.error else "Flow deployment failed",
            )
            
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("Unexpected error deploying flow %s/%s", bucket_id, flow_id)
        raise HTTPException(
            status_code=500,
            detail={
                "error_type": "INTERNAL_SERVER_ERROR",
                "user_message": "An unexpected error occurred",
                "action_required": "Contact system administrator",
            },
        ) from exc


@router.delete("/{bucket_id}/{flow_id}/deploy")
async def undeploy_flow(
    bucket_id: str = Path(..., description="Registry bucket ID"),
    flow_id: str = Path(..., description="Flow ID"),
    flow_service: FlowService = Depends(get_flow_service),
):
    """Undeploy flow from NiFi canvas."""
    try:
        await flow_service.undeploy_flow(bucket_id, flow_id)
        return {"message": "Flow undeployed successfully"}
    except Exception as exc:
        log.exception("Failed to undeploy flow %s/%s", bucket_id, flow_id)
        raise HTTPException(
            status_code=500,
            detail={
                "error_type": "FLOW_UNDEPLOY_FAILED",
                "user_message": f"Failed to undeploy flow {flow_id}",
                "action_required": "Please try again or contact support",
            },
        ) from exc


@router.post("/{bucket_id}/{flow_id}/start", status_code=HTTP_200_OK)
async def start_flow(
    bucket_id: str = Path(..., description="Registry bucket ID"),
    flow_id: str = Path(..., description="Flow ID"),
    flow_service: FlowService = Depends(get_flow_service),
) -> Dict[str, str]:
    """Start flow processors."""
    try:
        success = await flow_service.start_flow(bucket_id, flow_id)
        if success:
            return {"message": "Flow started successfully"}
        else:
            raise HTTPException(
                status_code=400,
                detail={
                    "error_type": "FLOW_START_FAILED",
                    "user_message": "Failed to start flow",
                    "action_required": "Verify flow is deployed and try again",
                },
            )
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("Failed to start flow %s/%s", bucket_id, flow_id)
        raise HTTPException(
            status_code=500,
            detail={
                "error_type": "FLOW_START_FAILED",
                "user_message": f"Failed to start flow {flow_id}",
                "action_required": "Please try again or contact support",
            },
        ) from exc


@router.post("/{bucket_id}/{flow_id}/stop", status_code=HTTP_200_OK)
async def stop_flow(
    bucket_id: str = Path(..., description="Registry bucket ID"),
    flow_id: str = Path(..., description="Flow ID"),
    flow_service: FlowService = Depends(get_flow_service),
) -> Dict[str, str]:
    """Stop flow processors."""
    try:
        success = await flow_service.stop_flow(bucket_id, flow_id)
        if success:
            return {"message": "Flow stopped successfully"}
        else:
            raise HTTPException(
                status_code=400,
                detail={
                    "error_type": "FLOW_STOP_FAILED",
                    "user_message": "Failed to stop flow",
                    "action_required": "Verify flow is deployed and try again",
                },
            )
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("Failed to stop flow %s/%s", bucket_id, flow_id)
        raise HTTPException(
            status_code=500,
            detail={
                "error_type": "FLOW_STOP_FAILED",
                "user_message": f"Failed to stop flow {flow_id}",
                "action_required": "Please try again or contact support",
            },
        ) from exc


@router.get("/{bucket_id}/{flow_id}/status", response_model=FlowStatusResponse)
async def get_flow_status(
    bucket_id: str = Path(..., description="Registry bucket ID"),
    flow_id: str = Path(..., description="Flow ID"),
    flow_service: FlowService = Depends(get_flow_service),
) -> FlowStatusResponse:
    """Get flow deployment status."""
    try:
        status = await flow_service.get_flow_status(bucket_id, flow_id)
        return FlowStatusResponse(**status)
    except Exception as exc:
        log.exception("Failed to get flow status %s/%s", bucket_id, flow_id)
        raise HTTPException(
            status_code=500,
            detail={
                "error_type": "FLOW_STATUS_FAILED",
                "user_message": f"Failed to get status for flow {flow_id}",
                "action_required": "Please try again or contact support",
            },
        ) from exc


@router.put("/{bucket_id}/{flow_id}/parameters", status_code=HTTP_200_OK)
async def update_flow_parameters(
    request: UpdateParametersRequest,
    bucket_id: str = Path(..., description="Registry bucket ID"),
    flow_id: str = Path(..., description="Flow ID"),
    flow_service: FlowService = Depends(get_flow_service),
) -> Dict[str, str]:
    """Update flow parameters at runtime."""
    try:
        success = await flow_service.update_flow_parameters(
            bucket_id=bucket_id,
            flow_id=flow_id,
            parameters=request.parameters,
        )
        if success:
            return {"message": "Parameters updated successfully"}
        else:
            raise HTTPException(
                status_code=400,
                detail={
                    "error_type": "PARAMETER_UPDATE_FAILED",
                    "user_message": "Failed to update parameters",
                    "action_required": "Verify flow is deployed and parameters are valid",
                },
            )
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("Failed to update parameters for flow %s/%s", bucket_id, flow_id)
        raise HTTPException(
            status_code=500,
            detail={
                "error_type": "PARAMETER_UPDATE_FAILED",
                "user_message": f"Failed to update parameters for flow {flow_id}",
                "action_required": "Please try again or contact support",
            },
        ) from exc


@router.get("/{bucket_id}/{flow_id}/parameters", response_model=Dict)
async def get_flow_parameters(
    bucket_id: str = Path(..., description="Registry bucket ID"),
    flow_id: str = Path(..., description="Flow ID"),
    flow_service: FlowService = Depends(get_flow_service),
) -> Dict:
    """Get current flow parameters."""
    try:
        parameters = await flow_service.get_flow_parameters(bucket_id, flow_id)
        return parameters
    except Exception as exc:
        log.exception("Failed to get parameters for flow %s/%s", bucket_id, flow_id)
        raise HTTPException(
            status_code=500,
            detail={
                "error_type": "PARAMETER_GET_FAILED",
                "user_message": f"Failed to get parameters for flow {flow_id}",
                "action_required": "Please try again or contact support",
            },
        ) from exc