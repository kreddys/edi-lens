# backend/tests/e2e/test_workflow_templates_e2e.py

import pytest
from httpx import AsyncClient

from tests.e2e.e2e_utils import get_user_token


pytestmark = pytest.mark.e2e


@pytest.mark.asyncio
async def test_workflow_templates_list_with_authentication():
    """Test that workflow templates endpoint works with proper authentication."""
    
    # Get an auth token for a superuser
    auth_token = await get_user_token("superuser@edilens.com")
    
    # Test the workflow templates endpoint
    async with AsyncClient(base_url="http://backend:8000") as client:
        response = await client.get(
            "/api/v1/workflow-templates/",
            headers={
                "Authorization": f"Bearer {auth_token}",
                "X-Tenant-Id": "tenant-a"
            }
        )
    
    # Should get a successful response
    assert response.status_code == 200
    
    # Should get a proper response structure
    data = response.json()
    assert "templates" in data
    assert "total" in data
    assert "page" in data
    assert "page_size" in data
    assert isinstance(data["templates"], list)


@pytest.mark.asyncio 
async def test_workflow_templates_access_control():
    """Test that workflow templates enforce proper access control."""
    
    # Test without authentication - should fail
    async with AsyncClient(base_url="http://backend:8000") as client:
        response = await client.get("/api/v1/workflow-templates/")
    
    assert response.status_code == 403
    # The exact detail message may vary, just check that it's a 403
    
    
    # Test with authentication but wrong permissions
    viewer_token = await get_user_token("viewer.b@edilens.com")
    
    async with AsyncClient(base_url="http://backend:8000") as client:
        response = await client.get(
            "/api/v1/workflow-templates/",
            headers={
                "Authorization": f"Bearer {viewer_token}",
                "X-Tenant-Id": "tenant-b"
            }
        )
    
    # Should work for viewing - viewers should be able to read templates
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_workflow_template_create_requires_proper_permissions():
    """Test that creating workflow templates requires proper permissions."""
    
    # Get auth tokens for different user types
    admin_token = await get_user_token("admin.a@edilens.com")
    viewer_token = await get_user_token("viewer.b@edilens.com")
    
    # Test data for creating a template
    template_data = {
        "name": "Test EDI Processor",
        "description": "A test template for EDI processing",
        "category": "BATCH", 
        "scope": "TENANT",
        "version": "1.0",
        "flow_definition": {"processors": [], "connections": []},
        "configuration_schema": {"type": "object", "properties": {}},
        "deployment_method": "registry"
    }
    
    # Test with admin user - should work
    async with AsyncClient(base_url="http://backend:8000") as client:
        response = await client.post(
            "/api/v1/workflow-templates/",
            json=template_data,
            headers={
                "Authorization": f"Bearer {admin_token}",
                "X-Tenant-Id": "tenant-a"
            }
        )
    
    # Admin should be able to create tenant templates
    if response.status_code != 201:
        print(f"Error response: {response.status_code} - {response.text}")
        print(f"Request data: {template_data}")
    assert response.status_code == 201
    created_template = response.json()
    assert created_template["name"] == template_data["name"]
    assert created_template["scope"] == "TENANT"
    
    # Test with viewer - should fail
    async with AsyncClient(base_url="http://backend:8000") as client:
        response = await client.post(
            "/api/v1/workflow-templates/",
            json=template_data,
            headers={
                "Authorization": f"Bearer {viewer_token}",
                "X-Tenant-Id": "tenant-b"
            }
        )
    
    # Viewer should not be able to create templates (lacks edi:write permission)
    assert response.status_code == 403