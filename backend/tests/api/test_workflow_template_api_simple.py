"""
Simple integration test for workflow template API to verify functionality works.
"""

import pytest
from httpx import AsyncClient

from src.main import app
from src.core.auth import get_current_user, User, RealmAccess


@pytest.fixture
def admin_user():
    """User with admin permissions."""
    return User(
        sub="admin-user",
        preferred_username="admin",
        groups=["tenant-a"],
        realm_access=RealmAccess(roles=["admin", "workflow:write", "workflow:read"])
    )


@pytest.fixture(autouse=True)
def cleanup_overrides():
    """Cleanup dependency overrides after each test."""
    yield
    # Clean up any dependency overrides
    if get_current_user in app.dependency_overrides:
        del app.dependency_overrides[get_current_user]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_create_workflow_template_simple(async_client: AsyncClient, admin_user):
    """Test creating workflow template via API works with relationships."""
    
    # Override authentication dependency
    app.dependency_overrides[get_current_user] = lambda: admin_user
    
    headers = {
        "X-Tenant-ID": "tenant-a",
        "Content-Type": "application/json"
    }
    
    # Template creation data
    template_data = {
        "name": "Simple API Test Template",
        "description": "Test template created via API",
        "category": "BATCH",
        "scope": "GLOBAL",
        "version": "1.0.0",
        "flow_definition": {
            "processors": [
                {"id": "processor1", "type": "ListSFTP", "properties": {"host": "example.com"}}
            ],
            "connections": []
        },
        "configuration_schema": {
            "type": "object",
            "properties": {
                "sftp_host": {"type": "string", "description": "SFTP server hostname"}
            },
            "required": ["sftp_host"]
        },
        "deployment_method": "registry",
        "tags": ["api-test", "batch-processing"],
        "features": ["sftp", "validation"],
        "documentation": "API test template for workflow processing",
        "is_featured": False
    }
    
    # Create template via API
    response = await async_client.post(
        "/api/v1/workflow-templates/",
        headers=headers,
        json=template_data
    )
    
    assert response.status_code == 201
    created_template = response.json()
    
    # Verify template structure
    assert created_template["name"] == template_data["name"]
    assert created_template["category"] == template_data["category"]
    assert created_template["scope"] == template_data["scope"]
    assert created_template["version"] == template_data["version"]
    assert "template_id" in created_template
    
    template_id = created_template["template_id"]
    
    # Test getting the template
    get_response = await async_client.get(
        f"/api/v1/workflow-templates/{template_id}",
        headers=headers
    )
    
    assert get_response.status_code == 200
    retrieved_template = get_response.json()
    assert retrieved_template["template_id"] == template_id
    assert retrieved_template["name"] == template_data["name"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_workflow_template_permissions_simple(async_client: AsyncClient, admin_user):
    """Test workflow template permission enforcement."""
    
    limited_user = User(
        sub="limited-user",
        preferred_username="limited",
        groups=["tenant-a"],
        realm_access=RealmAccess(roles=["workflow:read"])
    )
    
    # Template data
    template_data = {
        "name": "Permission Test Template",
        "description": "Test template for permissions",
        "category": "BATCH",
        "scope": "TENANT",
        "version": "1.0.0",
        "flow_definition": {"test": "permissions"},
        "configuration_schema": {"type": "object"},
        "deployment_method": "registry"
    }
    
    headers = {"X-Tenant-ID": "tenant-a", "Content-Type": "application/json"}
    
    # Admin should be able to create template
    app.dependency_overrides[get_current_user] = lambda: admin_user
    
    create_response = await async_client.post(
        "/api/v1/workflow-templates/",
        headers=headers,
        json=template_data
    )
    
    assert create_response.status_code == 201
    template = create_response.json()
    template_id = template["template_id"]
    
    # Limited user should be able to read template
    app.dependency_overrides[get_current_user] = lambda: limited_user
    
    read_response = await async_client.get(
        f"/api/v1/workflow-templates/{template_id}",
        headers=headers
    )
    
    assert read_response.status_code == 200
    
    # Limited user should NOT be able to create template
    create_denied_response = await async_client.post(
        "/api/v1/workflow-templates/",
        headers=headers,
        json=template_data
    )
    
    assert create_denied_response.status_code == 403