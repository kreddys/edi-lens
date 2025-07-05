from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from src.api import schemas
from src.core.database import get_db
from src.core.edi_parser import parse_edi
from src.core.auth import require_permission, AuthContext

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/validate", response_model=schemas.ValidationResponse)
async def validate_edi_endpoint(
    request: schemas.ValidationRequest,
    auth: AuthContext = Depends(require_permission("validation:run")),
    db: AsyncSession = Depends(get_db)    
):
    """
    Receives EDI data, validates it against configured rules for the specified tenant,
    and returns a compliance report with acknowledgements.
    """
    logger.debug(f"User '{auth.username}' validation request payload: {request.model_dump_json(indent=2)}")
    
    logger.info(f"User '{auth.username}' from tenant '{auth.tenant_id}' initiated validation.")
    
    parse_result = parse_edi(request.edi_data)

    if parse_result.error:
        logger.warning(f"EDI parsing failed for tenant '{auth.tenant_id}': {parse_result.error}")
        raise HTTPException(status_code=400, detail=parse_result.error)
    
    logger.info(f"Successfully parsed {len(parse_result.segments)} segments for tenant '{auth.tenant_id}'.")

    # ... future validation logic will use auth.tenant_id ...

    return schemas.ValidationResponse(
        status="Parsed Successfully",
        findings=[],
        ta1_acknowledgement=None,
        ack999_acknowledgement=None,
        parsed_segments=parse_result.segments,
    )