#!/usr/bin/env python3
"""
EDI Lens Generic API Test Script
===============================
This script demonstrates how to access various backend APIs through the API
using proper authentication.
"""

import argparse
import json
import os
import sys
import requests
from typing import Optional

# Add the scripts directory to the path so we can import our get_auth_token module
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

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
    """Test API access with proper authentication."""
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

def main():
    parser = argparse.ArgumentParser(
        description="Test EDI Lens backend APIs with proper authentication",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List workflow templates
  python test_api.py

  # Get a specific template
  python test_api.py -e /api/v1/workflow-templates/global-batch-edi-processor-v1.0

  # List schemas
  python test_api.py -e /api/v1/schemas

  # Create a new schema (example)
  python test_api.py -m POST -e /api/v1/schemas -d '{"name":"test","content":"{}"}'
        """
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
        default="http://localhost:8081",
        help="Keycloak URL (default: http://localhost:8081)"
    )
    parser.add_argument(
        "-r", "--realm",
        default="edi-lens",
        help="Keycloak realm (default: edi-lens)"
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
    print("🧪 Testing EDI Lens API")
    print("========================")
    
    # Get authentication token
    print(f"🔑 Getting authentication token for {args.user}...")
    try:
        token = get_auth_token(
            args.user, args.password, args.tenant, args.keycloak, args.realm
        )
        print("✅ Token generated successfully")
    except Exception as e:
        print(f"❌ Failed to generate token: {e}")
        sys.exit(1)
    
    # Test API access
    print()
    print("📋 Testing API access...")
    print(f"  Method: {args.method}")
    print(f"  Endpoint: {args.endpoint}")
    print(f"  Tenant: {args.tenant}")
    
    if args.verbose and data:
        print(f"  Data: {json.dumps(data, indent=2)}")
    
    try:
        response = test_api(args.endpoint, args.method, data, token, args.tenant)
        print("✅ API access successful")
        
        # Pretty print response
        print(json.dumps(response, indent=2))
        
    except requests.exceptions.RequestException as e:
        print(f"❌ API access failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)
    
    print()
    print("🎉 API test completed successfully!")

if __name__ == "__main__":
    main()