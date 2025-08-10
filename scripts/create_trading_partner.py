#!/usr/bin/env python3
"""
Create a trading partner with profile configuration.

This script allows creating trading partners either interactively or with command-line arguments.
It uses the API to create trading partners, handling authentication internally.
"""

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path
from typing import List, Optional
import httpx
import json

# Load environment variables
from dotenv import load_dotenv

# Load .env file from project root
project_root = Path(__file__).parent
env_file = project_root / ".env.dev"
if env_file.exists():
    load_dotenv(env_file)
else:
    # Try to find .env file in parent directories
    for parent in project_root.parents:
        env_file = parent / ".env.dev"
        if env_file.exists():
            load_dotenv(env_file)
            break

# Add backend to path for imports if needed
backend_path = project_root / "backend"
sys.path.append(str(backend_path))

# Import for JWT creation
import base64
from datetime import datetime, timedelta

# Available SNIP levels
SNIP_LEVELS = ["SNIP1", "SNIP2", "SNIP3", "SNIP4", "SNIP5", "SNIP6"]

# Default schemas (would normally be loaded from the system)
DEFAULT_SCHEMAS = [
    "837.5010.X222.A1.json",
    "837.5010.X223.A1.json",
    "835.5010.X221.A1.json",
    "834.5010.X220.A1.json",
    "270.5010.X279.A1.json",
    "271.5010.X279.A1.json",
    "999.5010.X231.A1.json"
]


def create_test_jwt():
    """Create a test JWT token for API authentication."""
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
            "roles": ["trading-partners:create", "trading-partners:read", "admin"]
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


async def get_available_schemas() -> List[str]:
    """Get list of available schemas (placeholder implementation)."""
    # In a real implementation, we might call an API endpoint to get available schemas
    return DEFAULT_SCHEMAS


def prompt_with_default(prompt: str, default: str = "", required: bool = True) -> str:
    """Prompt user for input with a default value."""
    if default:
        full_prompt = f"{prompt} [{default}]: "
    else:
        full_prompt = f"{prompt}: "
    
    while True:
        value = input(full_prompt).strip()
        if value:
            return value
        elif default:
            return default
        elif not required:
            return value
        else:
            print("This field is required.")


def prompt_choice(prompt: str, choices: List[str], default: str = "") -> str:
    """Prompt user to select from a list of choices."""
    print(f"{prompt}")
    for i, choice in enumerate(choices, 1):
        if choice == default:
            print(f"  {i}. {choice} (default)")
        else:
            print(f"  {i}. {choice}")
    
    while True:
        choice = input(f"Enter choice (1-{len(choices)}){f' [{choices.index(default)+1}]' if default else ''}: ").strip()
        
        if not choice and default:
            return default
        elif choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(choices):
                return choices[idx]
        
        print(f"Please enter a number between 1 and {len(choices)}.")


async def interactive_create_partner() -> dict:
    """Interactively create a trading partner."""
    print("\n=== Create Trading Partner ===")
    
    # Get partner details
    name = prompt_with_default("Partner Name")
    
    description = prompt_with_default("Description", required=False)
    if not description:
        description = None
    
    # SFTP configuration
    sftp_enabled_input = prompt_with_default("Enable SFTP? (y/n)", "n")
    sftp_enabled = sftp_enabled_input.lower() in ['y', 'yes']
    
    sftp_username = None
    sftp_password = None
    if sftp_enabled:
        sftp_username = prompt_with_default("SFTP Username")
        sftp_password = prompt_with_default("SFTP Password (for upload script)", "test123")

    # Get available schemas
    schemas = await get_available_schemas()
    
    # Create profile
    print("\n=== Create Profile ===")
    profile_name = prompt_with_default("Profile Name", "default")
    
    validation_schema = prompt_choice(
        "Select Validation Schema:", 
        schemas, 
        schemas[0] if schemas else "837.5010.X222.A1.json"
    )
    
    snip_level = prompt_choice(
        "Select SNIP Level:", 
        SNIP_LEVELS, 
        "SNIP3"
    )
    
    generate_ta1_input = prompt_with_default("Generate TA1 Acknowledgements? (y/n)", "y")
    generate_ta1 = generate_ta1_input.lower() in ['y', 'yes']
    
    generate_999_input = prompt_with_default("Generate 999 Acknowledgements? (y/n)", "n")
    generate_999 = generate_999_input.lower() in ['y', 'yes']
    
    # Create the profile
    profile = {
        "name": profile_name,
        "validation_schema_name": validation_schema,
        "snip_level": snip_level,
        "generate_ta1": generate_ta1,
        "generate_999": generate_999
    }
    
    # Create the partner
    partner = {
        "name": name,
        "description": description,
        "profiles": [profile],
        "sftp_enabled": sftp_enabled,
        "sftp_username": sftp_username,
        "sftp_password": sftp_password  # Store password for SFTP user creation
    }
    
    return partner


