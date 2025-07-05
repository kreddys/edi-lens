from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from src.api import schemas
from src.core.database import get_db
from src.core.auth import require_permission, AuthContext
from src.repositories.trading_partner import TradingPartnerRepository

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/", response_model=schemas.TradingPartner, status_code=status.HTTP_201_CREATED)
async def create_trading_partner(
    partner_in: schemas.TradingPartnerCreate, 
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(require_permission("partner:create"))
):
    """
    Create a new Trading Partner for the tenant specified in the X-Tenant-ID header.
    """
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