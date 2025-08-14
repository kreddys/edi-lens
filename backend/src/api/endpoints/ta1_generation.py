# FILE: backend/src/api/endpoints/ta1_generation.py

from fastapi import APIRouter, Depends, HTTPException, status
import logging
import time

from src.api.schemas import TA1GenerationRequest, TA1GenerationResponse
from src.core.auth import require_service_auth, ServiceContext
from src.services.ta1_generation_service import TA1GenerationService

router = APIRouter(prefix="/edi", tags=["TA1 Generation"])
logger = logging.getLogger(__name__)

@router.post("/generate-ta1", response_model=TA1GenerationResponse)
async def generate_ta1(
    request: TA1GenerationRequest,
    auth: ServiceContext = Depends(require_service_auth)
):
    """
    Generate TA1 acknowledgment from EDI content.
    
    This endpoint allows NiFi workflows to generate TA1 acknowledgments
    independently of the validation process. Supports acceptance, rejection,
    and error acknowledgments.
    
    Args:
        request: TA1 generation request containing EDI content and parameters
        auth: Service authentication context
        
    Returns:
        TA1GenerationResponse: Generated TA1 acknowledgment with metadata
        
    Raises:
        HTTPException: 403 if tenant access denied, 422 for validation errors, 
                      500 for generation failures
    """
    start_time = time.time()
    
    try:
        logger.debug(f"Processing TA1 generation request: workflow_id={request.workflow_id}, tenant_id={request.tenant_id}")
        
        # Validate tenant access
        logger.debug(f"Checking tenant access for tenant_id: {request.tenant_id}")
        
        if not auth.has_tenant_access(request.tenant_id):
            logger.info(f"Access denied for tenant '{request.tenant_id}' - service '{auth.service_name}' not authorized")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to specified tenant"
            )
        
        logger.debug(f"Tenant access granted for '{request.tenant_id}' by service '{auth.service_name}'")
        
        # Validate acknowledgment code and error requirements
        if request.acknowledgment_code == "E" and not request.error_code:
            logger.warning(f"Missing error_code for acknowledgment_code 'E' in workflow {request.workflow_id}")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="error_code is required when acknowledgment_code is 'E'"
            )
        
        # Initialize TA1 generation service
        ta1_service = TA1GenerationService()
        
        # Generate TA1
        logger.debug(f"Generating TA1 acknowledgment: ack_code={request.acknowledgment_code}")
        result = await ta1_service.generate_ta1(request)
        
        processing_time_ms = int((time.time() - start_time) * 1000)
        logger.info(f"TA1 generation completed successfully: workflow_id={request.workflow_id}, control_number={result.control_number}, processing_time={processing_time_ms}ms")
        
        return result
        
    except HTTPException:
        # Re-raise HTTP exceptions (like 403 Forbidden) as-is to preserve status codes
        raise
    except Exception as e:
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        # Log error with full context for monitoring and debugging
        logger.error(
            f"TA1 generation failed: workflow_id={request.workflow_id}, "
            f"tenant_id={request.tenant_id}, ack_code={request.acknowledgment_code}, "
            f"processing_time={processing_time_ms}ms, error={str(e)}", 
            exc_info=True
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"TA1 generation failed: {str(e)}"
        )