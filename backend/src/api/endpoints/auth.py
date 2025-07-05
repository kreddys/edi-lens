from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from urllib.parse import urlencode
import logging

from src.core.config import keycloak_openid, settings

logger = logging.getLogger(__name__)

router = APIRouter(redirect_slashes=False)

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

@router.get("/auth/login", response_class=RedirectResponse, tags=["Authentication"])
async def login(request: Request):
    """
    Redirects the user to the Keycloak login page by manually constructing
    the URL with the public-facing address.
    """
    redirect_uri = request.url_for('callback')
    params = {
        'client_id': settings.KEYCLOAK_BACKEND_CLIENT_ID,
        'response_type': 'code',
        'scope': 'openid profile email',
        'redirect_uri': redirect_uri
    }
    
    auth_url_base = f"{settings.KEYCLOAK_BROWSER_URL}/realms/{settings.KEYCLOAK_REALM}/protocol/openid-connect/auth"
    auth_url = f"{auth_url_base}?{urlencode(params)}"
    
    logger.info(f"Redirecting user to Keycloak for authentication. URL: {auth_url}")
    return RedirectResponse(auth_url)


@router.get("/auth/callback", response_model=TokenResponse, tags=["Authentication"])
async def callback(request: Request):
    logger.info("Received callback from Keycloak.")
    code = request.query_params.get('code')
    if not code:
        logger.error("Authorization code not found in callback.")
        return {"error": "Authorization code not provided"}

    logger.debug(f"Received authorization code (first 10 chars): {code[:10]}...")
    redirect_uri = request.url_for('callback')
    
    try:
        logger.info("Exchanging authorization code for access token.")
        token_data = keycloak_openid.token(
            grant_type='authorization_code',
            code=code,
            redirect_uri=redirect_uri,
        )
        logger.info("Token exchange successful.")
        logger.debug(f"Token data received: {token_data}")
        return TokenResponse(access_token=token_data['access_token'])
    except Exception as e:
        logger.error(f"Error during token exchange: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail="Failed to exchange code for token.")