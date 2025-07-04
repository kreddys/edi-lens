from fastapi import APIRouter, Depends
from src.core.dependencies import get_current_active_user
from src.models.user import User

router = APIRouter()

@router.get("/me")
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    """
    Test endpoint to get the current authenticated user.
    """
    return {
        "id": current_user.id,
        "email": current_user.email,
        "role": current_user.role,
        "tenant_id": current_user.tenant_id
    }