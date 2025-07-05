import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt, JWTError
from pydantic import BaseModel, Field
from typing import List, Optional
import logging

from src.core.config import settings

logger = logging.getLogger(__name__)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
bearer_scheme = HTTPBearer()

class RealmAccess(BaseModel):
    roles: List[str] = []

class User(BaseModel):
    sub: str
    preferred_username: Optional[str] = None
    email: Optional[str] = None
    groups: List[str] = Field(default_factory=list)
    realm_access: RealmAccess = Field(default_factory=RealmAccess)

    @property
    def id(self) -> str:
        return self.sub

    @property
    def username(self) -> str:
        return self.preferred_username or "unknown_user"

_keycloak_public_key = None

async def get_keycloak_public_key():
    global _keycloak_public_key
    if _keycloak_public_key:
        return _keycloak_public_key

    try:
        async with httpx.AsyncClient() as client:
            well_known_url = f"{settings.KEYCLOAK_URL}/realms/{settings.KEYCLOAK_REALM}/.well-known/openid-configuration"
            response = await client.get(well_known_url)
            response.raise_for_status()
            jwks_uri = response.json()["jwks_uri"]
            jwks_response = await client.get(jwks_uri)
            jwks_response.raise_for_status()
            keys = jwks_response.json()["keys"]
            rsa_key = next((key for key in keys if key["kty"] == "RSA" and key.get("use") == "sig"), None)
            if not rsa_key:
                raise HTTPException(status_code=500, detail="RSA signing key not found in JWKS")
            _keycloak_public_key = rsa_key
            return _keycloak_public_key
    except (httpx.HTTPStatusError, KeyError) as e:
        raise HTTPException(status_code=500, detail=f"Could not fetch Keycloak public key: {e}")

async def get_current_user(creds: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        public_key = await get_keycloak_public_key()
        
        # Log the audience we are expecting for easier debugging
        logger.debug(f"Expecting token audience: {settings.KEYCLOAK_CLIENT_ID}")

        payload = jwt.decode(
            creds.credentials,
            public_key,
            algorithms=["RS256"],
            audience=settings.KEYCLOAK_CLIENT_ID
        )
        # Log the full token payload only at DEBUG level for security
        logger.debug(f"Token payload successfully decoded and validated: {payload}")

        user = User.model_validate(payload)
        logger.debug(f"Pydantic User model validated for user: {user.username}")
        
        if not user.sub:
            logger.error("User 'sub' claim is missing after validation.")
            raise credentials_exception
        
        return user
    except JWTError as e:
        # Log JWT-specific errors, which are common (e.g., signature expired)
        logger.error(f"JWT validation error: {e}")
        raise credentials_exception
    except Exception as e:
        # Log any other unexpected errors
        logger.error(f"An unexpected error occurred during token validation: {e}", exc_info=True)
        raise credentials_exception