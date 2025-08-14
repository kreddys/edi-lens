# FILE: backend/src/api/endpoints/edi_parsing.py

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
import logging

from src.api.schemas import EdiParsingRequest, EdiSegment
from src.core.auth import require_service_auth, AuthContext
from src.services.edi_parsing_service import EdiParsingService

router = APIRouter(prefix="/edi", tags=["EDI Processing"])
logger = logging.getLogger(__name__)

@router.post("/parse", response_model=List[EdiSegment])
async def parse_edi(
    request: EdiParsingRequest,
    auth: AuthContext = Depends(require_service_auth)
) -> List[EdiSegment]:
    """
    Parse an EDI document and return its structure.
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
        return parsed_segments

    except Exception as e:
        logger.error(f"EDI parsing failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"EDI parsing failed: {str(e)}"
        )
