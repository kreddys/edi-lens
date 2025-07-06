from fastapi import APIRouter, Depends, HTTPException, status, Response, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import logging
from typing import List, Any

from sqlalchemy.future import select
from src.models import trading_partner, partner_profile

from src.api import schemas
from src.core.database import get_db
from src.core.auth import require_permission, AuthContext
from src.repositories.trading_partner import TradingPartnerRepository

router = APIRouter()
logger = logging.getLogger(__name__)

async def get_partner_or_404(
    partner_id: int,
    tenant_id: str,
    db: AsyncSession
) -> trading_partner.TradingPartner:
    repo = TradingPartnerRepository(db)
    partner = await repo.get_by_id(partner_id=partner_id, tenant_id=tenant_id)
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
    """List all trading partners for the tenant."""
    repo = TradingPartnerRepository(db)
    limit = _end - _start
    partners, total_count = await repo.get_all_for_tenant(tenant_id=auth.tenant_id, skip=_start, limit=limit)
    response.headers["X-Total-Count"] = str(total_count)
    return partners

@router.get("/trading-partners/{partner_id}", response_model=schemas.TradingPartner, summary="Get a Single Trading Partner",
            description="Fetches the complete details of a single trading partner, including all nested profiles and criteria. Requires `trading-partners:read` permission.")
async def get_trading_partner(
    partner_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(require_permission("trading-partners:read"))
):
    """Get a single trading partner by ID."""
    partner = await get_partner_or_404(partner_id=partner_id, tenant_id=auth.tenant_id, db=db)
    return partner


@router.post("/trading-partners", response_model=schemas.TradingPartner, status_code=status.HTTP_201_CREATED, summary="Create a Trading Partner",
             description="Creates a new trading partner with its associated profiles and criteria. Requires `trading-partners:create` permission.")
async def create_trading_partner(
    partner_in: schemas.TradingPartnerCreate,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(require_permission("trading-partners:create"))
):
    """Create a new Trading Partner."""
    repo = TradingPartnerRepository(db)
    existing_partner = await repo.get_by_name(name=partner_in.name, tenant_id=auth.tenant_id)
    if existing_partner:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"A trading partner with name '{partner_in.name}' already exists in this tenant.")
    
    new_partner = await repo.create_with_profiles(partner_in=partner_in, tenant_id=auth.tenant_id)
    await db.commit()
    # Eagerly load the full object graph for the response
    return await get_partner_or_404(partner_id=new_partner.id, tenant_id=auth.tenant_id, db=db)


@router.put("/trading-partners/{partner_id}", response_model=schemas.TradingPartner, summary="Update a Trading Partner",
            description="Updates an existing trading partner. This endpoint supports full replacement of profiles and criteria. Requires `trading-partners:update` permission.")
async def update_trading_partner(
    partner_id: int,
    partner_in: schemas.TradingPartnerUpdate,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(require_permission("trading-partners:update"))
):
    """Update an existing Trading Partner."""
    repo = TradingPartnerRepository(db)
    db_partner = await get_partner_or_404(partner_id=partner_id, tenant_id=auth.tenant_id, db=db)

    if db_partner.name != partner_in.name:
        existing = await repo.get_by_name(name=partner_in.name, tenant_id=auth.tenant_id)
        if existing and existing.id != partner_id:
             raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"A trading partner with name '{partner_in.name}' already exists in this tenant.")
    
    try:
        updated_partner_id = (await repo.update(db_partner=db_partner, partner_in=partner_in)).id
        await db.commit()
        # After committing, the session is expired. We MUST re-fetch the object
        # with full relationships to ensure it can be serialized correctly.
        return await get_partner_or_404(partner_id=updated_partner_id, tenant_id=auth.tenant_id, db=db)
    except Exception as e:
        logger.error(f"Error updating partner, rolling back transaction: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An error occurred while updating the trading partner.")


@router.delete("/trading-partners/{partner_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a Trading Partner",
               description="Deletes a trading partner and all of its associated profiles and criteria. Requires `trading-partners:delete` permission.")
async def delete_trading_partner(
    partner_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(require_permission("trading-partners:delete"))
):
    """Delete a trading partner."""
    repo = TradingPartnerRepository(db)
    db_partner = await get_partner_or_404(partner_id=partner_id, tenant_id=auth.tenant_id, db=db)
    await repo.delete(db_partner=db_partner)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)