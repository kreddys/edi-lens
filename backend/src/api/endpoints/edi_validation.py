# FILE: backend/src/api/endpoints/edi_validation.py

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
import time
import logging
from datetime import datetime

from src.api.schemas import (
    RealtimeEDIValidationRequest,
    RealtimeEDIValidationResponse,
    BatchEDIValidationRequest,
    BatchEDIValidationResponse,
    BatchJobStatusResponse,
    ValidationFinding
)
from src.core.auth import require_service_auth, AuthContext
from src.services.edi_validation_service import EDIValidationService
from src.services.batch_job_service import BatchJobService

router = APIRouter(prefix="/edi", tags=["EDI Processing"])
logger = logging.getLogger(__name__)

@router.post("/validate-realtime", response_model=RealtimeEDIValidationResponse)
async def validate_realtime_edi(
    request: RealtimeEDIValidationRequest,
    auth: AuthContext = Depends(require_service_auth)
) -> RealtimeEDIValidationResponse:
    """
    Validate EDI document with immediate synchronous response.
    
    This endpoint is designed for real-time HTTP workflows where immediate
    response is required. Processing is synchronous and should complete
    within seconds.
    """
    start_time = time.time()
    
    try:
        # Validate tenant access
        logger.debug(f"Checking tenant access for tenant_id: {request.tenant_id}, auth context: {type(auth).__name__}")
        
        has_access = auth.has_tenant_access(request.tenant_id)
        logger.debug(f"Tenant access check result: {has_access}")
        
        if not has_access:
            logger.info(f"Access denied for tenant '{request.tenant_id}' - service '{getattr(auth, 'service_name', 'unknown')}' not authorized")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to specified tenant"
            )
        
        # Initialize validation service
        validation_service = EDIValidationService()
        
        # Perform EDI validation
        validation_result = await validation_service.validate_edi(
            edi_content=request.edi_content,
            schema_name=request.validation_schema,
            tenant_id=request.tenant_id,
            snip_level=request.snip_level
        )
        
        # Generate TA1 if requested
        ta1_content = None
        if request.generate_ta1:
            ta1_content = await validation_service.generate_ta1(
                edi_content=request.edi_content,
                validation_errors=validation_result.findings
            )
        
        # Calculate processing time
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        return RealtimeEDIValidationResponse(
            valid=validation_result.valid,
            validation_results=validation_result.findings,
            processing_time_ms=processing_time_ms,
            schema_used=request.validation_schema,
            snip_level_used=request.snip_level,
            ta1_content=ta1_content,
            workflow_id=request.workflow_id,
            processed_at=datetime.utcnow()
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions (like 403 Forbidden) as-is
        raise
    except Exception as e:
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        # Log error for monitoring
        logger.error(f"EDI validation failed: {str(e)}", exc_info=True)
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"EDI validation failed: {str(e)}"
        )

@router.post("/validate-batch", response_model=BatchEDIValidationResponse)
async def validate_batch_edi(
    request: BatchEDIValidationRequest,
    auth: AuthContext = Depends(require_service_auth)
) -> BatchEDIValidationResponse:
    """
    Process single EDI file asynchronously with webhook callback.
    
    This endpoint creates a job for batch processing and returns immediately.
    The actual processing happens asynchronously, and results are sent
    via webhook to the specified callback_url.
    """
    try:
        # Validate tenant access
        if not auth.has_tenant_access(request.tenant_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to specified tenant"
            )
        
        # Initialize batch job service
        batch_service = BatchJobService()
        
        # Create batch processing job
        job_id = await batch_service.create_batch_job(request)
        
        # Estimate processing time based on content size
        estimated_time = min(max(len(request.edi_content) // 1000, 1000), 30000)
        
        return BatchEDIValidationResponse(
            job_id=job_id,
            status="QUEUED",
            workflow_id=request.workflow_id,
            file_name=request.file_name,
            estimated_processing_time_ms=estimated_time,
            created_at=datetime.utcnow()
        )
        
    except Exception as e:
        # Log error for monitoring
        # TODO: Add proper logging
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create batch job: {str(e)}"
        )

@router.get("/jobs/{job_id}", response_model=BatchJobStatusResponse)
async def get_batch_job_status(
    job_id: str,
    auth: AuthContext = Depends(require_service_auth)
) -> BatchJobStatusResponse:
    """
    Get status of batch processing job.
    
    Returns current status and results if the job is completed.
    """
    try:
        # Initialize batch job service
        batch_service = BatchJobService()
        
        # Get job status
        job_status = await batch_service.get_job_status(job_id)
        
        if not job_status:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found"
            )
        
        # Validate tenant access
        if not auth.has_tenant_access(job_status.tenant_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to specified tenant"
            )
        
        return job_status
        
    except HTTPException:
        raise
    except Exception as e:
        # Log error for monitoring
        # TODO: Add proper logging
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get job status: {str(e)}"
        )