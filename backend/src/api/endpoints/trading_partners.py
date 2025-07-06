from fastapi import APIRouter, Depends, HTTPException, status, Response, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import logging
from typing import List

from sqlalchemy.future import select
from src.models import trading_partner, partner_profile

from src.api import schemas
from src.core.database import get_db
from src.core.auth import require_permission, AuthContext
from src.repositories.trading_partner import TradingPartnerRepository

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/trading-partners", response_model=List[schemas.TradingPartner])
async def list_trading_partners(
    response: Response,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(require_permission("partner:read")),
    _start: int = Query(0, alias="start"),
    _end: int = Query(10, alias="end"),
):
    """
    List all trading partners for the tenant specified in the X-Tenant-ID header.
    Supports pagination for admin-ui (using _start and _end).
    """
    logger.info(f"User '{auth.username}' listing partners for tenant '{auth.tenant_id}'.")
    repo = TradingPartnerRepository(db)
    
    limit = _end - _start
    partners, total_count = await repo.get_all_for_tenant(
        tenant_id=auth.tenant_id, skip=_start, limit=limit
    )
    
    # Set the X-Total-Count header for admin-ui pagination
    response.headers["X-Total-Count"] = str(total_count)
    
    return partners

@router.post("/trading-partners", response_model=schemas.TradingPartner, status_code=status.HTTP_201_CREATED)
async def create_trading_partner(
    partner_in: schemas.TradingPartnerCreate,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(require_permission("partner:create"))
):
    """
    Create a new Trading Partner for the tenant specified in the X-Tenant-ID header.
    """
    logger.debug(f"User '{auth.username}' create partner request payload: {partner_in.model_dump_json(indent=2)}")

    logger.info(f"User '{auth.username}' attempting to create partner '{partner_in.name}' in tenant '{auth.tenant_id}'.")
    repo = TradingPartnerRepository(db)

    existing_partner = await repo.get_by_name(name=partner_in.name, tenant_id=auth.tenant_id)
    if existing_partner:
        logger.warning(
            f"User '{auth.username}' failed to create partner '{partner_in.name}' in tenant "
            f"'{auth.tenant_id}' because it already exists."
        )
        raise HTTPException(
            status_code=400,
            detail=f"A trading partner with name '{partner_in.name}' already exists in this tenant."
        )

    try:
        # The repo method returns a partner object with a generated ID after the flush.
        new_partner = await repo.create_with_profiles(partner_in=partner_in, tenant_id=auth.tenant_id)
        
        # Commit the transaction to persist the new partner and all its children.
        await db.commit()

        # --- THIS IS THE FIX ---
        # After committing, the original 'new_partner' object is 'expired'.
        # We must fetch a fresh, complete copy from the database to ensure all
        # relationships are loaded before serialization.
        
        result = await db.execute(
            select(trading_partner.TradingPartner)
            .options(
                # Eagerly load the 'profiles' and the nested 'criteria'
                selectinload(trading_partner.TradingPartner.profiles)
                .selectinload(partner_profile.PartnerProfile.criteria)
            )
            .filter(trading_partner.TradingPartner.id == new_partner.id)
        )
        committed_partner = result.scalars().one()

        logger.info(
            f"Successfully created and committed partner '{committed_partner.name}' with id={committed_partner.id} "
            f"for tenant '{auth.tenant_id}'."
        )
        # Return the fully loaded object to prevent lazy-loading during serialization.
        return committed_partner
        
    except Exception as e:
        logger.error(f"Error creating partner, rolling back transaction: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while creating the trading partner."
        )