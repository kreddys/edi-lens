from fastapi import APIRouter, Depends, HTTPException, status, Response, Query
from sqlalchemy.ext.asyncio import AsyncSession
import logging
from typing import List

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
    
    new_partner = await repo.create_with_profiles(partner_in=partner_in, tenant_id=auth.tenant_id)
    logger.info(
        f"Successfully created partner '{new_partner.name}' with id={new_partner.id} "
        f"for tenant '{auth.tenant_id}'."
    )
    return new_partner