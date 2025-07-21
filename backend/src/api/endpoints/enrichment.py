# FILE: backend/src/api/endpoints/enrichment.py
import logging
import uuid
import json
import jsonpatch # <-- Add this import
from pathlib import Path # <-- Add this import
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks

from src.core.auth import require_permission, AuthContext
from src.core.config import settings
from src.api import schemas
from src.services.enrichment_service import job_storage, run_enrichment_analysis

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post(
    "/enrichment/analyze",
    response_model=schemas.EnrichmentJobStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start Schema Enrichment Analysis",
    description="Kicks off a background job to analyze an EDI schema segment using AI agents."
)
async def start_analysis(
    request: schemas.EnrichmentAnalysisRequest,
    background_tasks: BackgroundTasks,
    auth: AuthContext = Depends(require_permission("superuser")) # This is a privileged action
):
    job_id = str(uuid.uuid4())
    
    # Add the job to our background task runner
    background_tasks.add_task(
        run_enrichment_analysis,
        job_id,
        request.schema_name,
        request.segment_id,
        request.context_id
    )
    
    # Immediately return the job ID to the client
    return schemas.EnrichmentJobStartResponse(job_id=job_id)

@router.get(
    "/enrichment/status/{job_id}",
    response_model=schemas.EnrichmentJobStatusResponse,
    summary="Get Enrichment Analysis Status",
    description="Poll this endpoint with a job ID to get the status and result of an analysis."
)
async def get_analysis_status(
    job_id: str,
    auth: AuthContext = Depends(require_permission("superuser"))
):
    job = job_storage.get(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")

    return schemas.EnrichmentJobStatusResponse(job_id=job_id, **job)

@router.post(
    "/enrichment/apply",
    status_code=status.HTTP_200_OK,
    summary="Apply a Single Schema Patch",
    description="Applies a single, user-approved JSON patch to a schema file on disk."
)
async def apply_patch(
    request: schemas.EnrichmentApplyRequest,
    auth: AuthContext = Depends(require_permission("superuser"))
):
    schema_dir = Path(settings.EDI_SCHEMA_DIRECTORY)
    schema_path = (schema_dir / request.schema_name).resolve()

    # Security check to prevent path traversal
    if not schema_path.is_file() or schema_dir.resolve() not in schema_path.parents:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schema file '{request.schema_name}' not found."
        )

    try:
        # Read the current schema
        with open(schema_path, 'r') as f:
            schema_content = json.load(f)

        # Apply the patch in-memory
        # The patch from the agent will be a dict, jsonpatch needs a list
        patch_to_apply = [request.patch.model_dump(exclude_none=True)]
        updated_content = jsonpatch.apply_patch(schema_content, patch_to_apply)

        # Write the updated schema back to the file
        with open(schema_path, 'w') as f:
            json.dump(updated_content, f, indent=2)

        logger.info(f"User '{auth.username}' applied patch to '{request.schema_name}': {request.patch.path}")
        return {"message": "Patch applied successfully."}

    except jsonpatch.JsonPatchException as e:
        logger.error(f"Failed to apply patch to {request.schema_name}: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"An unexpected error occurred while applying patch: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An internal error occurred.")