"""
Authentication helpers for testing.
"""

from typing import List, Optional
from .jwt_utils import forge_jwt


def create_test_jwt(
    user_id: str = "test-user",
    username: str = "testuser",
    tenant_id: str = "tenant-a",
    permissions: Optional[List[str]] = None,
    groups: Optional[List[str]] = None,
    expires_in: int = 300,
) -> str:
    """
    Create a test JWT token with specified user attributes and permissions.
    
    Args:
        user_id: User identifier
        username: Username for the token
        tenant_id: Primary tenant ID for the user
        permissions: List of permissions/roles for the user
        groups: List of groups/tenants the user belongs to
        expires_in: Token expiration time in seconds
        
    Returns:
        Signed JWT token string
    """
    if permissions is None:
        permissions = ["workflow:read"]
    
    if groups is None:
        groups = [tenant_id]
    
    # Ensure tenant_id is in groups
    if tenant_id not in groups:
        groups.append(tenant_id)
    
    payload = {
        "sub": user_id,
        "preferred_username": username,
        "email": f"{username}@test.com",
        "realm_access": {"roles": permissions},
        "groups": groups,
    }
    
    return forge_jwt(payload, expires_in=expires_in)