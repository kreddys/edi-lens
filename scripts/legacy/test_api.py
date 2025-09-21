#!/usr/bin/env python3
"""
EDI Lens Generic API Test Script
===============================
This script demonstrates how to access various backend APIs, NiFi APIs, and NiFi Registry APIs
using proper authentication.
"""

import argparse
import json
import os
import sys
import requests
import base64
from typing import Optional
from urllib3.exceptions import InsecureRequestWarning
from dotenv import load_dotenv

# Disable SSL warnings for self-signed certificates
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# Add the scripts directory to the path so we can import our get_auth_token module
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# Load environment variables from .env.dev
env_file = os.path.join(os.path.dirname(__file__), '..', '.env.dev')
if os.path.exists(env_file):
    load_dotenv(env_file)

def get_auth_token(username: str, password: str, tenant: str, keycloak_url: str, realm: str) -> str:
    """Get authentication token using our get_auth_token script."""
    import subprocess
    import tempfile
    
    # Create a temporary script to get the token without verbose output
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write('''
import sys
sys.path.append(".")
from auth_token_helper import get_user_token_from_keycloak
token = get_user_token_from_keycloak(
    username=sys.argv[1],
    password=sys.argv[2],
    tenant_id=sys.argv[3],
    keycloak_url=sys.argv[4],
    realm=sys.argv[5],
    verbose=False
)
print(token)
''')
        temp_script = f.name
    
    try:
        # Run the temporary script
        result = subprocess.run([
            'python', temp_script, username, password, tenant, keycloak_url, realm
        ], capture_output=True, text=True, cwd=os.path.dirname(__file__))
        
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            raise Exception(f"Failed to get token: {result.stderr}")
    finally:
        # Clean up the temporary script
        os.unlink(temp_script)

def test_api(
    endpoint: str,
    method: str = "GET",
    data: Optional[dict] = None,
    token: str = "",
    tenant: str = "tenant-a"
) -> dict:
    """Test backend API access with proper authentication."""
    url = f"http://localhost:3001{endpoint}"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": tenant
    }
    
    if data:
        headers["Content-Type"] = "application/json"
    
    # Handle tenant_id parameter for workflows endpoint
    params = {}
    if "/workflows" in endpoint and method == "GET":
        params["tenant_id"] = tenant
    
    response = requests.request(method, url, headers=headers, json=data, params=params)
    response.raise_for_status()
    
    try:
        return response.json()
    except json.JSONDecodeError:
        return {"text": response.text}

def test_nifi_api(
    endpoint: str,
    method: str = "GET",
    data: Optional[dict] = None,
    username: str = None,
    password: str = None,
    base_url: str = "http://localhost:8080"
) -> dict:
    """Test NiFi API access via Caddy proxy."""
    # Use environment variables as defaults if not provided
    if username is None:
        username = os.getenv("NIFI_ADMIN_USER", "admin")
    if password is None:
        password = os.getenv("NIFI_ADMIN_PASSWORD", "admin123")
    
    url = f"{base_url}/nifi-api{endpoint}"
    
    # Handle special case for token endpoint (requires form data)
    if endpoint == "/access/token" and method == "POST":
        form_data = {"username": username, "password": password}
        response = requests.post(url, data=form_data, verify=False)
        response.raise_for_status()
        return {"token": response.text}
    
    headers = {
        "Content-Type": "application/json"
    }
    
    # For direct NiFi access (https), use basic auth
    if base_url.startswith("https://"):
        credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
        headers["Authorization"] = f"Basic {credentials}"
        verify_ssl = False
    else:
        # For Caddy proxy access (http), no auth needed
        verify_ssl = True
    
    response = requests.request(
        method, url, headers=headers, json=data, verify=verify_ssl
    )
    response.raise_for_status()
    
    try:
        return response.json()
    except json.JSONDecodeError:
        return {"text": response.text}

def test_nifi_registry_api(
    endpoint: str,
    method: str = "GET",
    data: Optional[dict] = None,
    base_url: str = "http://localhost:18080"
) -> dict:
    """Test NiFi Registry API access (no auth required in dev)."""
    url = f"{base_url}/nifi-registry-api{endpoint}"
    
    headers = {
        "Content-Type": "application/json"
    }
    
    response = requests.request(
        method, url, headers=headers, json=data
    )
    response.raise_for_status()
    
    try:
        return response.json()
    except json.JSONDecodeError:
        return {"text": response.text}

