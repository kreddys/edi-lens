"""Core flow CRUD operations."""

from __future__ import annotations

import time
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Path
from starlette.status import HTTP_200_OK, HTTP_201_CREATED, HTTP_204_NO_CONTENT

from src.api.dependencies import get_workflow_orchestrator
from src.core.logging import get_logger, audit_logger
from src.models.v1.flows import (
    FlowCreate,
    FlowUpdate, 
    FlowResponse,
    FlowListResponse,
    FlowStatus,
    DeploymentStatus
)
from src.services.workflow_orchestrator import WorkflowOrchestrator

log = get_logger(__name__)

router = APIRouter(prefix="/flows", tags=["flows"])


@router.get("/", response_model=FlowListResponse, status_code=HTTP_200_OK)
async def list_flows(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(50, ge=1, le=100, description="Page size"),
    status: Optional[FlowStatus] = Query(None, description="Filter by flow status"),
    orchestrator: WorkflowOrchestrator = Depends(get_workflow_orchestrator),
) -> FlowListResponse:
    """List all flows with pagination and filtering."""
    try:
        log.debug("Listing flows: page=%d, size=%d, status=%s", page, size, status)
        
        # Get flows from NiFi (these are the deployed flows)
        nifi_flows = await orchestrator.nifi_flow_mgmt.list_flows()
        
        flows_with_status = []
        for flow in nifi_flows:
            process_group_id = flow.get("process_group_id") or flow.get("id")
            flow_name = flow.get("name") or flow.get("component", {}).get("name", "Unknown Flow")
            
            if process_group_id:
                try:
                    # Get detailed status for each flow
                    overview = await orchestrator.get_flow_overview(process_group_id)
                    flow_status = overview.get("flow_status", {}) or {}
                    
                    # Map to new response format
                    overall_status = flow_status.get("overall_status", "unknown")
                    mapped_status = FlowStatus.RUNNING if overall_status == "running" else \
                                  FlowStatus.STOPPED if overall_status == "stopped" else \
                                  FlowStatus.INVALID if overall_status == "invalid" else \
                                  FlowStatus.UNKNOWN
                    
                    # Skip if filtering by status and doesn't match
                    if status and mapped_status != status:
                        continue
                        
                    flow_response = FlowResponse(
                        id=process_group_id,
                        name=flow_name,
                        description=flow.get("component", {}).get("comments", ""),
                        definition=None,  # Not included in list for performance
                        parameters={},
                        status=mapped_status,
                        deployment_status=DeploymentStatus.DEPLOYED,
                        processor_count=flow_status.get("total_processors", 0),
                        running_count=flow_status.get("running_processors", 0),
                        stopped_count=flow_status.get("stopped_processors", 0),
                        invalid_count=flow_status.get("invalid_processors", 0),
                        version_control=overview.get("version_control_info")
                    )
                    flows_with_status.append(flow_response)
                    
                except Exception as exc:
                    log.warning("Failed to get status for flow %s: %s", process_group_id, exc)
                    # Include flow even if status retrieval fails
                    flow_response = FlowResponse(
                        id=process_group_id,
                        name=flow_name,
                        description="",
                        definition=None,
                        parameters={},
                        status=FlowStatus.UNKNOWN,
                        deployment_status=DeploymentStatus.DEPLOYED,
                        processor_count=0,
                        running_count=0,
                        stopped_count=0,
                        invalid_count=0
                    )
                    flows_with_status.append(flow_response)
        
        # Apply pagination
        total = len(flows_with_status)
        start_idx = (page - 1) * size
        end_idx = start_idx + size
        paginated_flows = flows_with_status[start_idx:end_idx]
        
        log.debug("Found %d flows (page %d/%d)", len(paginated_flows), page, (total + size - 1) // size)
        
        return FlowListResponse(
            flows=paginated_flows,
            total=total,
            page=page,
            size=size
        )
        
    except Exception as exc:
        log.exception("Failed to list flows")
        raise HTTPException(
            status_code=500,
            detail={
                "error_type": "FLOWS_LIST_FAILED",
                "message": "Failed to retrieve flows",
                "details": str(exc)
            }
        ) from exc


@router.post("/", response_model=FlowResponse, status_code=HTTP_201_CREATED)
async def create_flow(
    flow_data: FlowCreate,
    orchestrator: WorkflowOrchestrator = Depends(get_workflow_orchestrator),
) -> FlowResponse:
    """Create a new flow."""
    try:
        start_time = time.time()
        log.info("Creating flow '%s'", flow_data.name)
        
        # Convert to legacy format for now
        from src.models.flow_models import DeployAndStoreFlowRequest, FlowDefinition as LegacyFlowDefinition
        
        legacy_request = DeployAndStoreFlowRequest(
            bucket_id=flow_data.bucket_id or "default-bucket", 
            flow_definition=LegacyFlowDefinition(
                name=flow_data.name,
                description=flow_data.description,
                processors=flow_data.definition.processors if flow_data.definition else [],
                connections=flow_data.definition.connections if flow_data.definition else [],
                process_groups=flow_data.definition.process_groups if flow_data.definition else []
            ),
            parameters=flow_data.parameters,
            parent_group_id=flow_data.parent_group_id,
            flow_name=flow_data.name,
            flow_description=flow_data.description
        )
        
        # Execute deployment workflow
        result = await orchestrator.execute_deployment_first_workflow(legacy_request)
        
        if result.get("success"):
            process_group_id = result.get("process_group_id")
            
            # Get flow details for response
            overview = await orchestrator.get_flow_overview(process_group_id)
            flow_status = overview.get("flow_status", {}) or {}
            
            overall_status = flow_status.get("overall_status", "stopped")
            mapped_status = FlowStatus.RUNNING if overall_status == "running" else \
                          FlowStatus.STOPPED if overall_status == "stopped" else \
                          FlowStatus.INVALID if overall_status == "invalid" else \
                          FlowStatus.UNKNOWN
                          
            response = FlowResponse(
                id=process_group_id,
                name=flow_data.name,
                description=flow_data.description,
                definition=flow_data.definition,
                parameters=flow_data.parameters,
                status=mapped_status,
                deployment_status=DeploymentStatus.DEPLOYED,
                processor_count=flow_status.get("total_processors", 0),
                running_count=flow_status.get("running_processors", 0),
                stopped_count=flow_status.get("stopped_processors", 0),
                invalid_count=flow_status.get("invalid_processors", 0),
                version_control=overview.get("version_control_info")
            )
            
            duration = time.time() - start_time
            log.info("Successfully created flow '%s' in %.2fs", flow_data.name, duration)
            audit_logger.log_user_action("flow_created", {
                "flow_id": process_group_id,
                "flow_name": flow_data.name,
                "duration_ms": duration * 1000
            })
            
            return response
        else:
            raise HTTPException(
                status_code=400,
                detail={
                    "error_type": "FLOW_CREATION_FAILED",
                    "message": result.get("message", "Flow creation failed"),
                    "details": result.get("details", {})
                }
            )
            
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("Failed to create flow '%s'", flow_data.name)
        raise HTTPException(
            status_code=500,
            detail={
                "error_type": "FLOW_CREATION_ERROR",
                "message": "Internal error during flow creation",
                "details": str(exc)
            }
        ) from exc


@router.get("/{flow_id}", response_model=FlowResponse, status_code=HTTP_200_OK)
async def get_flow(
    flow_id: str = Path(..., description="Flow ID"),
    orchestrator: WorkflowOrchestrator = Depends(get_workflow_orchestrator),
) -> FlowResponse:
    """Get a specific flow by ID."""
    try:
        log.debug("Getting flow: %s", flow_id)
        
        # Get flow overview which includes all details
        overview = await orchestrator.get_flow_overview(flow_id)
        
        if not overview:
            raise HTTPException(
                status_code=404,
                detail={
                    "error_type": "FLOW_NOT_FOUND",
                    "message": f"Flow {flow_id} not found"
                }
            )
        
        flow_status = overview.get("flow_status", {}) or {}
        flow_info = overview.get("flow_info", {}) or {}
        
        overall_status = flow_status.get("overall_status", "unknown")
        mapped_status = FlowStatus.RUNNING if overall_status == "running" else \
                      FlowStatus.STOPPED if overall_status == "stopped" else \
                      FlowStatus.INVALID if overall_status == "invalid" else \
                      FlowStatus.UNKNOWN
        
        response = FlowResponse(
            id=flow_id,
            name=flow_info.get("name", "Unknown Flow"),
            description=flow_info.get("component", {}).get("comments", ""),
            definition=None,  # TODO: Extract from NiFi if needed
            parameters={},  # TODO: Extract from parameter context
            status=mapped_status,
            deployment_status=DeploymentStatus.DEPLOYED,
            processor_count=flow_status.get("total_processors", 0),
            running_count=flow_status.get("running_processors", 0),
            stopped_count=flow_status.get("stopped_processors", 0),
            invalid_count=flow_status.get("invalid_processors", 0),
            version_control=overview.get("version_control_info")
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("Failed to get flow %s", flow_id)
        raise HTTPException(
            status_code=500,
            detail={
                "error_type": "FLOW_GET_ERROR",
                "message": "Failed to retrieve flow",
                "details": str(exc)
            }
        ) from exc


@router.put("/{flow_id}", response_model=FlowResponse, status_code=HTTP_200_OK)
async def update_flow(
    flow_data: FlowUpdate,
    flow_id: str = Path(..., description="Flow ID"),
    orchestrator: WorkflowOrchestrator = Depends(get_workflow_orchestrator),
) -> FlowResponse:
    """Update an existing flow."""
    try:
        log.info("Updating flow: %s", flow_id)
        
        # For now, this is a placeholder - would need to implement flow updates
        # This would involve updating the NiFi process group and potentially the Registry
        
        raise HTTPException(
            status_code=501,
            detail={
                "error_type": "NOT_IMPLEMENTED",
                "message": "Flow updates are not yet implemented",
                "action_required": "Use version control operations or redeploy the flow"
            }
        )
        
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("Failed to update flow %s", flow_id)
        raise HTTPException(
            status_code=500,
            detail={
                "error_type": "FLOW_UPDATE_ERROR", 
                "message": "Failed to update flow",
                "details": str(exc)
            }
        ) from exc


@router.delete("/{flow_id}", status_code=HTTP_204_NO_CONTENT)
async def delete_flow(
    flow_id: str = Path(..., description="Flow ID"),
    force: bool = Query(False, description="Force deletion even if flow is running"),
    orchestrator: WorkflowOrchestrator = Depends(get_workflow_orchestrator),
):
    """Delete a flow."""
    try:
        log.info("Deleting flow: %s (force=%s)", flow_id, force)
        
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
        
        # Check if flow is running and force is not set
        flow_status = overview.get("flow_status", {}) or {}
        if not force and flow_status.get("overall_status") == "running":
            raise HTTPException(
                status_code=400,
                detail={
                    "error_type": "FLOW_RUNNING",
                    "message": "Cannot delete running flow without force=true",
                    "action_required": "Stop the flow first or use force=true"
                }
            )
        
        # Delete the flow
        await orchestrator.nifi_flow_mgmt.delete_flow(flow_id)
        
        log.info("Successfully deleted flow: %s", flow_id)
        audit_logger.log_user_action("flow_deleted", {
            "flow_id": flow_id,
            "force": force
        })
        
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("Failed to delete flow %s", flow_id)
        raise HTTPException(
            status_code=500,
            detail={
                "error_type": "FLOW_DELETE_ERROR",
                "message": "Failed to delete flow",
                "details": str(exc)
            }
        ) from exc