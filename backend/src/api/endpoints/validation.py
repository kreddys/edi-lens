from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from src.api import schemas
from src.core.database import get_db
from src.core.edi_parser import EdiParser, get_guide_version_from_edi
from src.core.auth import require_permission, AuthContext
from src.core.schema_manager import schema_manager
# --- THIS IS THE CHANGE ---
# Import the new top-level CDM model
from src.core.cdm import CdmInterchange 

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
        
    # 3. Parse the EDI data into the CdmInterchange model.
    try:
        parser = EdiParser(edi_string=request.edi_data, schema=schema)
        interchange: CdmInterchange = parser.parse() # The return type is now CdmInterchange
        logger.info(f"Successfully parsed EDI into interchange model for guide '{guide_version}'.")
        if interchange.errors:
            # For now, let's just log the parser-level errors.
            # In a full implementation, these would become findings.
            logger.warning(f"Parser-level errors found: {[e.message for e in interchange.errors]}")

    except Exception as e: # Catch any unexpected parser errors
        logger.error(f"Failed to parse EDI data: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"EDI Parsing Error: {e}")

    # TODO: Implement Phase 2 - Run ValidationEngine against each transaction in the interchange.
    # For now, we return a success response if parsing succeeds.
    
    all_findings = [] # This would collect findings from all transactions.
    
    # Example of how you would now process the interchange:
    for group in interchange.functional_groups:
        for transaction in group.transactions:
            # Here you would run the validator on `transaction`
            # and append any findings to `all_findings`
            pass

    return schemas.ValidationResponse(
        status="Parsed Successfully",
        findings=all_findings,  # Placeholder for future validation findings
        ta1_acknowledgement=None,
        ack999_acknowledgement=None,
    )