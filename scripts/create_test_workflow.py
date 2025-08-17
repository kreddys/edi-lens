#!/usr/bin/env python3
"""
Create Test Workflow Script

Creates a test workflow for debugging the workflows UI.
"""

import argparse
import json
import os
import sys
from typing import Optional

import requests

# Add the backend to the Python path so we can import our auth helper
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from get_auth_token import get_user_token_from_keycloak


def create_workflow(
    token: str,
    tenant_id: str,
    api_url: str,
    template_id: str,
    verbose: bool = False
) -> dict:
    """Create a workflow using the API."""
    
    workflow_data = {
        "name": "Test Workflow",
        "description": "A test workflow for debugging",
        "template_id": template_id,
        "configuration": {}
    }
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-Tenant-ID": tenant_id
    }
    
    if verbose:
        print(f"Creating workflow with data: {json.dumps(workflow_data, indent=2)}")
        print(f"Headers: {headers}")
    
    try:
        response = requests.post(
            f"{api_url}/api/v1/workflows/", 
            json=workflow_data, 
            headers=headers, 
            timeout=30
        )
        
        if verbose:
            print(f"Response status: {response.status_code}")
            print(f"Response headers: {dict(response.headers)}")
            print(f"Response body: {response.text}")
        
        response.raise_for_status()
        return response.json()
        
    except requests.exceptions.RequestException as e:
        print(f"Failed to create workflow: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response status: {e.response.status_code}")
            print(f"Response body: {e.response.text}")
        sys.exit(1)


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Create Test Workflow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create a test workflow for tenant-a
  python scripts/create_test_workflow.py --user admin.a@edilens.com --password password --tenant tenant-a
        """
    )
    
    parser.add_argument(
        "--user",
        default="admin.a@edilens.com",
        help="Username for authentication (default: admin.a@edilens.com)"
    )
    
    parser.add_argument(
        "--password",
        default="password",
        help="Password for authentication (default: password)"
    )
    
    parser.add_argument(
        "--tenant",
        default="tenant-a",
        help="Tenant ID (default: tenant-a)"
    )
    
    parser.add_argument(
        "--template-id",
        default="global-batch-edi-processor-v1.0",
        help="Template ID to use (default: global-batch-edi-processor-v1.0)"
    )
    
    parser.add_argument(
        "--api-url",
        default="http://localhost:3001",
        help="API URL (default: http://localhost:3001)"
    )
    
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
        "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    
    args = parser.parse_args()
    
    # Get authentication token
    print(f"Authenticating user: {args.user}")
    token = get_user_token_from_keycloak(
        username=args.user,
        password=args.password,
        tenant_id=args.tenant,
        keycloak_url=args.keycloak_url,
        realm=args.realm,
        verbose=args.verbose
    )
    
    # Create workflow
    print(f"Creating workflow for tenant: {args.tenant}")
    workflow = create_workflow(
        token=token,
        tenant_id=args.tenant,
        api_url=args.api_url,
        template_id=args.template_id,
        verbose=args.verbose
    )
    
    print(f"Workflow created successfully!")
    print(f"Workflow ID: {workflow.get('workflow_id')}")
    print(f"Workflow name: {workflow.get('name')}")


if __name__ == "__main__":
    main()