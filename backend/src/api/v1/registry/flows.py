"""Registry flow operations."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Path
from starlette.status import HTTP_200_OK

from src.api.dependencies import get_workflow_orchestrator
from src.core.logging import get_logger
from src.models.v1.registry import (
    RegistryFlowResponse,
    RegistryFlowVersion,
    RegistryFlowVersionListResponse,
    RegistryFlowListResponse
)
from src.services.workflow_orchestrator import WorkflowOrchestrator

log = get_logger(__name__)

router = APIRouter(prefix="/registry/buckets/{bucket_id}/flows", tags=["registry-flows"])

# Add a separate router for general registry flows
general_router = APIRouter(prefix="/registry/flows", tags=["registry-flows-general"])


@general_router.get("/", response_model=RegistryFlowListResponse, status_code=HTTP_200_OK)
async def list_all_registry_flows(
    orchestrator: WorkflowOrchestrator = Depends(get_workflow_orchestrator),
) -> RegistryFlowListResponse:
    """List all flows across all registry buckets."""
    try:
        log.debug("Listing all registry flows")
        
        # Get all buckets first
        buckets = await orchestrator.registry_bucket_mgmt.list_buckets()
        
        all_flows = []
        for bucket in buckets:
            bucket_id = bucket.get("bucket_id")
            if not bucket_id:
                continue
                
            try:
                # Get flows from this bucket
                flows_data = await orchestrator.registry_flow_mgmt.list_flows_in_bucket(bucket_id)
                
                for flow_data in flows_data:
                    flow_response = RegistryFlowResponse(
                        id=flow_data.get("flow_id", ""),
                        name=flow_data.get("name", ""),  # Fixed: was "flow_name"
                        description=flow_data.get("description", ""),
                        bucket_id=bucket_id,
                        version_count=flow_data.get("version_count", 0),
                        latest_version=flow_data.get("latest_version"),
                        created_at=flow_data.get("created_timestamp", "2024-01-01T00:00:00Z"),
                        updated_at=flow_data.get("modified_timestamp"),
                        permissions=flow_data.get("permissions", {})
                    )
                    all_flows.append(flow_response)
            except Exception as e:
                log.warning("Failed to get flows from bucket %s: %s", bucket_id, e)
                # Continue with other buckets
                continue
        
        response = RegistryFlowListResponse(
            flows=all_flows,
            total=len(all_flows)
        )
        
        log.debug("Found %d registry flows across all buckets", len(all_flows))
        return response
        
    except Exception as exc:
        log.exception("Failed to list all registry flows")
        raise HTTPException(
            status_code=500,
            detail={
                "error_type": "REGISTRY_FLOWS_LIST_FAILED",
                "message": "Failed to retrieve all registry flows",
                "details": str(exc)
            }
        ) from exc


@router.get("/", response_model=List[RegistryFlowResponse], status_code=HTTP_200_OK)
async def list_registry_flows(
    bucket_id: str = Path(..., description="Bucket ID"),
    orchestrator: WorkflowOrchestrator = Depends(get_workflow_orchestrator),
) -> List[RegistryFlowResponse]:
    """List all flows in a registry bucket."""
    try:
        log.debug("Listing flows in registry bucket: %s", bucket_id)
        
        # Get flows from registry
        flows_data = await orchestrator.registry_flow_mgmt.list_flows_in_bucket(bucket_id)
        
        flows = []
        for flow_data in flows_data:
            flow_response = RegistryFlowResponse(
                id=flow_data.get("flow_id", ""),
                name=flow_data.get("name", ""),  # Fixed: was "flow_name"
                description=flow_data.get("description", ""),
                bucket_id=bucket_id,
                version_count=flow_data.get("version_count", 0),
                latest_version=flow_data.get("latest_version"),
                created_at=flow_data.get("created_timestamp", "2024-01-01T00:00:00Z"),
                updated_at=flow_data.get("modified_timestamp"),
                permissions=flow_data.get("permissions", {})
            )
            flows.append(flow_response)
        
        log.debug("Found %d flows in bucket %s", len(flows), bucket_id)
        return flows
        
    except Exception as exc:
        log.exception("Failed to list flows in bucket %s", bucket_id)
        raise HTTPException(
            status_code=500,
            detail={
                "error_type": "REGISTRY_FLOWS_LIST_FAILED",
                "message": "Failed to retrieve registry flows",
                "details": str(exc)
            }
        ) from exc


@router.get("/{flow_id}", response_model=RegistryFlowResponse, status_code=HTTP_200_OK)
async def get_registry_flow(
    bucket_id: str = Path(..., description="Bucket ID"),
    flow_id: str = Path(..., description="Flow ID"),
    orchestrator: WorkflowOrchestrator = Depends(get_workflow_orchestrator),
) -> RegistryFlowResponse:
    """Get a specific registry flow."""
    try:
        log.debug("Getting registry flow: %s in bucket %s", flow_id, bucket_id)
        
        # Get flow from registry
        flow_data = await orchestrator.registry_flow_mgmt.get_flow(bucket_id, flow_id)
        
        if not flow_data:
            raise HTTPException(
                status_code=404,
                detail={
                    "error_type": "REGISTRY_FLOW_NOT_FOUND",
                    "message": f"Flow {flow_id} not found in bucket {bucket_id}"
                }
            )
        
        flow_response = RegistryFlowResponse(
            id=flow_id,
            name=flow_data.get("name", ""),  # Fixed: was "flow_name"
            description=flow_data.get("description", ""),
            bucket_id=bucket_id,
            version_count=flow_data.get("version_count", 0),
            latest_version=flow_data.get("latest_version"),
            created_at=flow_data.get("created_timestamp", "2024-01-01T00:00:00Z"),
            updated_at=flow_data.get("modified_timestamp"),
            permissions=flow_data.get("permissions", {})
        )
        
        return flow_response
        
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("Failed to get registry flow %s in bucket %s", flow_id, bucket_id)
        raise HTTPException(
            status_code=500,
            detail={
                "error_type": "REGISTRY_FLOW_GET_FAILED",
                "message": "Failed to retrieve registry flow",
                "details": str(exc)
            }
        ) from exc


@router.get("/{flow_id}/versions", response_model=RegistryFlowVersionListResponse, status_code=HTTP_200_OK)
async def list_registry_flow_versions(
    bucket_id: str = Path(..., description="Bucket ID"),
    flow_id: str = Path(..., description="Flow ID"),
    orchestrator: WorkflowOrchestrator = Depends(get_workflow_orchestrator),
) -> RegistryFlowVersionListResponse:
    """List all versions of a registry flow."""
    try:
        log.debug("Listing versions for registry flow: %s in bucket %s", flow_id, bucket_id)
        
        # Get versions from registry
        versions_data = await orchestrator.registry_version_mgmt.list_flow_versions(bucket_id, flow_id)
        
        versions = []
        for version_data in versions_data:
            version = RegistryFlowVersion(
                version=version_data.get("version", 0),
                flow_id=flow_id,
                bucket_id=bucket_id,
                comments=version_data.get("comments", ""),
                author=version_data.get("author"),
                created_at=version_data.get("created_timestamp", "2024-01-01T00:00:00Z"),
                snapshot_metadata=version_data.get("snapshot_metadata", {}),
                flow_contents=version_data.get("flow_contents", {})
            )
            versions.append(version)
        
        response = RegistryFlowVersionListResponse(
            versions=versions,
            flow_id=flow_id,
            bucket_id=bucket_id,
            total=len(versions)
        )
        
        log.debug("Found %d versions for flow %s", len(versions), flow_id)
        return response
        
    except Exception as exc:
        log.exception("Failed to list versions for registry flow %s in bucket %s", flow_id, bucket_id)
        raise HTTPException(
            status_code=500,
            detail={
                "error_type": "REGISTRY_VERSIONS_LIST_FAILED",
                "message": "Failed to retrieve registry flow versions",
                "details": str(exc)
            }
        ) from exc