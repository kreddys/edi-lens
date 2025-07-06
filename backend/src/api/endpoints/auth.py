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

@router.get("/auth/login", response_class=RedirectResponse, summary="Redirect to Keycloak Login",
            description="Initiates the OIDC login flow by redirecting the user's browser to the Keycloak authentication page.")
async def login(request: Request):
    redirect_uri = request.url_for('callback')
    params = {'client_id': settings.KEYCLOAK_BACKEND_CLIENT_ID, 'response_type': 'code', 'scope': 'openid profile email', 'redirect_uri': redirect_uri}
    auth_url = f"{settings.KEYCLOAK_BROWSER_URL}/realms/{settings.KEYCLOAK_REALM}/protocol/openid-connect/auth?{urlencode(params)}"
    logger.info(f"Redirecting user to Keycloak for authentication.")
    return RedirectResponse(auth_url)

@router.get("/auth/callback", response_model=TokenResponse, summary="Keycloak Login Callback",
            description="The callback endpoint that Keycloak redirects to after a successful login. It exchanges the authorization code for an access token.")
async def callback(request: Request):
    code = request.query_params.get('code')
    if not code:
        raise HTTPException(status_code=400, detail="Authorization code not provided")
    redirect_uri = request.url_for('callback')
    try:
        token_data = keycloak_openid.token(grant_type='authorization_code', code=code, redirect_uri=redirect_uri)
        return TokenResponse(access_token=token_data['access_token'])
    except Exception as e:
        logger.error(f"Error during token exchange: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail="Failed to exchange code for token.")