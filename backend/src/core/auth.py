import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from pydantic import BaseModel, Field
from typing import List, Optional

from src.core.config import settings

# This URL points to our Keycloak service inside Docker.
KEYCLOAK_URL = f"{settings.KEYCLOAK_URL}/realms/{settings.KEYCLOAK_REALM}"
# The tokenUrl should point to where a client would get a token from, for OpenAPI docs.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{KEYCLOAK_URL}/protocol/openid-connect/token")

# This Pydantic model represents the user data we get from the Keycloak token
class User(BaseModel):
    id: str = Field(alias="sub")
    username: Optional[str] = Field(alias="preferred_username", default=None)
    email: Optional[str] = None
    first_name: Optional[str] = Field(alias="given_name", default=None)
    last_name: Optional[str] = Field(alias="family_name", default=None)
    # This is an example of how you could get roles
    roles: List[str] = Field(alias="realm_access.roles", default=[])

# A cache for Keycloak's public key to avoid fetching it on every request
_keycloak_public_key = None

async def get_keycloak_public_key():
    """Fetches the public key from Keycloak, with a simple cache."""
    global _keycloak_public_key
    if _keycloak_public_key:
        return _keycloak_public_key

    async with httpx.AsyncClient() as client:
        response = await client.get(KEYCLOAK_URL)
        response.raise_for_status()
        public_key = response.json()["public_key"]
        # Format the key as a PEM key for python-jose
        _keycloak_public_key = f"-----BEGIN PUBLIC KEY-----\n{public_key}\n-----END PUBLIC KEY-----"
        return _keycloak_public_key

async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        public_key = await get_keycloak_public_key()
        
        payload = jwt.decode(
            token, public_key, algorithms=["RS256"], audience="account"
        )
        
        user = User.model_validate(payload)
        if user.id is None:
            raise credentials_exception
    except (JWTError, httpx.HTTPStatusError, KeyError):
        raise credentials_exception
    return user