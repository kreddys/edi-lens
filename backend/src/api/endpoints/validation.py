# FILE: backend/src/api/endpoints/validation.py

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
             description="Validates an EDI document using an explicitly named profile. Returns structured validation results and generated acknowledgments.")
async def validate_edi_endpoint(
    request: schemas.ValidationRequest,
    auth: AuthContext = Depends(require_permission("validation:run")),
    db: AsyncSession = Depends(get_db)    
):
    try:
        validation_service = ValidationService(db_session=db)
        response_data = await validation_service.process_edi_file(
            edi_data=request.edi_data,
            tenant_id=auth.tenant_id,
            user_id=auth.user_id,
            username=auth.username,
            profile_name=request.profile_name
            # --- THIS IS THE FIX: file_name is no longer passed from the API ---
        )
        return response_data
    
    except PrevalidationError as e:
        logger.warning(f"Pre-validation failed for tenant '{auth.tenant_id}': {e}")
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.error(f"The validation service failed for tenant '{auth.tenant_id}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred during the validation process.")