def create_partner_with_args(
    name: str,
    description: Optional[str],
    sftp_enabled: bool,
    sftp_username: Optional[str],
    sftp_password: Optional[str],
    profile_name: str,
    validation_schema: str,
    snip_level: str,
    generate_ta1: bool,
    generate_999: bool
) -> dict:
    """Create a trading partner with provided arguments."""
    # Validate SNIP level
    if snip_level not in SNIP_LEVELS:
        raise ValueError(f"Invalid SNIP level. Must be one of: {', '.join(SNIP_LEVELS)}")
    
    # Create the profile
    profile = {
        "name": profile_name,
        "validation_schema_name": validation_schema,
        "snip_level": snip_level,
        "generate_ta1": generate_ta1,
        "generate_999": generate_999
    }
    
    # Create the partner
    partner = {
        "name": name,
        "description": description,
        "profiles": [profile],
        "sftp_enabled": sftp_enabled,
        "sftp_username": sftp_username,
        "sftp_password": sftp_password  # Store password for SFTP user creation
    }
    
    return partner


async def get_user_token(username: str, password: str = "password", internal: bool = False) -> str:
    """Fetches a valid access token using the password grant flow."""
    # Keycloak token endpoint
    if internal:
        # Internal URL when running inside Docker network
        token_url = "http://keycloak:8080/realms/edi-lens/protocol/openid-connect/token"
    else:
        # External URL when running from host
        token_url = "http://localhost:8081/realms/edi-lens/protocol/openid-connect/token"
    
    # Payload for token request using password grant
    payload = {
        "grant_type": "password",
        "client_id": "edi-lens-backend",
        "client_secret": "this-is-a-very-secret-key-change-it",
        "username": username,
        "password": password,
        "audience": "edi-lens-backend",  # Specify the audience
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(token_url, data=payload, timeout=10.0)
            response.raise_for_status()
            token_data = response.json()
            return token_data["access_token"]
        except httpx.HTTPStatusError as e:
            error_text = await e.response.aread()
            raise Exception(f"HTTP {e.response.status_code} error getting token for user {username} from Keycloak: {error_text.decode()}")
        except (httpx.RequestError, KeyError, json.JSONDecodeError) as e:
            raise Exception(f"Could not get token for user {username} from Keycloak: {e}")


async def set_sftp_user_password(username: str, password: str):
    """Set the password for an SFTP user via the SFTPGo API."""
    try:
        # Get SFTPGo admin credentials from environment
        sftpgo_admin_user = os.getenv("SFTPGO_ADMIN_USER", "admin")
        sftpgo_admin_password = os.getenv("SFTPGO_ADMIN_PASSWORD", "admin123")
        
        # Authenticate with SFTPGo to get a token
        auth_credentials = f"{sftpgo_admin_user}:{sftpgo_admin_password}"
        encoded_credentials = base64.b64encode(auth_credentials.encode()).decode()
        auth_headers = {"Authorization": f"Basic {encoded_credentials}"}
        
        async with httpx.AsyncClient() as client:
            # Get authentication token
            token_response = await client.get("http://localhost:8082/api/v2/token", headers=auth_headers, timeout=10)
            token_response.raise_for_status()
            access_token = token_response.json().get("access_token")
            
            if not access_token:
                print("❌ Failed to get SFTPGo access token")
                return False
            
            # First, get the current user details
            get_headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            get_response = await client.get(
                f"http://localhost:8082/api/v2/users/{username}",
                headers=get_headers,
                timeout=15
            )
            
            if get_response.status_code != 200:
                print(f"❌ Failed to get SFTP user '{username}' details: {get_response.status_code} - {get_response.text}")
                return False
            
            user_data = get_response.json()
            
            # Update user with password, keeping existing permissions and other settings
            update_headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            # Add password to the existing user data
            user_data["password"] = password
            
            update_response = await client.put(
                f"http://localhost:8082/api/v2/users/{username}",
                json=user_data,
                headers=update_headers,
                timeout=15
            )
            
            if update_response.status_code == 200:
                print(f"✅ Successfully set password for SFTP user '{username}'")
                return True
            else:
                print(f"❌ Failed to set password for SFTP user '{username}': {update_response.status_code} - {update_response.text}")
                return False
                
    except Exception as e:
        print(f"❌ Error setting password for SFTP user '{username}': {e}")
        return False

async def save_partner(partner: dict, tenant_id: str, internal: bool = False):
    """Save the trading partner using the API."""
    try:
        # Get JWT token for authentication using the superuser account
        jwt_token = await get_user_token("superuser@edilens.com", "password", internal)
    except Exception as e:
        print(f"\n❌ Failed to get authentication token: {e}")
        return
    
    # API endpoint
    if internal:
        # Internal URL when running inside Docker network
        api_url = "http://backend:8000/api/v1/trading-partners"
    else:
        # External URL when running from host through Caddy proxy
        api_url = "http://localhost:3001/api/v1/trading-partners"
    
    # Headers
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "X-Tenant-ID": tenant_id,
        "Content-Type": "application/json"
    }
    
    # Send POST request to create partner
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(api_url, json=partner, headers=headers)
            response.raise_for_status()
            
            # Parse response
            result = response.json()
            
            print(f"\n✅ Successfully created trading partner '{result['name']}' with ID {result['id']}")
            if result.get('sftp_enabled') and result.get('sftp_username'):
                print(f"📁 SFTP enabled with username: {result['sftp_username']}")
                # Set password for SFTP user if provided
                sftp_password = partner.get('sftp_password')
                if sftp_password:
                    await set_sftp_user_password(result['sftp_username'], sftp_password)
            
            for profile in result['profiles']:
                print(f"📄 Profile: {profile['name']}")
                print(f"   Schema: {profile['validation_schema_name']}")
                print(f"   SNIP Level: {profile['snip_level']}")
                print(f"   TA1 Generation: {'Yes' if profile['generate_ta1'] else 'No'}")
                print(f"   999 Generation: {'Yes' if profile['generate_999'] else 'No'}")
            
            return result
        except httpx.HTTPStatusError as e:
            error_detail = e.response.text
            print(f"\n❌ HTTP error occurred: {e}")
            print(f"Response: {error_detail}")
            raise
        except httpx.RequestError as e:
            print(f"\n❌ Request error occurred: {e}")
            raise
        except Exception as e:
            print(f"\n❌ Unexpected error occurred: {e}")
            raise


