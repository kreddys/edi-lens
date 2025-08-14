# FILE: backend/src/api/endpoints/edi.py

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from typing import List
import logging
import time
from datetime import datetime

from src.api.schemas import (
    # EDI Validation
    RealtimeEDIValidationRequest,
    RealtimeEDIValidationResponse,
    BatchEDIValidationRequest,
    BatchEDIValidationResponse,
    BatchJobStatusResponse,
    # EDI Parsing
    EdiParsingRequest,
    EdiSegment,
    # TA1 Generation
    TA1GenerationRequest,
    TA1GenerationResponse,
)
from src.core.auth import require_service_auth, AuthContext
from src.services.edi_validation_service import EDIValidationService
from src.services.edi_parsing_service import EdiParsingService
from src.services.ta1_generation_service import TA1GenerationService
from src.services.batch_job_service import BatchJobService

router = APIRouter(prefix="/edi", tags=["EDI Processing"])
logger = logging.getLogger(__name__)

# ============================================================================
# EDI VALIDATION ENDPOINTS
# ============================================================================

@router.post("/validate-realtime", response_model=RealtimeEDIValidationResponse)
async def validate_realtime_edi(
    request: RealtimeEDIValidationRequest,
    auth: AuthContext = Depends(require_service_auth)
) -> RealtimeEDIValidationResponse:
    """
    Validate EDI document with immediate synchronous response.
    
    This endpoint provides real-time validation for immediate feedback.
    Use this for small files or when you need instant results.
    """
    start_time = time.time()
    
    try:
        if not auth.has_tenant_access(request.tenant_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to specified tenant"
            )

        validation_service = EDIValidationService()
        validation_result = await validation_service.validate_edi(
            edi_content=request.edi_content,
            schema_name=request.validation_schema,
            tenant_id=request.tenant_id,
            snip_level=request.snip_level
        )
        
        processing_time = int(round((time.time() - start_time) * 1000))
        logger.info(f"Real-time validation completed in {processing_time}ms for tenant {request.tenant_id}")
        
        # Convert to response format
        from src.api.schemas import RealtimeEDIValidationResponse
        from datetime import datetime
        
        return RealtimeEDIValidationResponse(
            valid=validation_result.valid,
            validation_results=validation_result.findings,
            processing_time_ms=processing_time,
            schema_used=request.validation_schema,
            snip_level_used=request.snip_level,
            workflow_id=request.workflow_id,
            processed_at=datetime.utcnow()
        )

    except HTTPException:
        # Re-raise HTTP exceptions (like 403 Forbidden) as-is
        raise
    except Exception as e:
        logger.error(f"Real-time EDI validation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"EDI validation failed: {str(e)}"
        )

@router.post("/validate-batch", response_model=BatchEDIValidationResponse)
async def validate_batch_edi(
    request: BatchEDIValidationRequest,
    background_tasks: BackgroundTasks,
    auth: AuthContext = Depends(require_service_auth)
) -> BatchEDIValidationResponse:
    """
    Submit EDI document for batch validation processing.
    
    This endpoint queues validation jobs for asynchronous processing.
    Use this for large files or when you can wait for results.
    """
    try:
        if not auth.has_tenant_access(request.tenant_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to specified tenant"
            )

        batch_service = BatchJobService()
        job_id = await batch_service.create_batch_job(request)
        
        # Schedule background processing
        background_tasks.add_task(
            batch_service.process_validation_job,
            job_id=job_id
        )
        
        logger.info(f"Batch validation job {job_id} created for tenant {request.tenant_id}")
        
        from datetime import datetime
        
        return BatchEDIValidationResponse(
            job_id=job_id,
            status="QUEUED",
            workflow_id=request.workflow_id,
            file_name=request.file_name,
            estimated_processing_time_ms=1000,  # Placeholder estimate
            created_at=datetime.utcnow()
        )

    except Exception as e:
        logger.error(f"Batch EDI validation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch validation failed: {str(e)}"
        )

@router.get("/jobs/{job_id}/status", response_model=BatchJobStatusResponse)
async def get_batch_job_status(
    job_id: str,
    auth: AuthContext = Depends(require_service_auth)
) -> BatchJobStatusResponse:
    """
    Get the status of a batch validation job.
    """
    try:
        batch_service = BatchJobService()
        status_info = await batch_service.get_job_status(job_id)
        
        if not status_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found"
            )
        
        # Verify tenant access
        if not auth.has_tenant_access(status_info.tenant_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to specified job"
            )
        
        return status_info

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get job status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get job status: {str(e)}"
        )

# ============================================================================
# EDI PARSING ENDPOINTS
# ============================================================================

@router.post("/parse", response_model=List[EdiSegment])
async def parse_edi(
    request: EdiParsingRequest,
    auth: AuthContext = Depends(require_service_auth)
) -> List[EdiSegment]:
    """
    Parse an EDI document and return its structure.
    
    This endpoint breaks down EDI content into individual segments
    and elements for detailed analysis and processing.
    """
    try:
        if not auth.has_tenant_access(request.tenant_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to specified tenant"
            )

        parsing_service = EdiParsingService()
        parsed_segments = await parsing_service.parse_edi(
            edi_content=request.edi_content,
            schema_name=request.schema_name,
            tenant_id=request.tenant_id,
        )
        
        logger.info(f"EDI parsing completed for tenant {request.tenant_id}, {len(parsed_segments)} segments parsed")
        return parsed_segments

    except Exception as e:
        logger.error(f"EDI parsing failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"EDI parsing failed: {str(e)}"
        )

# ============================================================================
# TA1 GENERATION ENDPOINTS
# ============================================================================

@router.post("/generate-ta1", response_model=TA1GenerationResponse)
async def generate_ta1(
    request: TA1GenerationRequest,
    auth: AuthContext = Depends(require_service_auth)
) -> TA1GenerationResponse:
    """
    Generate TA1 acknowledgment for an EDI interchange.
    
    This endpoint creates functional acknowledgments (TA1) based on
    the provided EDI content and acknowledgment parameters.
    """
    try:
        if not auth.has_tenant_access(request.tenant_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to specified tenant"
            )

        ta1_service = TA1GenerationService()
        ta1_response = await ta1_service.generate_ta1(request)
        
        logger.info(f"TA1 generation completed for tenant {request.tenant_id}")
        return ta1_response

    except Exception as e:
        logger.error(f"TA1 generation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"TA1 generation failed: {str(e)}"
        )