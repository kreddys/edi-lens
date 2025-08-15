#!/usr/bin/env python3
"""
EDI Lens Authentication Token Helper Script

Generates JWT tokens for testing EDI validation endpoints and service authentication.
Supports both user tokens and service account tokens for NiFi integration.
"""

import argparse
import base64
import json
import sys
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

import requests


class Colors:
    """ANSI color codes for terminal output."""
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'  # No Color


def info(msg: str) -> None:
    """Print info message."""
    print(f"{Colors.BLUE}[INFO]{Colors.NC} {msg}")


def success(msg: str) -> None:
    """Print success message."""
    print(f"{Colors.GREEN}[SUCCESS]{Colors.NC} {msg}")


def warn(msg: str) -> None:
    """Print warning message."""
    print(f"{Colors.YELLOW}[WARN]{Colors.NC} {msg}")


def error(msg: str) -> None:
    """Print error message."""
    print(f"{Colors.RED}[ERROR]{Colors.NC} {msg}", file=sys.stderr)


def create_mock_service_token(service_name: str, client_id: str, verbose: bool = False) -> str:
    """
    Create a mock JWT token for service account authentication.
    
    Note: This is for development/testing only. In production, use proper Keycloak service account authentication.
    """
    current_time = int(time.time())
    expiry_time = current_time + 3600  # 1 hour from now
    
    # JWT Header
    header = {
        "alg": "HS256",
        "typ": "JWT"
    }
    
    # JWT Payload - Match what the backend expects
    payload = {
        "sub": f"service-account-{service_name}",
        "azp": service_name,  # Authorized party - this is critical for our service auth
        "preferred_username": f"{service_name}-processor",
        "email": f"{service_name}@edi-lens.local",
        "aud": client_id,
        "iss": "edi-lens-test",
        "iat": current_time,
        "exp": expiry_time,
        "realm_access": {
            "roles": ["edi:process", "edi:validate", "edi:generate-acknowledgments"]
        }
    }
    
    if verbose:
        info(f"Generating service account token for: {service_name}")
        info(f"Token payload: {json.dumps(payload, indent=2)}")
        info(f"Token valid until: {datetime.fromtimestamp(expiry_time)}")
    
    # Create base64 encoded parts
    header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip('=')
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip('=')
    
    # For development, use a fake signature
    signature = "fake_signature_for_demo"
    
    token = f"{header_b64}.{payload_b64}.{signature}"
    
    if verbose:
        success("Service token generated successfully")
    
    return token