async def main():
    parser = argparse.ArgumentParser(description="Create a trading partner with profile configuration")
    parser.add_argument("--name", help="Partner name")
    parser.add_argument("--description", help="Partner description")
    parser.add_argument("--sftp-enabled", action="store_true", help="Enable SFTP for this partner")
    parser.add_argument("--sftp-username", help="SFTP username")
    parser.add_argument("--sftp-password", default="test123", help="SFTP password (default: test123)")
    parser.add_argument("--profile-name", default="default", help="Profile name (default: default)")
    parser.add_argument("--schema", help="Validation schema name")
    parser.add_argument("--snip-level", choices=SNIP_LEVELS, default="SNIP3", help="SNIP validation level")
    parser.add_argument("--generate-ta1", action="store_true", help="Generate TA1 acknowledgements")
    parser.add_argument("--no-generate-ta1", action="store_true", help="Do not generate TA1 acknowledgements")
    parser.add_argument("--generate-999", action="store_true", help="Generate 999 acknowledgements")
    parser.add_argument("--tenant-id", default="tenant-a", help="Tenant ID (default: tenant-a)")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive mode")
    parser.add_argument("--list-schemas", action="store_true", help="List available schemas and exit")
    parser.add_argument("--internal", action="store_true", help="Run in internal mode (for Docker container)")
    parser.add_argument("--unique", action="store_true", help="Add timestamp to partner name and SFTP username to ensure uniqueness")
    
    args = parser.parse_args()
    
    # Handle schema listing
    if args.list_schemas:
        schemas = await get_available_schemas()
        print("Available schemas:")
        for schema in schemas:
            print(f"  - {schema}")
        return
    
    # Determine mode
    interactive_mode = args.interactive or not args.name
    
    if interactive_mode:
        # Interactive mode
        partner = await interactive_create_partner()
        tenant_id = prompt_with_default("Tenant ID", "tenant-a")
    else:
        # Command-line mode
        # Handle TA1 generation flags
        generate_ta1 = True  # Default
        if args.no_generate_ta1:
            generate_ta1 = False
        elif args.generate_ta1:
            generate_ta1 = True
            
        # Get available schemas for validation if schema is not provided
        if not args.schema:
            schemas = await get_available_schemas()
            if schemas:
                schema = schemas[0]  # Use first schema as default
            else:
                schema = "837.5010.X222.A1.json"  # Fallback
        else:
            schema = args.schema
            
        # Add timestamp to ensure uniqueness if requested
        partner_name = args.name
        sftp_username = args.sftp_username
        if args.unique:
            timestamp = str(int(time.time()))
            partner_name = f"{args.name} {timestamp}"
            if args.sftp_username:
                sftp_username = f"{args.sftp_username}{timestamp}"
            
        partner = create_partner_with_args(
            name=partner_name,
            description=args.description,
            sftp_enabled=args.sftp_enabled,
            sftp_username=sftp_username,
            sftp_password=args.sftp_password,
            profile_name=args.profile_name,
            validation_schema=schema,
            snip_level=args.snip_level,
            generate_ta1=generate_ta1,
            generate_999=args.generate_999
        )
        tenant_id = args.tenant_id
    
    # Confirm before creating
    print("\n=== Partner Summary ===")
    print(f"Name: {partner['name']}")
    print(f"Description: {partner['description'] or 'None'}")
    print(f"SFTP Enabled: {'Yes' if partner['sftp_enabled'] else 'No'}")
    if partner['sftp_enabled']:
        print(f"SFTP Username: {partner['sftp_username']}")
        if partner.get('sftp_password'):
            print(f"SFTP Password: {partner['sftp_password']}")
    
    for profile in partner['profiles']:
        print(f"\nProfile: {profile['name']}")
        print(f"  Schema: {profile['validation_schema_name']}")
        print(f"  SNIP Level: {profile['snip_level']}")
        print(f"  Generate TA1: {'Yes' if profile['generate_ta1'] else 'No'}")
        print(f"  Generate 999: {'Yes' if profile['generate_999'] else 'No'}")
    
    if interactive_mode:
        confirm = prompt_with_default("\nCreate this partner? (y/n)", "y")
        if confirm.lower() not in ['y', 'yes']:
            print("Cancelled.")
            return
    
    # Save the partner
    await save_partner(partner, tenant_id, args.internal)


if __name__ == "__main__":
    asyncio.run(main())