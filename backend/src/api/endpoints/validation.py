from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from src.api import schemas
from src.core.database import get_db
from src.core.auth import require_permission, AuthContext
from src.services.validation_service import ValidationService, PrevalidationError

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/validate", response_model=schemas.ValidationResponse, summary="Validate an EDI File",
             description="Crystal clear EDI validation endpoint with flexible profile selection. Supports both auto-detection from EDI content and manual profile override. Returns validation results with configured TA1/999 responses.")
async def validate_edi_endpoint(
    request: schemas.ValidationRequest,
    auth: AuthContext = Depends(require_permission("validation:run")),
    db: AsyncSession = Depends(get_db)    
):
    """
    This endpoint is a thin wrapper around the ValidationService.
    It handles HTTP request/response and authentication, then delegates all
    business logic to the service layer.
    """
    try:
        validation_service = ValidationService(db_session=db)
        response_data = await validation_service.process_edi_file(
            edi_data=request.edi_data,
            file_name=request.file_name or "api_upload.txt",
            tenant_id=auth.tenant_id,
            user_id=auth.user_id,
            username=auth.username,
            profile_name=request.profile_name
        )
        return response_data
    
    except PrevalidationError as e:
        logger.warning(f"Pre-validation failed for file '{request.file_name}': {e}")
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.error(f"The validation service failed for file '{request.file_name}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred during the validation process.")