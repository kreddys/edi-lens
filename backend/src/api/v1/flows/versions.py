"""Flow version control operations."""

from __future__ import annotations

import time
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Path
from starlette.status import HTTP_200_OK

from src.api.dependencies import get_workflow_orchestrator
from src.core.logging import get_logger, audit_logger
from src.models.v1.flows import (
    VersionRequest,
    VersionResponse,
    FlowVersion
)
from src.services.workflow_orchestrator import WorkflowOrchestrator

log = get_logger(__name__)

router = APIRouter(prefix="/flows/{flow_id}/versions", tags=["flow-versions"])


@router.get("/", response_model=List[FlowVersion], status_code=HTTP_200_OK)
async def list_flow_versions(
    flow_id: str = Path(..., description="Flow ID"),
    orchestrator: WorkflowOrchestrator = Depends(get_workflow_orchestrator),
) -> List[FlowVersion]:
    """List all versions of a flow."""
    try:
        log.debug("Listing versions for flow: %s", flow_id)
        
        # Check if flow exists and has version control
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
        
        version_control = overview.get("version_control_info", {})
        if not version_control or not version_control.get("flowId"):
            raise HTTPException(
                status_code=400,
                detail={
                    "error_type": "NO_VERSION_CONTROL",
                    "message": "Flow is not under version control",
                    "action_required": "Enable version control for this flow first"
                }
            )
        
        # Get versions from registry
        registry_flow_id = version_control.get("flowId")
        bucket_id = version_control.get("bucketId")
        current_version = version_control.get("version", 1)
        
        try:
            # For now, return a single version entry since we don't have full registry integration
            versions = [
                FlowVersion(
                    version=current_version,
                    created_at=overview.get("created_at", "2024-01-01T00:00:00Z"),
                    author=version_control.get("author", "system"),
                    comments=version_control.get("comments", ""),
                    is_current=True
                )
            ]
            
            return versions
            
        except Exception as exc:
            log.warning("Failed to get versions from registry: %s", exc)
            # Return minimal version info
            return [
                FlowVersion(
                    version=current_version,
                    created_at="2024-01-01T00:00:00Z",
                    author="unknown", 
                    comments="Current version",
                    is_current=True
                )
            ]
            
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("Failed to list versions for flow %s", flow_id)
        raise HTTPException(
            status_code=500,
            detail={
                "error_type": "VERSION_LIST_ERROR",
                "message": "Failed to list flow versions",
                "details": str(exc)
            }
        ) from exc


@router.post("/", response_model=VersionResponse, status_code=HTTP_200_OK)
async def create_flow_version(
    version_data: VersionRequest,
    flow_id: str = Path(..., description="Flow ID"),
    orchestrator: WorkflowOrchestrator = Depends(get_workflow_orchestrator),
) -> VersionResponse:
    """Create a new version of a flow (commit changes)."""
    try:
        start_time = time.time()
        log.info("Creating new version for flow %s: action=%s", flow_id, version_data.action)
        
        if version_data.action != "commit":
            raise HTTPException(
                status_code=400,
                detail={
                    "error_type": "INVALID_ACTION",
                    "message": "Only 'commit' action is supported for version creation"
                }
            )
        
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
        
        # Check version control
        version_control = overview.get("version_control_info", {})
        if not version_control or not version_control.get("flowId"):
            raise HTTPException(
                status_code=400,
                detail={
                    "error_type": "NO_VERSION_CONTROL",
                    "message": "Flow is not under version control",
                    "action_required": "Enable version control for this flow first"
                }
            )
        
        # For now, return not implemented for version operations
        raise HTTPException(
            status_code=501,
            detail={
                "error_type": "NOT_IMPLEMENTED",
                "message": "Version control operations are not fully implemented",
                "action_required": "Use the legacy version control endpoints"
            }
        )
        
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("Failed to create version for flow %s", flow_id)
        raise HTTPException(
            status_code=500,
            detail={
                "error_type": "VERSION_CREATE_ERROR",
                "message": "Failed to create flow version",
                "details": str(exc)
            }
        ) from exc


@router.get("/latest", response_model=FlowVersion, status_code=HTTP_200_OK)
async def get_latest_version(
    flow_id: str = Path(..., description="Flow ID"),
    orchestrator: WorkflowOrchestrator = Depends(get_workflow_orchestrator),
) -> FlowVersion:
    """Get the latest version of a flow."""
    try:
        log.debug("Getting latest version for flow: %s", flow_id)
        
        # Get all versions and return the latest
        versions = await list_flow_versions(flow_id, orchestrator)
        
        if not versions:
            raise HTTPException(
                status_code=404,
                detail={
                    "error_type": "NO_VERSIONS",
                    "message": "No versions found for this flow"
                }
            )
        
        # Return the version with highest version number
        latest = max(versions, key=lambda v: v.version)
        return latest
        
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("Failed to get latest version for flow %s", flow_id)
        raise HTTPException(
            status_code=500,
            detail={
                "error_type": "LATEST_VERSION_ERROR",
                "message": "Failed to get latest flow version", 
                "details": str(exc)
            }
        ) from exc


@router.post("/sync", response_model=VersionResponse, status_code=HTTP_200_OK)
async def sync_with_registry(
    flow_id: str = Path(..., description="Flow ID"),
    orchestrator: WorkflowOrchestrator = Depends(get_workflow_orchestrator),
) -> VersionResponse:
    """Sync flow with latest version from registry."""
    try:
        log.info("Syncing flow %s with registry", flow_id)
        
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
        
        # For now, return not implemented
        raise HTTPException(
            status_code=501,
            detail={
                "error_type": "NOT_IMPLEMENTED",
                "message": "Registry sync is not fully implemented",
                "action_required": "Use the legacy version control endpoints"
            }
        )
        
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("Failed to sync flow %s with registry", flow_id)
        raise HTTPException(
            status_code=500,
            detail={
                "error_type": "SYNC_ERROR",
                "message": "Failed to sync with registry",
                "details": str(exc)
            }
        ) from exc


@router.post("/revert", response_model=VersionResponse, status_code=HTTP_200_OK)
async def revert_changes(
    flow_id: str = Path(..., description="Flow ID"),
    orchestrator: WorkflowOrchestrator = Depends(get_workflow_orchestrator),
) -> VersionResponse:
    """Revert local changes to match registry version."""
    try:
        log.info("Reverting changes for flow %s", flow_id)
        
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
        
        # For now, return not implemented
        raise HTTPException(
            status_code=501,
            detail={
                "error_type": "NOT_IMPLEMENTED",
                "message": "Change reversion is not fully implemented",
                "action_required": "Use the legacy version control endpoints"
            }
        )
        
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("Failed to revert changes for flow %s", flow_id)
        raise HTTPException(
            status_code=500,
            detail={
                "error_type": "REVERT_ERROR",
                "message": "Failed to revert changes",
                "details": str(exc)
            }
        ) from exc