def get_service_token_from_keycloak(
    service_name: str,
    keycloak_url: str,
    realm: str,
    client_id: str,
    verbose: bool = False
) -> str:
    """Get service account token from Keycloak using client credentials grant."""
    
    if verbose:
        info(f"Authenticating service account: {service_name}")
        info(f"Keycloak URL: {keycloak_url}")
        info(f"Client ID: {client_id}")
    
    # Map service names to actual client IDs in Keycloak
    client_id_mapping = {
        "nifi-service": "nifi-service",
        "edi-lens-backend": "edi-lens-backend",
        "backend": "edi-lens-backend"
    }
    
    actual_client_id = client_id_mapping.get(service_name, service_name)
    client_secret = "nifi-service-secret" if actual_client_id == "nifi-service" else "this-is-a-very-secret-key-change-it"
    
    token_url = f"{keycloak_url}/realms/{realm}/protocol/openid-connect/token"
    
    data = {
        "grant_type": "client_credentials",
        "client_id": actual_client_id,
        "client_secret": client_secret,
        "scope": "openid profile email"
    }
    
    try:
        response = requests.post(token_url, data=data, timeout=30)
        response.raise_for_status()
        
        token_data = response.json()
        access_token = token_data.get("access_token")
        
        if not access_token:
            error_msg = token_data.get("error_description", token_data.get("error", "Unknown error"))
            error(f"Service authentication failed: {error_msg}")
            sys.exit(1)
        
        if verbose:
            success("Service authentication successful")
            expires_in = token_data.get("expires_in")
            if expires_in:
                info(f"Token expires in: {expires_in} seconds")
        
        return access_token
        
    except requests.exceptions.RequestException as e:
        error(f"Failed to connect to Keycloak: {e}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        error(f"Invalid JSON response from Keycloak: {e}")
        sys.exit(1)


def get_user_token_from_keycloak(
    username: str,
    password: str,
    tenant_id: str,
    keycloak_url: str,
    realm: str,
    client_id: str,
    verbose: bool = False
) -> str:
    """Get user token from Keycloak using password grant."""
    
    if verbose:
        info(f"Authenticating user: {username}")
        info(f"Tenant: {tenant_id}")
        info(f"Keycloak URL: {keycloak_url}")
    
    token_url = f"{keycloak_url}/realms/{realm}/protocol/openid-connect/token"
    
    data = {
        "grant_type": "password",
        "client_id": client_id,
        "username": username,
        "password": password,
        "scope": "openid profile email groups"
    }
    
    try:
        response = requests.post(token_url, data=data, timeout=30)
        response.raise_for_status()
        
        token_data = response.json()
        access_token = token_data.get("access_token")
        
        if not access_token:
            error_msg = token_data.get("error_description", token_data.get("error", "Unknown error"))
            error(f"Authentication failed: {error_msg}")
            sys.exit(1)
        
        if verbose:
            success("User authentication successful")
            expires_in = token_data.get("expires_in")
            if expires_in:
                info(f"Token expires in: {expires_in} seconds")
        
        return access_token
        
    except requests.exceptions.RequestException as e:
        error(f"Failed to connect to Keycloak: {e}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        error(f"Invalid JSON response from Keycloak: {e}")
        sys.exit(1)


def validate_token_format(token: str, verbose: bool = False) -> bool:
    """Validate JWT token format and optionally decode payload for debugging."""
    
    parts = token.split('.')
    if len(parts) != 3:
        warn("Token does not appear to be in JWT format (expected 3 parts separated by dots)")
        return False
    
    if verbose:
        try:
            # Decode payload for debugging
            payload_b64 = parts[1]
            # Add padding if needed
            padding = 4 - len(payload_b64) % 4
            if padding != 4:
                payload_b64 += '=' * padding
            
            payload_bytes = base64.urlsafe_b64decode(payload_b64)
            payload = json.loads(payload_bytes)
            info(f"Token payload: {json.dumps(payload, indent=2)}")
            
            # Check expiration
            exp = payload.get('exp')
            if exp:
                exp_time = datetime.fromtimestamp(exp)
                if exp_time > datetime.now():
                    info(f"Token expires at: {exp_time}")
                else:
                    warn(f"Token expired at: {exp_time}")
            
        except Exception as e:
            warn(f"Unable to decode token payload: {e}")
    
    return True


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="EDI Lens Authentication Token Helper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Get service token for NiFi (real token from Keycloak)
  python scripts/get_auth_token.py --service nifi-service --real

  # Get service token for NiFi (mock token for development)
  python scripts/get_auth_token.py --service nifi-service

  # Get user token for admin user  
  python scripts/get_auth_token.py --user admin --password admin --tenant tenant-a

  # Test EDI endpoint with generated token
  TOKEN=$(python scripts/get_auth_token.py --service nifi-service --real)
  curl -H "Authorization: Bearer $TOKEN" \\
       -H "Content-Type: application/json" \\
       -d '{"edi_content":"...","tenant_id":"tenant-a","workflow_id":"test","validation_schema":"test"}' \\
       http://localhost:3001/api/v1/edi/validate-realtime
        """
    )
    
    # Token type options
    token_group = parser.add_mutually_exclusive_group(required=True)
    token_group.add_argument(
        "--service",
        help="Generate service account token (e.g., nifi-service)"
    )
    token_group.add_argument(
        "--user",
        help="Generate user token for specified username"
    )
    
    # Service authentication options
    parser.add_argument(
        "--real",
        action="store_true",
        help="Get real token from Keycloak instead of mock token"
    )
    
    # User authentication options
    parser.add_argument(
        "--password",
        help="Password for user authentication (required with --user)"
    )
    parser.add_argument(
        "--tenant",
        help="Tenant ID for user tokens (required with --user)"
    )
    
    # Keycloak configuration
    parser.add_argument(
        "--keycloak-url",
        default="http://localhost:8081",
        help="Keycloak URL (default: http://localhost:8081)"
    )
    parser.add_argument(
        "--realm",
        default="edi-lens",
        help="Keycloak realm (default: edi-lens)"
    )
    parser.add_argument(
        "--client-id",
        default="nifi-service",
        help="Client ID (default: nifi-service)"
    )
    
    # Output options
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    
    args = parser.parse_args()
    
    # Validation
    if args.user and not args.password:
        error("Password required when using --user")
        sys.exit(1)
    
    if args.user and not args.tenant:
        error("Tenant ID required when using --user")
        sys.exit(1)
    
    # Generate token
    token = None
    
    if args.service:
        if args.real:
            token = get_service_token_from_keycloak(
                service_name=args.service,
                keycloak_url=args.keycloak_url,
                realm=args.realm,
                client_id=args.client_id,
                verbose=args.verbose
            )
        else:
            token = create_mock_service_token(
                service_name=args.service,
                client_id=args.client_id,
                verbose=args.verbose
            )
    elif args.user:
        token = get_user_token_from_keycloak(
            username=args.user,
            password=args.password,
            tenant_id=args.tenant,
            keycloak_url=args.keycloak_url,
            realm=args.realm,
            client_id=args.client_id,
            verbose=args.verbose
        )
    
    if not token:
        error("Failed to generate token")
        sys.exit(1)
    
    # Validate token format
    if not validate_token_format(token, verbose=args.verbose):
        error("Generated token appears to be invalid")
        sys.exit(1)
    
    # Output token (this is what gets captured when script is used in command substitution)
    print(token)
    
    if args.verbose:
        success("Token generated successfully!")
        info("You can now use this token to test EDI endpoints:")
        print()
        print(f"export TOKEN='{token}'")
        print('curl -H "Authorization: Bearer $TOKEN" \\')
        print('     -H "Content-Type: application/json" \\')
        print('     -d \'{"edi_content":"test","tenant_id":"tenant-a","workflow_id":"test","validation_schema":"test"}\' \\')
        print('     http://localhost:3001/api/v1/edi/validate-realtime')


if __name__ == "__main__":
    main()