import httpx
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import OAuth2PasswordBearer, HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt, JWTError
from pydantic import BaseModel, Field
from typing import List, Optional, Annotated
import logging
import uuid

from src.core.config import settings
from src.core.audit import user_id_cv, username_cv, tenant_id_cv, request_id_cv

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

class AuthContext:
    def __init__(self, user: User, tenant_id: str):
        self.user_id = user.sub
        self.username = user.username
        self.tenant_id = tenant_id
        self.roles = set(user.realm_access.roles)
        self.groups = set(user.groups)

    def has_permission(self, permission: str) -> bool:
        if "superuser" in self.roles:
            return True
        return permission in self.roles

    def is_member_of(self, tenant_id: str) -> bool:
        return tenant_id in self.groups

    def has_tenant_access(self, tenant_id: str) -> bool:
        """Check if user has access to specified tenant."""
        return self.is_member_of(tenant_id)

class ServiceContext:
    """Authentication context for service-to-service communication."""
    def __init__(self, service_name: str, allowed_tenants: List[str] = None):
        self.service_name = service_name
        self.allowed_tenants = allowed_tenants or []
        self.is_service_account = True

    def has_permission(self, permission: str) -> bool:
        """Service accounts have broad permissions for EDI processing."""
        service_permissions = [
            "edi:process", "edi:validate", "edi:generate-acknowledgments"
        ]
        return permission in service_permissions

    def has_tenant_access(self, tenant_id: str) -> bool:
        """Check if service has access to specified tenant."""
        # If no specific tenants configured, allow all
        if not self.allowed_tenants:
            return True
        return tenant_id in self.allowed_tenants

def require_permission(permission: str):
    async def dependency(
        x_tenant_id: Annotated[str, Header()],
        user: User = Depends(get_current_user)
    ) -> AuthContext:
        # --- THIS IS THE FIX ---
        # Set context variables for the audit logging system.
        user_id_cv.set(user.sub)
        username_cv.set(user.username)
        tenant_id_cv.set(x_tenant_id)
        request_id_cv.set(str(uuid.uuid4())) # Generate a unique ID for this request

        logger.debug(f"Checking permission '{permission}' for user '{user.username}' in tenant '{x_tenant_id}'.")
        auth_context = AuthContext(user, x_tenant_id)
        
        if not auth_context.is_member_of(x_tenant_id):
            logger.warning(
                f"User '{auth_context.username}' denied access to tenant '{x_tenant_id}'. "
                f"User is only in groups: {list(auth_context.groups)}"
            )
            raise HTTPException(status_code=403, detail=f"Access denied to tenant '{x_tenant_id}'.")
        
        if not auth_context.has_permission(permission):
            logger.warning(
                f"User '{auth_context.username}' in tenant '{x_tenant_id}' "
                f"denied action requiring permission '{permission}'."
            )
            raise HTTPException(status_code=403, detail=f"Permission '{permission}' required.")
            
        logger.info(
            f"User '{auth_context.username}' granted access to tenant '{x_tenant_id}' "
            f"with permission '{permission}'."
        )
        return auth_context
    return dependency

_keycloak_public_key = None

async def get_keycloak_public_key():
    global _keycloak_public_key
    if _keycloak_public_key:
        return _keycloak_public_key
    
    logger.debug("Fetching Keycloak public key for the first time.")
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
                logger.error("RSA signing key not found in JWKS from Keycloak.")
                raise HTTPException(status_code=500, detail="RSA signing key not found in JWKS")

            _keycloak_public_key = rsa_key
            logger.info("Successfully fetched and cached Keycloak public key.")
            return _keycloak_public_key
    except (httpx.RequestError, KeyError) as e:
        logger.error(f"Could not fetch Keycloak public key: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Could not fetch Keycloak public key: {e}")

async def get_current_user(creds: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        public_key = await get_keycloak_public_key()
        
        logger.debug(f"Expecting token audience: {settings.KEYCLOAK_BACKEND_CLIENT_ID}")

        payload = jwt.decode(
            creds.credentials,
            public_key,
            algorithms=["RS256"],
            audience=settings.KEYCLOAK_BACKEND_CLIENT_ID
        )
        logger.debug(f"Token payload successfully decoded and validated: {payload}")

        user = User.model_validate(payload)
        logger.debug(f"Pydantic User model validated for user: {user.username}")
        
        if not user.sub:
            logger.error("User 'sub' claim is missing after validation.")
            raise credentials_exception
        
        return user
    except JWTError as e:
        logger.error(f"JWT validation error: {e}")
        raise credentials_exception
    except Exception as e:
        logger.error(f"An unexpected error occurred during token validation: {e}", exc_info=True)
        raise credentials_exception

async def require_service_auth(
    authorization: str = Header(...),
) -> ServiceContext:
    """
    Dependency for service-to-service authentication.
    
    This is used for NiFi processors and other internal services
    that need to call the EDI processing APIs.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid service credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Extract token from Authorization header
        if not authorization.startswith("Bearer "):
            logger.error("Service auth header missing Bearer prefix")
            raise credentials_exception
        
        token = authorization.split("Bearer ")[1]
        
        # Validate service token with Keycloak
        public_key = await get_keycloak_public_key()
        
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience=settings.KEYCLOAK_BACKEND_CLIENT_ID
        )
        
        # Check if this is a service account token
        client_id = payload.get("azp")  # Authorized party
        if not client_id or client_id != "nifi-service":
            logger.error(f"Invalid service client_id: {client_id}")
            raise credentials_exception
        
        # Extract service name and permissions
        service_name = payload.get("preferred_username", "unknown-service")
        
        # For now, allow all tenants for service accounts
        # In production, this should be configured per service
        allowed_tenants = []  # Empty list means all tenants allowed
        
        service_context = ServiceContext(
            service_name=service_name,
            allowed_tenants=allowed_tenants
        )
        
        logger.info(f"Service authentication successful for: {service_name}")
        return service_context
        
    except JWTError as e:
        logger.error(f"Service JWT validation error: {e}")
        raise credentials_exception
    except Exception as e:
        logger.error(f"Service authentication error: {e}", exc_info=True)
        raise credentials_exception