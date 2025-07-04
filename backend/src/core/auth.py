import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt, JWTError
from pydantic import BaseModel, Field
from typing import List, Optional
import logging

# Import settings, not the keycloak_openid object
from src.core.config import settings

logger = logging.getLogger(__name__)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
bearer_scheme = HTTPBearer()

class RealmAccess(BaseModel):
    """A Pydantic model for the nested 'realm_access' object in the token."""
    roles: List[str] = []

class User(BaseModel):
    """
    Pydantic model for user data from the token. This now correctly handles
    the nested roles structure.
    """
    id: str = Field(alias="sub")
    username: Optional[str] = Field(alias="preferred_username", default=None)
    email: Optional[str] = None
    first_name: Optional[str] = Field(alias="given_name", default=None)
    last_name: Optional[str] = Field(alias="family_name", default=None)
    realm_access: RealmAccess # Use the nested model to parse roles

# A simple cache for Keycloak's public key
_keycloak_public_key = None

async def get_keycloak_public_key():
    """
    Fetches the public key from Keycloak's .well-known endpoint to verify tokens.
    Uses the INTERNAL Docker URL for this server-to-server call.
    """
    global _keycloak_public_key
    if _keycloak_public_key:
        return _keycloak_public_key

    try:
        async with httpx.AsyncClient() as client:
            # Construct the well-known URL using settings
            well_known_url = f"{settings.KEYCLOAK_URL}/realms/{settings.KEYCLOAK_REALM}/.well-known/openid-configuration"
            response = await client.get(well_known_url)
            response.raise_for_status()
            
            # The JWKS (JSON Web Key Set) URI is where the public keys are
            jwks_uri = response.json()["jwks_uri"]
            
            # Fetch the keys
            jwks_response = await client.get(jwks_uri)
            jwks_response.raise_for_status()
            
            # Find the RS256 signing key
            keys = jwks_response.json()["keys"]
            rsa_key = next((key for key in keys if key["kty"] == "RSA" and key.get("use") == "sig"), None)
            
            if not rsa_key:
                raise HTTPException(status_code=500, detail="RSA signing key not found in JWKS")

            # The key is already in a format that python-jose can use directly
            _keycloak_public_key = rsa_key
            return _keycloak_public_key
    except (httpx.HTTPStatusError, KeyError) as e:
        raise HTTPException(status_code=500, detail=f"Could not fetch Keycloak public key: {e}")

# This is the robust, offline token validation function
async def get_current_user(creds: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    logger.debug("Attempting to get current user from token.")
    
    try:
        public_key = await get_keycloak_public_key()
        
        logger.debug("Decoding JWT token.")
        payload = jwt.decode(
            creds.credentials,
            public_key,
            algorithms=["RS256"],
            audience=settings.KEYCLOAK_CLIENT_ID
        )
        logger.info(f"Token successfully decoded for user: {payload.get('preferred_username')}")
        logger.debug(f"Token payload: {payload}") # This is very useful for debugging claims

        user = User.model_validate(payload)
        if user.id is None:
            logger.error("User ID (sub) not found in token payload.")
            raise credentials_exception
        
        return user
    except JWTError as e:
        logger.error(f"JWT Error during token decoding: {e}")
        raise credentials_exception
    except Exception as e:
        logger.error(f"An unexpected error occurred during token validation: {e}", exc_info=True)
        raise credentials_exception