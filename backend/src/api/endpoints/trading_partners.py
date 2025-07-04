from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api import schemas
from src.core.database import get_db
from src.core.auth import get_current_user, User
from src.repositories.trading_partner import TradingPartnerRepository

router = APIRouter()

@router.post("/", response_model=schemas.TradingPartner, status_code=status.HTTP_201_CREATED)
async def create_trading_partner(
    partner_in: schemas.TradingPartnerCreate, 
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new Trading Partner with its associated profiles and criteria.
    This is an authenticated endpoint.
    """
    repo = TradingPartnerRepository(db)

    existing_partner = await repo.get_by_name(name=partner_in.name)
    if existing_partner:
        raise HTTPException(
            status_code=400,
            detail="A trading partner with this name already exists."
        )
    
    return await repo.create_with_profiles(partner_in=partner_in)