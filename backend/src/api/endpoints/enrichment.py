# FILE: backend/src/api/endpoints/enrichment.py
import logging
import uuid
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks

from src.core.auth import require_permission, AuthContext
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