def main():
    parser = argparse.ArgumentParser(
        description="Test EDI Lens backend APIs, NiFi APIs, and NiFi Registry APIs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Backend API - List workflow templates
  python test_api.py

  # Backend API - Get a specific template
  python test_api.py -e /api/v1/workflow-templates/global-batch-edi-processor-v1.0

  # Backend API - List schemas
  python test_api.py -e /api/v1/schemas

  # NiFi API - Get root process group
  python test_api.py --api-type nifi -e /process-groups/root

  # NiFi API - List process groups
  python test_api.py --api-type nifi -e /process-groups/root/process-groups

  # NiFi Registry API - List buckets
  python test_api.py --api-type nifi-registry -e /buckets

  # NiFi Registry API - List flows in a bucket
  python test_api.py --api-type nifi-registry -e /buckets/{bucket-id}/flows
        """
    )
    
    parser.add_argument(
        "--api-type",
        choices=["backend", "nifi", "nifi-registry"],
        default="backend",
        help="API type to test (default: backend)"
    )
    parser.add_argument(
        "-u", "--user",
        default="superuser@edilens.com",
        help="Username for authentication (default: superuser@edilens.com)"
    )
    parser.add_argument(
        "-p", "--password",
        default="password",
        help="Password for authentication (default: password)"
    )
    parser.add_argument(
        "--nifi-user",
        default=os.getenv("NIFI_ADMIN_USER", "admin"),
        help=f"NiFi username (default: {os.getenv('NIFI_ADMIN_USER', 'admin')})"
    )
    parser.add_argument(
        "--nifi-password",
        default=os.getenv("NIFI_ADMIN_PASSWORD", "admin123"),
        help="NiFi password (from NIFI_ADMIN_PASSWORD env var)"
    )
    parser.add_argument(
        "-t", "--tenant",
        default="tenant-a",
        help="Tenant ID (default: tenant-a)"
    )
    parser.add_argument(
        "-e", "--endpoint",
        default="/api/v1/workflow-templates",
        help="API endpoint (default: /api/v1/workflow-templates)"
    )
    parser.add_argument(
        "-m", "--method",
        default="GET",
        help="HTTP method (default: GET)"
    )
    parser.add_argument(
        "-d", "--data",
        help="Request data for POST/PUT (JSON format)"
    )
    parser.add_argument(
        "-k", "--keycloak",
        default=os.getenv("KEYCLOAK_BROWSER_URL", "http://localhost:8081"),
        help=f"Keycloak URL (default: {os.getenv('KEYCLOAK_BROWSER_URL', 'http://localhost:8081')})"
    )
    parser.add_argument(
        "-r", "--realm",
        default=os.getenv("KEYCLOAK_REALM", "edi-lens"),
        help=f"Keycloak realm (default: {os.getenv('KEYCLOAK_REALM', 'edi-lens')})"
    )
    parser.add_argument(
        "--nifi-url",
        default="http://localhost:8080",
        help="NiFi URL via Caddy proxy (default: http://localhost:8080)"
    )
    parser.add_argument(
        "--nifi-registry-url",
        default="http://localhost:18080",
        help="NiFi Registry URL via Caddy proxy (default: http://localhost:18080)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    
    args = parser.parse_args()
    
    # Parse data if provided
    data = None
    if args.data:
        try:
            data = json.loads(args.data)
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON data: {e}")
            sys.exit(1)
    
    # Print header
    print(f"🧪 Testing EDI Lens {args.api_type.upper()} API")
    print("=" * (len(f"Testing EDI Lens {args.api_type.upper()} API") + 4))
    
    # Handle different API types
    if args.api_type == "backend":
        # Get authentication token for backend API
        print(f"🔑 Getting authentication token for {args.user}...")
        try:
            token = get_auth_token(
                args.user, args.password, args.tenant, args.keycloak, args.realm
            )
            print("✅ Token generated successfully")
        except Exception as e:
            print(f"❌ Failed to generate token: {e}")
            sys.exit(1)
        
        # Test backend API access
        print()
        print("📋 Testing Backend API access...")
        print(f"  Method: {args.method}")
        print(f"  Endpoint: {args.endpoint}")
        print(f"  Tenant: {args.tenant}")
        
        if args.verbose and data:
            print(f"  Data: {json.dumps(data, indent=2)}")
        
        try:
            response = test_api(args.endpoint, args.method, data, token, args.tenant)
            print("✅ Backend API access successful")
            print(json.dumps(response, indent=2))
        except requests.exceptions.RequestException as e:
            print(f"❌ Backend API access failed: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            sys.exit(1)
            
    elif args.api_type == "nifi":
        # Test NiFi API access
        print()
        print("📋 Testing NiFi API access...")
        print(f"  Method: {args.method}")
        print(f"  Endpoint: {args.endpoint}")
        print(f"  NiFi URL: {args.nifi_url}")
        print(f"  Username: {args.nifi_user}")
        
        if args.verbose and data:
            print(f"  Data: {json.dumps(data, indent=2)}")
        
        try:
            response = test_nifi_api(
                args.endpoint, args.method, data, 
                args.nifi_user, args.nifi_password, args.nifi_url
            )
            print("✅ NiFi API access successful")
            print(json.dumps(response, indent=2))
        except requests.exceptions.RequestException as e:
            print(f"❌ NiFi API access failed: {e}")
            if args.verbose:
                if hasattr(e, 'response') and e.response is not None:
                    print(f"   Response status: {e.response.status_code}")
                    print(f"   Response text: {e.response.text}")
                else:
                    print(f"   Full error: {str(e)}")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            sys.exit(1)
            
    elif args.api_type == "nifi-registry":
        # Test NiFi Registry API access
        print()
        print("📋 Testing NiFi Registry API access...")
        print(f"  Method: {args.method}")
        print(f"  Endpoint: {args.endpoint}")
        print(f"  Registry URL: {args.nifi_registry_url}")
        
        if args.verbose and data:
            print(f"  Data: {json.dumps(data, indent=2)}")
        
        try:
            response = test_nifi_registry_api(
                args.endpoint, args.method, data, args.nifi_registry_url
            )
            print("✅ NiFi Registry API access successful")
            print(json.dumps(response, indent=2))
        except requests.exceptions.RequestException as e:
            print(f"❌ NiFi Registry API access failed: {e}")
            if args.verbose:
                if hasattr(e, 'response') and e.response is not None:
                    print(f"   Response status: {e.response.status_code}")
                    print(f"   Response text: {e.response.text}")
                else:
                    print(f"   Full error: {str(e)}")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            sys.exit(1)
    
    print()
    print("🎉 API test completed successfully!")

if __name__ == "__main__":
    main()