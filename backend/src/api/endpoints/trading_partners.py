# FILE: backend/src/api/endpoints/trading_partners.py

from fastapi import APIRouter, Depends, HTTPException, status, Response, Query
from sqlalchemy.ext.asyncio import AsyncSession
import logging
from typing import List

from src.api import schemas
from src.core.database import get_db
from src.core.auth import require_permission, AuthContext
from src.repositories.trading_partner import TradingPartnerRepository
from src.models import trading_partner

router = APIRouter()
logger = logging.getLogger(__name__)

async def get_partner_or_404(
    partner_id: int,
    repo: TradingPartnerRepository
) -> trading_partner.TradingPartner:
    """Helper to fetch a partner using the repository or raise 404."""
    partner = await repo.get_by_id(partner_id=partner_id)
    if not partner:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trading partner not found")
    return partner

@router.get("/trading-partners", response_model=List[schemas.TradingPartner], summary="List Trading Partners",
            description="Retrieves a paginated list of all trading partners for the tenant specified in the `X-Tenant-ID` header. Requires `trading-partners:read` permission.")
async def list_trading_partners(
    response: Response,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(require_permission("trading-partners:read")),
    _start: int = Query(0, alias="start"),
    _end: int = Query(10, alias="end"),
):
    repo = TradingPartnerRepository(db, auth)
    limit = _end - _start
    partners, total_count = await repo.get_all_for_tenant(skip=_start, limit=limit)
    response.headers["X-Total-Count"] = str(total_count)
    return partners

@router.get("/trading-partners/{partner_id}", response_model=schemas.TradingPartner, summary="Get a Single Trading Partner",
            description="Fetches the complete details of a single trading partner, including all nested profiles. Requires `trading-partners:read` permission.")
async def get_trading_partner(
    partner_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(require_permission("trading-partners:read"))
):
    repo = TradingPartnerRepository(db, auth)
    return await get_partner_or_404(partner_id=partner_id, repo=repo)

@router.post("/trading-partners", response_model=schemas.TradingPartner, status_code=status.HTTP_201_CREATED, summary="Create a Trading Partner",
             description="Creates a new trading partner with its associated profiles. Requires `trading-partners:create` permission.")
async def create_trading_partner(
    partner_in: schemas.TradingPartnerCreate,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(require_permission("trading-partners:create"))
):
    repo = TradingPartnerRepository(db, auth)
    existing_partner = await repo.get_by_name(name=partner_in.name)
    if existing_partner:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"A trading partner with name '{partner_in.name}' already exists in this tenant.")
    
    new_partner = await repo.create_with_profiles(partner_in=partner_in)
    await db.commit()
    # Re-fetch to eager load relationships for the response
    return await repo.get_by_id(partner_id=new_partner.id)

@router.put("/trading-partners/{partner_id}", response_model=schemas.TradingPartner, summary="Update a Trading Partner",
            description="Updates an existing trading partner. This supports full replacement of profiles. Requires `trading-partners:update` permission.")
async def update_trading_partner(
    partner_id: int,
    partner_in: schemas.TradingPartnerUpdate,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(require_permission("trading-partners:update"))
):
    repo = TradingPartnerRepository(db, auth)
    db_partner = await get_partner_or_404(partner_id=partner_id, repo=repo)

    if db_partner.name != partner_in.name:
        existing = await repo.get_by_name(name=partner_in.name)
        if existing and existing.id != partner_id:
             raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"A trading partner with name '{partner_in.name}' already exists in this tenant.")
    
    try:
        updated_partner_id = (await repo.update(db_partner=db_partner, partner_in=partner_in)).id
        await db.commit()
        # Re-fetch to eager load relationships for the response
        return await repo.get_by_id(partner_id=updated_partner_id)
    except Exception as e:
        logger.error(f"Error updating partner, rolling back transaction: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An error occurred while updating the trading partner.")

@router.delete("/trading-partners/{partner_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a Trading Partner",
               description="Deletes a trading partner and all of its associated profiles. Requires `trading-partners:delete` permission.")
async def delete_trading_partner(
    partner_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(require_permission("trading-partners:delete"))
):
    repo = TradingPartnerRepository(db, auth)
    db_partner = await get_partner_or_404(partner_id=partner_id, repo=repo)
    await repo.delete(db_partner=db_partner)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)