"""Registry bucket operations."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Path
from starlette.status import HTTP_200_OK, HTTP_201_CREATED, HTTP_204_NO_CONTENT

from src.api.dependencies import get_workflow_orchestrator
from src.core.logging import get_logger, audit_logger
from src.models.v1.registry import (
    BucketCreate,
    BucketUpdate,
    BucketResponse
)
from src.services.workflow_orchestrator import WorkflowOrchestrator

log = get_logger(__name__)

router = APIRouter(prefix="/registry/buckets", tags=["registry-buckets"])


@router.get("/", response_model=List[BucketResponse], status_code=HTTP_200_OK)
async def list_buckets(
    orchestrator: WorkflowOrchestrator = Depends(get_workflow_orchestrator),
) -> List[BucketResponse]:
    """List all registry buckets."""
    try:
        log.debug("Listing registry buckets")
        
        # Get buckets from registry
        buckets_data = await orchestrator.registry_bucket_mgmt.list_buckets()
        
        buckets = []
        for bucket_data in buckets_data:
            bucket_response = BucketResponse(
                id=bucket_data.get("bucket_id", ""),
                name=bucket_data.get("bucket_name", ""),
                description=bucket_data.get("description", ""),
                allow_public_read=bucket_data.get("allow_public_read", False),
                created_at=bucket_data.get("created_timestamp", "2024-01-01T00:00:00Z"),
                updated_at=bucket_data.get("modified_timestamp"),
                flow_count=0,  # Not tracked in current format
                permissions=bucket_data.get("permissions", {}),
                revision=bucket_data.get("revision", {})
            )
            buckets.append(bucket_response)
        
        log.debug("Found %d registry buckets", len(buckets))
        return buckets
        
    except Exception as exc:
        log.exception("Failed to list registry buckets")
        raise HTTPException(
            status_code=500,
            detail={
                "error_type": "BUCKET_LIST_FAILED",
                "message": "Failed to retrieve registry buckets",
                "details": str(exc)
            }
        ) from exc


@router.post("/", response_model=BucketResponse, status_code=HTTP_201_CREATED)
async def create_bucket(
    bucket_data: BucketCreate,
    orchestrator: WorkflowOrchestrator = Depends(get_workflow_orchestrator),
) -> BucketResponse:
    """Create a new registry bucket."""
    try:
        log.info("Creating registry bucket: %s", bucket_data.name)
        
        # Create bucket in registry
        result = await orchestrator.registry_bucket_mgmt.create_bucket(
            name=bucket_data.name,
            description=bucket_data.description
        )
        
        if result.get("success"):
            # The service returns normalized bucket data at the top level
            bucket_response = BucketResponse(
                id=result.get("bucket_id", ""),
                name=bucket_data.name,
                description=bucket_data.description,
                allow_public_read=bucket_data.allow_public_read,
                created_at=result.get("created_timestamp"),
                flow_count=0,
                permissions=result.get("permissions", {}),
                revision=result.get("revision", {})
            )
            
            log.info("Successfully created bucket: %s", bucket_data.name)
            audit_logger.log_system_event("bucket_created", {
                "bucket_id": bucket_response.id,
                "bucket_name": bucket_data.name
            })
            
            return bucket_response
        else:
            raise HTTPException(
                status_code=400,
                detail={
                    "error_type": "BUCKET_CREATION_FAILED",
                    "message": result.get("message", "Failed to create bucket"),
                    "details": result.get("details", {})
                }
            )
            
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("Failed to create bucket %s", bucket_data.name)
        raise HTTPException(
            status_code=500,
            detail={
                "error_type": "BUCKET_CREATION_ERROR",
                "message": "Internal error during bucket creation",
                "details": str(exc)
            }
        ) from exc


@router.get("/{bucket_id}", response_model=BucketResponse, status_code=HTTP_200_OK)
async def get_bucket(
    bucket_id: str = Path(..., description="Bucket ID"),
    orchestrator: WorkflowOrchestrator = Depends(get_workflow_orchestrator),
) -> BucketResponse:
    """Get a specific registry bucket by ID."""
    try:
        log.debug("Getting registry bucket: %s", bucket_id)
        
        # Get bucket from registry
        bucket_data = await orchestrator.registry_bucket_mgmt.get_bucket(bucket_id)
        
        if not bucket_data:
            raise HTTPException(
                status_code=404,
                detail={
                    "error_type": "BUCKET_NOT_FOUND",
                    "message": f"Bucket {bucket_id} not found"
                }
            )
        
        bucket_response = BucketResponse(
            id=bucket_data.get("bucket_id", bucket_id),
            name=bucket_data.get("bucket_name", ""),
            description=bucket_data.get("description", ""),
            allow_public_read=bucket_data.get("allow_public_read", False),
            created_at=bucket_data.get("created_timestamp", "2024-01-01T00:00:00Z"),
            updated_at=bucket_data.get("modified_timestamp"),
            flow_count=0,  # Not tracked in current format
            permissions=bucket_data.get("permissions", {}),
            revision=bucket_data.get("revision", {})
        )
        
        return bucket_response
        
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("Failed to get bucket %s", bucket_id)
        raise HTTPException(
            status_code=500,
            detail={
                "error_type": "BUCKET_GET_FAILED",
                "message": "Failed to retrieve bucket",
                "details": str(exc)
            }
        ) from exc


@router.delete("/{bucket_id}", status_code=HTTP_204_NO_CONTENT)
async def delete_bucket(
    bucket_id: str = Path(..., description="Bucket ID"),
    orchestrator: WorkflowOrchestrator = Depends(get_workflow_orchestrator),
):
    """Delete a registry bucket."""
    try:
        log.info("Deleting registry bucket: %s", bucket_id)
        
        # Check if bucket exists
        bucket_data = await orchestrator.registry_bucket_mgmt.get_bucket(bucket_id)
        if not bucket_data:
            raise HTTPException(
                status_code=404,
                detail={
                    "error_type": "BUCKET_NOT_FOUND",
                    "message": f"Bucket {bucket_id} not found"
                }
            )
        
        # For now, return not implemented since deletion needs careful handling
        raise HTTPException(
            status_code=501,
            detail={
                "error_type": "NOT_IMPLEMENTED",
                "message": "Bucket deletion is not yet implemented",
                "action_required": "Contact administrator to delete buckets"
            }
        )
        
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("Failed to delete bucket %s", bucket_id)
        raise HTTPException(
            status_code=500,
            detail={
                "error_type": "BUCKET_DELETE_ERROR",
                "message": "Failed to delete bucket",
                "details": str(exc)
            }
        ) from exc