from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.api import schemas
from src.core.database import get_db
from src.core.edi_parser import parse_edi # <-- Import our new parser

router = APIRouter()

@router.post("/", response_model=schemas.ValidationResponse)
async def validate_edi_endpoint(
    request: schemas.ValidationRequest,
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

    # TODO (Future steps will go here)
    # - Fetch rules from DB
    # - Build hierarchical structure
    # - Run validator
    # - Generate acknowledgements

    # For now, return the successfully parsed segments
    return schemas.ValidationResponse(
        status="Parsed Successfully",
        findings=[], # No validation logic yet
        ta1_acknowledgement=None,
        ack999_acknowledgement=None,
        parsed_segments=parse_result.segments,
    )