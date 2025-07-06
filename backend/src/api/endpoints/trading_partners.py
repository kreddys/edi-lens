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

# Reusable dependency to get a partner and check for existence
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


@router.get("/trading-partners", response_model=List[schemas.TradingPartner])
async def list_trading_partners(
    response: Response,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(require_permission("partner:read")),
    _start: int = Query(0, alias="start"),
    _end: int = Query(10, alias="end"),
):
    """List all trading partners for the tenant."""
    logger.info(f"User '{auth.username}' listing partners for tenant '{auth.tenant_id}'.")
    repo = TradingPartnerRepository(db)
    
    limit = _end - _start
    partners, total_count = await repo.get_all_for_tenant(
        tenant_id=auth.tenant_id, skip=_start, limit=limit
    )
    
    response.headers["X-Total-Count"] = str(total_count)
    return partners

@router.get("/trading-partners/{partner_id}", response_model=schemas.TradingPartner)
async def get_trading_partner(
    partner_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(require_permission("partner:read"))
):
    """Get a single trading partner by ID."""
    logger.info(f"User '{auth.username}' getting partner id={partner_id} for tenant '{auth.tenant_id}'.")
    partner = await get_partner_or_404(partner_id=partner_id, tenant_id=auth.tenant_id, db=db)
    return partner


@router.post("/trading-partners", response_model=schemas.TradingPartner, status_code=status.HTTP_201_CREATED)
async def create_trading_partner(
    partner_in: schemas.TradingPartnerCreate,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(require_permission("partner:create"))
):
    """Create a new Trading Partner."""
    logger.info(f"User '{auth.username}' attempting to create partner '{partner_in.name}' in tenant '{auth.tenant_id}'.")
    repo = TradingPartnerRepository(db)

    existing_partner = await repo.get_by_name(name=partner_in.name, tenant_id=auth.tenant_id)
    if existing_partner:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A trading partner with name '{partner_in.name}' already exists in this tenant."
        )

    try:
        new_partner = await repo.create_with_profiles(partner_in=partner_in, tenant_id=auth.tenant_id)
        await db.commit()
        await db.refresh(new_partner, attribute_names=["profiles"])
        return new_partner
        
    except Exception as e:
        logger.error(f"Error creating partner, rolling back transaction: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while creating the trading partner."
        )

@router.put("/trading-partners/{partner_id}", response_model=schemas.TradingPartner)
async def update_trading_partner(
    partner_id: int,
    partner_in: schemas.TradingPartnerUpdate,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(require_permission("partner:update"))
):
    """Update an existing Trading Partner."""
    logger.info(f"User '{auth.username}' attempting to update partner id={partner_id} in tenant '{auth.tenant_id}'.")
    repo = TradingPartnerRepository(db)
    
    db_partner = await get_partner_or_404(partner_id=partner_id, tenant_id=auth.tenant_id, db=db)

    # Check for name conflict if the name is being changed
    if db_partner.name != partner_in.name:
        existing = await repo.get_by_name(name=partner_in.name, tenant_id=auth.tenant_id)
        if existing and existing.id != partner_id:
             raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A trading partner with name '{partner_in.name}' already exists in this tenant."
            )
    try:
        updated_partner = await repo.update(db_partner=db_partner, partner_in=partner_in)
        await db.commit()
        await db.refresh(updated_partner)
        return updated_partner
    except Exception as e:
        logger.error(f"Error updating partner, rolling back transaction: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while updating the trading partner."
        )


@router.delete("/trading-partners/{partner_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_trading_partner(
    partner_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(require_permission("partner:delete"))
):
    """Delete a trading partner."""
    logger.info(f"User '{auth.username}' attempting to delete partner id={partner_id} in tenant '{auth.tenant_id}'.")
    repo = TradingPartnerRepository(db)
    db_partner = await get_partner_or_404(partner_id=partner_id, tenant_id=auth.tenant_id, db=db)
    await repo.delete(db_partner=db_partner)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)