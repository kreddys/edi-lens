# FILE: backend/src/api/endpoints/schema_validation.py

from fastapi import APIRouter, Depends, HTTPException, status
import logging

from src.api.schemas import SchemaValidationRequest, SchemaValidationResponse
from src.core.auth import require_service_auth, AuthContext
from src.services.schema_validation_service import SchemaValidationService

router = APIRouter(prefix="/schemas", tags=["Schema Management"])
logger = logging.getLogger(__name__)

@router.post("/validate", response_model=SchemaValidationResponse)
async def validate_schema(
    request: SchemaValidationRequest,
    auth: AuthContext = Depends(require_service_auth)
) -> SchemaValidationResponse:
    """
    Validate an EDI schema.
    """
    try:
        if not auth.has_tenant_access(request.tenant_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to specified tenant"
            )

        validation_service = SchemaValidationService()
        is_valid = await validation_service.validate_schema(
            schema_name=request.schema_name,
            tenant_id=request.tenant_id,
        )
        return SchemaValidationResponse(is_valid=is_valid)

    except Exception as e:
        logger.error(f"Schema validation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Schema validation failed: {str(e)}"
        )
