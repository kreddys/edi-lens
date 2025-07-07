from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from src.api import schemas
from src.core.database import get_db
# --- THIS IS THE FIX ---
from src.core.edi_parser import EdiParser, get_guide_version_from_edi
from src.core.auth import require_permission, AuthContext
from src.core.schema_manager import schema_manager

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/validate", response_model=schemas.ValidationResponse, summary="Validate an EDI File",
             description="Parses and validates a raw EDI string against configured rules for the specified tenant. Requires `validation:run` permission.")
async def validate_edi_endpoint(
    request: schemas.ValidationRequest,
    auth: AuthContext = Depends(require_permission("validation:run")),
    db: AsyncSession = Depends(get_db)    
):
    """
    Receives EDI data, validates it against a loaded implementation guide schema,
    and returns a compliance report.
    """
    logger.info(f"User '{auth.username}' from tenant '{auth.tenant_id}' initiated validation for file '{request.file_name}'.")
    
    # 1. Determine which implementation guide to use from the EDI data itself.
    guide_version = get_guide_version_from_edi(request.edi_data)
    if not guide_version:
        raise HTTPException(status_code=400, detail="Could not determine implementation guide version (GS08) from EDI data.")
        
    # 2. Load the appropriate schema for that guide.
    schema = schema_manager.get_schema(guide_version)
    if not schema:
        logger.warning(f"No implementation guide schema found for version '{guide_version}'.")
        raise HTTPException(status_code=400, detail=f"Unsupported implementation guide version: {guide_version}")
        
    # 3. Parse the EDI data into the Canonical Data Model (CDM) using the loaded schema.
    try:
        parser = EdiParser(edi_string=request.edi_data, schema=schema)
        cdm = parser.parse()
        logger.info(f"Successfully parsed EDI into CDM for guide '{guide_version}'.")
    except ValueError as e:
        logger.error(f"Failed to parse EDI data: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"EDI Parsing Error: {e}")

    # TODO: Implement Phase 2 - Run ValidationEngine against the CDM.
    # For now, we return a success response if parsing succeeds.

    return schemas.ValidationResponse(
        status="Parsed Successfully",
        findings=[],  # Placeholder for future validation findings
        ta1_acknowledgement=None,
        ack999_acknowledgement=None,
    )