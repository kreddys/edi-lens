#!/usr/bin/env python3
"""
Create a test JWT token for testing the secure SFTP processor.
This generates a simple JWT for demo purposes.
"""

import json
import base64
from datetime import datetime, timedelta

def create_test_jwt():
    """Create a test JWT token for demo purposes."""
    
    # Header (simplified - no signature verification for demo)
    header = {
        "alg": "HS256",
        "typ": "JWT"
    }
    
    # Payload with test user and tenant information
    payload = {
        "sub": "test-user-123",
        "preferred_username": "test-admin",
        "email": "admin@test.com",
        "groups": ["tenant-a", "tenant-b"],  # User has access to multiple tenants
        "realm_access": {
            "roles": ["sftp:read", "sftp:process", "admin"]
        },
        "iat": int(datetime.utcnow().timestamp()),
        "exp": int((datetime.utcnow() + timedelta(hours=2)).timestamp()),
        "iss": "edi-lens-test",
        "aud": "edi-lens-api"
    }
    
    # Encode (no signature for demo - just base64 encode)
    header_encoded = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip('=')
    payload_encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip('=')
    
    # Fake signature for demo
    signature = base64.urlsafe_b64encode(b"fake_signature_for_demo").decode().rstrip('=')
    
    # Combine
    token = f"{header_encoded}.{payload_encoded}.{signature}"
    
    return token

if __name__ == "__main__":
    token = create_test_jwt()
    print("Test JWT Token:")
    print(token)
    print()
    print("This token grants access to:")
    print("- Tenants: tenant-a, tenant-b")
    print("- Permissions: sftp:read, sftp:process, admin")
    print("- Valid for: 2 hours")
    print()
    print("Usage:")
    print(f'export TEST_JWT="{token}"')
    print('./run.sh dev:sftp:process --auth-token "$TEST_JWT" --tenant tenant-a --list-partners')