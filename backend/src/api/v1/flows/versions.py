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
        
        # Get versions from registry using IntegrationBridge
        try:
            registry_flow_id = version_control.get("flowId")
            bucket_id = version_control.get("bucketId")
            current_version = version_control.get("version", 1)
            
            # Use integration bridge to get versions from registry
            registry_comparison = await orchestrator.integration_bridge.compare_with_registry(flow_id)
            
            # Get all versions from registry
            registry_versions = await orchestrator.registry.flows.list_flow_versions(bucket_id, registry_flow_id)
            
            versions = []
            for registry_version in registry_versions:
                # Extract version number from different possible locations
                version_num = (
                    registry_version.get("version") or 
                    registry_version.get("snapshotMetadata", {}).get("version")
                )
                
                # Extract timestamp
                timestamp = (
                    registry_version.get("timestamp") or
                    registry_version.get("snapshotMetadata", {}).get("timestamp") or
                    registry_version.get("created_timestamp")
                )
                
                # Convert timestamp to ISO string if it's a number
                if isinstance(timestamp, (int, float)):
                    from datetime import datetime
                    timestamp = datetime.fromtimestamp(timestamp / 1000).isoformat() + "Z"
                elif not timestamp:
                    timestamp = "2024-01-01T00:00:00Z"
                
                # Extract author and comments
                author = (
                    registry_version.get("author") or
                    registry_version.get("snapshotMetadata", {}).get("author") or
                    "unknown"
                )
                
                comments = (
                    registry_version.get("comments") or
                    registry_version.get("snapshotMetadata", {}).get("comments") or
                    ""
                )
                
                if version_num:
                    versions.append(FlowVersion(
                        version=int(version_num),
                        created_at=timestamp,
                        author=author,
                        comments=comments,
                        is_current=(int(version_num) == current_version)
                    ))
            
            # Sort versions by version number (descending - newest first)
            versions.sort(key=lambda v: v.version, reverse=True)
            
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
        
        # Commit changes and create new version using IntegrationBridge
        try:
            sync_result = await orchestrator.integration_bridge.sync_flow_with_registry(
                process_group_id=flow_id,
                action="push"
            )
            
            if not sync_result.get("success"):
                raise HTTPException(
                    status_code=500,
                    detail={
                        "error_type": "VERSION_CREATE_FAILED",
                        "message": "Failed to create new version",
                        "details": sync_result.get("message", "Unknown error")
                    }
                )
            
            # Log the version creation
            audit_logger.log_flow_operation(
                operation="create_version",
                bucket_id=version_control.get("bucketId", "unknown"),
                flow_id=flow_id,
                details={
                    "previous_version": sync_result.get("previous_version"),
                    "new_version": sync_result.get("new_version"),
                    "action": version_data.action,
                    "comments": version_data.message,  # Use 'message' field from VersionRequest
                    "duration_ms": (time.time() - start_time) * 1000
                }
            )
            
            return VersionResponse(
                success=True,
                message=sync_result.get("message", "Version created successfully"),
                version=sync_result.get("new_version"),
                previous_version=sync_result.get("previous_version"),
                timestamp=int(time.time() * 1000)
            )
            
        except Exception as exc:
            log.error("Failed to create version via IntegrationBridge: %s", exc)
            raise HTTPException(
                status_code=500,
                detail={
                    "error_type": "VERSION_CREATE_ERROR",
                    "message": "Failed to create new version",
                    "details": str(exc)
                }
            ) from exc
        
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
        
        # Sync with latest version from Registry using IntegrationBridge
        try:
            sync_result = await orchestrator.integration_bridge.sync_flow_with_registry(
                process_group_id=flow_id,
                action="pull"
            )
            
            if not sync_result.get("success"):
                raise HTTPException(
                    status_code=500,
                    detail={
                        "error_type": "SYNC_FAILED",
                        "message": "Failed to sync with Registry",
                        "details": sync_result.get("message", "Unknown error")
                    }
                )
            
            return VersionResponse(
                success=True,
                message=sync_result.get("message", "Successfully synced with Registry"),
                version=sync_result.get("new_version", sync_result.get("current_version")),
                previous_version=sync_result.get("previous_version"),
                timestamp=int(time.time() * 1000)
            )
            
        except Exception as exc:
            log.error("Failed to sync with Registry: %s", exc)
            raise HTTPException(
                status_code=500,
                detail={
                    "error_type": "SYNC_ERROR",
                    "message": "Failed to sync with Registry",
                    "details": str(exc)
                }
            ) from exc
        
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
        
        # Revert local changes using NiFi version control
        try:
            revert_result = await orchestrator.nifi.version_control.revert_local_changes(
                process_group_id=flow_id
            )
            
            return VersionResponse(
                success=True,
                message="Successfully reverted local changes to match Registry version",
                version=overview.get("version_control_info", {}).get("version"),
                previous_version=overview.get("version_control_info", {}).get("version"),
                timestamp=int(time.time() * 1000)
            )
            
        except Exception as exc:
            log.error("Failed to revert local changes: %s", exc)
            raise HTTPException(
                status_code=500,
                detail={
                    "error_type": "REVERT_ERROR",
                    "message": "Failed to revert local changes",
                    "details": str(exc)
                }
            ) from exc
        
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


