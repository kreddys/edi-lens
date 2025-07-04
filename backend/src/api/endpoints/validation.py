from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.api import schemas
from src.core.database import get_db
from src.core.edi_parser import parse_edi # <-- Import our new parser
from src.core.auth import get_current_user
from src.core.auth import User

router = APIRouter()

@router.post("/", response_model=schemas.ValidationResponse)
async def validate_edi_endpoint(
    request: schemas.ValidationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)    
):
    """
    Receives EDI data, validates it against configured rules,
    and returns a compliance report with acknowledgements.
    """
    
    # Step 1: Parse the raw EDI data using our new parser
    parse_result = parse_edi(request.edi_data)

    if parse_result.error:
        # If the parser returns an error, we can't proceed.
        # Return a 400 Bad Request error.
        raise HTTPException(status_code=400, detail=parse_result.error)

    # TODO: Use the `current_user` object to implement multi-tenancy
    # For example, you could fetch rules that belong to the user's tenant/organization.
    # logger.info(f"Validation request by user: {current_user.username}")

    # ... (rest of the function)
    return schemas.ValidationResponse(
        status="Parsed Successfully",
        findings=[], # No validation logic yet
        ta1_acknowledgement=None,
        ack999_acknowledgement=None,
        parsed_segments=parse_result.segments,
    )