@router.get("/{version}", response_model=FlowVersion, status_code=HTTP_200_OK)
async def get_flow_version(
    version: int = Path(..., description="Version number"),
    flow_id: str = Path(..., description="Flow ID"),
    orchestrator: WorkflowOrchestrator = Depends(get_workflow_orchestrator),
) -> FlowVersion:
    """Get details for a specific version of a flow."""
    try:
        log.debug("Getting version %d details for flow: %s", version, flow_id)
        
        # Get all versions and find the requested one
        versions = await list_flow_versions(flow_id, orchestrator)
        
        for flow_version in versions:
            if flow_version.version == version:
                return flow_version
        
        # Version not found
        raise HTTPException(
            status_code=404,
            detail={
                "error_type": "VERSION_NOT_FOUND",
                "message": f"Version {version} not found for flow {flow_id}",
                "available_versions": [v.version for v in versions]
            }
        )
        
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("Failed to get version %d for flow %s", version, flow_id)
        raise HTTPException(
            status_code=500,
            detail={
                "error_type": "VERSION_GET_ERROR",
                "message": "Failed to get flow version details",
                "details": str(exc)
            }
        ) from exc


@router.put("/{version}", response_model=VersionResponse, status_code=HTTP_200_OK)
async def switch_to_version(
    version: int = Path(..., description="Version number to switch to"),
    flow_id: str = Path(..., description="Flow ID"),
    orchestrator: WorkflowOrchestrator = Depends(get_workflow_orchestrator),
) -> VersionResponse:
    """Switch flow to a specific version."""
    try:
        start_time = time.time()
        log.info("Switching flow %s to version %d", flow_id, version)
        
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
        
        current_version = version_control.get("version", 1)
        
        # Check if we're already on the requested version
        if current_version == version:
            return VersionResponse(
                success=True,
                message=f"Already on version {version}",
                version=version,
                previous_version=version,
                timestamp=int(time.time() * 1000)
            )
        
        # Verify the target version exists
        versions = await list_flow_versions(flow_id, orchestrator)
        available_versions = [v.version for v in versions]
        
        if version not in available_versions:
            raise HTTPException(
                status_code=404,
                detail={
                    "error_type": "VERSION_NOT_FOUND",
                    "message": f"Version {version} not found for flow {flow_id}",
                    "available_versions": available_versions
                }
            )
        
        # Switch to the target version using NiFi version control
        try:
            switch_result = await orchestrator.nifi.version_control.update_process_group_version(
                process_group_id=flow_id,
                version=version
            )
            
            # Log the version switch
            audit_logger.log_flow_operation(
                operation="switch_version",
                bucket_id=version_control.get("bucketId", "unknown"),
                flow_id=flow_id,
                details={
                    "previous_version": current_version,
                    "new_version": version,
                    "duration_ms": (time.time() - start_time) * 1000
                }
            )
            
            return VersionResponse(
                success=True,
                message=f"Successfully switched to version {version}",
                version=version,
                previous_version=current_version,
                timestamp=int(time.time() * 1000)
            )
            
        except Exception as exc:
            log.error("Failed to switch to version %d: %s", version, exc)
            raise HTTPException(
                status_code=500,
                detail={
                    "error_type": "VERSION_SWITCH_ERROR",
                    "message": f"Failed to switch to version {version}",
                    "details": str(exc)
                }
            ) from exc
        
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("Failed to switch flow %s to version %d", flow_id, version)
        raise HTTPException(
            status_code=500,
            detail={
                "error_type": "VERSION_SWITCH_ERROR",
                "message": "Failed to switch flow version",
                "details": str(exc)
            }
        ) from exc


@router.delete("/{version}", response_model=VersionResponse, status_code=HTTP_200_OK)
async def delete_flow_version(
    version: int = Path(..., description="Version number to delete"),
    flow_id: str = Path(..., description="Flow ID"),
    orchestrator: WorkflowOrchestrator = Depends(get_workflow_orchestrator),
) -> VersionResponse:
    """Delete a specific version of a flow (NOTE: Not supported by NiFi Registry)."""
    try:
        log.info("Attempting to delete version %d of flow %s", version, flow_id)
        
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
                    "message": "Flow is not under version control"
                }
            )
        
        # NiFi Registry doesn't support individual version deletion
        raise HTTPException(
            status_code=405,
            detail={
                "error_type": "OPERATION_NOT_SUPPORTED",
                "message": "Individual version deletion is not supported by NiFi Registry",
                "explanation": "NiFi Registry maintains immutable version history. You can only delete the entire flow (all versions) or switch to a different version.",
                "alternatives": [
                    f"Switch to a different version using PUT /flows/{flow_id}/versions/{{version}}",
                    f"Delete the entire flow using DELETE /flows/{flow_id}"
                ]
            }
        )
        
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("Error during version deletion attempt for flow %s version %d", flow_id, version)
        raise HTTPException(
            status_code=500,
            detail={
                "error_type": "VERSION_DELETE_ERROR",
                "message": "Error during version deletion attempt",
                "details": str(exc)
            }
        ) from exc