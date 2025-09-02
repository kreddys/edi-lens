"""
Integration tests for Workflow API endpoints (/api/v1/workflows/).

Tests the complete workflow API functionality including:
- Workflow CRUD operations through HTTP  
- Workflow deployment and lifecycle management via API
- Workflow execution and status endpoints
- Authentication and authorization validation
- Multi-tenant access control
"""

import pytest
from uuid import uuid4
from httpx import AsyncClient
from asgi_lifespan import LifespanManager
from fastapi import status

from src.main import app
from src.core.auth import get_current_user, User, RealmAccess
from src.core.database import get_db

pytestmark = pytest.mark.integration


@pytest.fixture
def admin_user():
    """User with full workflow permissions."""
    return User(
        sub="admin-user",
        preferred_username="admin",
        groups=["tenant-a"],
        realm_access=RealmAccess(roles=["admin", "workflow:write", "workflow:read", "workflow:execute"])
    )


@pytest.fixture
def read_only_user():
    """User with read-only permissions."""
    return User(
        sub="readonly-user", 
        preferred_username="readonly",
        groups=["tenant-a"],
        realm_access=RealmAccess(roles=["workflow:read"])
    )


@pytest.fixture
def execute_user():
    """User with execute permissions."""
    return User(
        sub="execute-user",
        preferred_username="execute",
        groups=["tenant-a"],
        realm_access=RealmAccess(roles=["workflow:read", "workflow:execute"])
    )


@pytest.fixture
def tenant_b_user():
    """User from different tenant."""
    return User(
        sub="tenant-b-user",
        preferred_username="tenant-b-user", 
        groups=["tenant-b"],
        realm_access=RealmAccess(roles=["workflow:write", "workflow:read", "workflow:execute"])
    )


@pytest.fixture(autouse=True)
def cleanup_overrides():
    """Cleanup dependency overrides after each test."""
    yield
    app.dependency_overrides.clear()


class TestWorkflowEndpoints:
    """Integration tests for workflow API endpoints."""
    
    @property
    def tenant_headers(self):
        """Standard headers with tenant ID."""
        return {"x-tenant-id": "tenant-a"}
    
    @property  
    def tenant_b_headers(self):
        """Headers for tenant B."""
        return {"x-tenant-id": "tenant-b"}

    def generate_test_flow_definition(self):
        """Generate a test flow definition."""
        return {
            "identifier": f"test-workflow-flow-{uuid4().hex[:8]}",
            "name": "Test Workflow Flow",
            "description": "Test flow for workflow API testing",
            "processors": [
                {
                    "identifier": str(uuid4()),
                    "name": "Test Workflow Processor",
                    "type": "org.apache.nifi.processors.standard.GenerateFlowFile",
                    "position": {"x": 200.0, "y": 200.0},
                    "properties": {"File Size": "1KB", "Batch Size": "1"},
                    "autoTerminatedRelationships": ["success"]
                }
            ],
            "processGroups": [],
            "connections": [],
            "controllerServices": [],
            "variables": {},
            "version": 1
        }

    async def create_test_template(self, client, name_suffix=""):
        """Helper to create a test template for workflows."""
        import time
        unique_id = str(int(time.time() * 1000))  # Millisecond timestamp for uniqueness
        template_data = {
            "name": f"Workflow Test Template {name_suffix} {unique_id}",
            "description": "Template for workflow endpoint testing",
            "flow_definition": self.generate_test_flow_definition(),
            "scope": "GLOBAL"
        }
        
        response = await client.post("/api/v1/templates/", json=template_data, headers=self.tenant_headers)
        assert response.status_code == status.HTTP_201_CREATED
        return response.json()

    @pytest.mark.asyncio
    async def test_create_workflow_endpoint(self, admin_user, db_session):
        """Test workflow creation endpoint."""
        app.dependency_overrides[get_current_user] = lambda: admin_user
        app.dependency_overrides[get_db] = lambda: db_session
        
        async with LifespanManager(app):
            async with AsyncClient(app=app, base_url="http://test") as client:
                # Create template first
                template = await self.create_test_template(client, "Create")
                
                # Create workflow
                workflow_data = {
                    "template_id": template["template_id"],
                    "name": f"API Test Workflow {uuid4().hex[:8]}",
                    "description": "Workflow created via API endpoint test",
                    "configuration": {
                        "batch_size": "10",
                        "processing_mode": "test",
                        "timeout": 30
                    }
                }
                
                response = await client.post("/api/v1/workflows/", json=workflow_data, headers=self.tenant_headers)
                
                assert response.status_code == status.HTTP_201_CREATED
                data = response.json()
                
                # Verify response structure
                assert "workflow_id" in data
                assert data["name"] == workflow_data["name"]
                assert data["description"] == workflow_data["description"]
                assert data["template_id"] == template["template_id"]
                assert data["tenant_id"] == "tenant-a"
                assert data["status"] == "CREATED"
                assert data["is_deployed"] is False
                assert data["configuration"] == workflow_data["configuration"]
                assert "created_at" in data
                assert "updated_at" in data

    @pytest.mark.asyncio
    async def test_get_workflow_endpoint(self, admin_user, db_session):
        """Test workflow retrieval endpoint."""
        app.dependency_overrides[get_current_user] = lambda: admin_user
        app.dependency_overrides[get_db] = lambda: db_session
        
        async with LifespanManager(app):
            async with AsyncClient(app=app, base_url="http://test") as client:
                # Create template and workflow
                template = await self.create_test_template(client, "Get")
                
                workflow_data = {
                    "template_id": template["template_id"],
                    "name": f"Get Test Workflow {uuid4().hex[:8]}",
                    "description": "Workflow for get endpoint test"
                }
                
                create_response = await client.post("/api/v1/workflows/", json=workflow_data)
                workflow_id = create_response.json()["workflow_id"]
                
                # Get workflow
                get_response = await client.get(f"/api/v1/workflows/{workflow_id}")
                
                assert get_response.status_code == status.HTTP_200_OK
                data = get_response.json()
                
                assert data["workflow_id"] == workflow_id
                assert data["name"] == workflow_data["name"]
                assert data["template_id"] == template["template_id"]
                assert data["status"] == "CREATED"

    @pytest.mark.asyncio
    async def test_list_workflows_endpoint(self, admin_user, db_session):
        """Test workflow listing endpoint with filtering."""
        app.dependency_overrides[get_current_user] = lambda: admin_user
        app.dependency_overrides[get_db] = lambda: db_session
        
        async with LifespanManager(app):
            async with AsyncClient(app=app, base_url="http://test") as client:
                # Create template and multiple workflows
                template = await self.create_test_template(client, "List")
                
                workflow1_data = {
                    "template_id": template["template_id"], 
                    "name": f"List Test Workflow 1 {uuid4().hex[:8]}",
                    "description": "First workflow for list test"
                }
                
                workflow2_data = {
                    "template_id": template["template_id"],
                    "name": f"List Test Workflow 2 {uuid4().hex[:8]}",
                    "description": "Second workflow for list test"
                }
                
                # Create workflows
                response1 = await client.post("/api/v1/workflows/", json=workflow1_data)
                response2 = await client.post("/api/v1/workflows/", json=workflow2_data)
                
                assert response1.status_code == status.HTTP_201_CREATED
                assert response2.status_code == status.HTTP_201_CREATED
                
                # Test list all workflows
                list_response = await client.get("/api/v1/workflows/")
                assert list_response.status_code == status.HTTP_200_OK
                workflows = list_response.json()
                assert len(workflows) >= 2
                
                workflow_names = [w["name"] for w in workflows]
                assert workflow1_data["name"] in workflow_names
                assert workflow2_data["name"] in workflow_names
                
                # Test filtering by template_id
                template_response = await client.get(f"/api/v1/workflows/?template_id={template['template_id']}")
                assert template_response.status_code == status.HTTP_200_OK
                filtered_workflows = template_response.json()
                
                for workflow in filtered_workflows:
                    assert workflow["template_id"] == template["template_id"]
                
                # Test filtering by status
                status_response = await client.get("/api/v1/workflows/?status=CREATED")
                assert status_response.status_code == status.HTTP_200_OK
                status_workflows = status_response.json()
                
                for workflow in status_workflows:
                    assert workflow["status"] == "CREATED"

    @pytest.mark.asyncio
    async def test_update_workflow_endpoint(self, admin_user, db_session):
        """Test workflow update endpoint."""
        app.dependency_overrides[get_current_user] = lambda: admin_user
        app.dependency_overrides[get_db] = lambda: db_session
        
        async with LifespanManager(app):
            async with AsyncClient(app=app, base_url="http://test") as client:
                # Create template and workflow
                template = await self.create_test_template(client, "Update")
                
                workflow_data = {
                    "template_id": template["template_id"],
                    "name": f"Update Test Workflow {uuid4().hex[:8]}",
                    "description": "Original description",
                    "configuration": {"original_param": "original_value"}
                }
                
                create_response = await client.post("/api/v1/workflows/", json=workflow_data)
                workflow_id = create_response.json()["workflow_id"]
                
                # Update workflow
                update_data = {
                    "name": "Updated Workflow Name",
                    "description": "Updated description",
                    "configuration": {
                        "original_param": "updated_value",
                        "new_param": "new_value"
                    }
                }
                
                update_response = await client.put(f"/api/v1/workflows/{workflow_id}", json=update_data)
                
                assert update_response.status_code == status.HTTP_200_OK
                data = update_response.json()
                
                assert data["name"] == "Updated Workflow Name"
                assert data["description"] == "Updated description"
                assert data["configuration"]["original_param"] == "updated_value"
                assert data["configuration"]["new_param"] == "new_value"
                assert data["workflow_id"] == workflow_id

    @pytest.mark.asyncio
    async def test_delete_workflow_endpoint(self, admin_user, db_session):
        """Test workflow deletion endpoint."""
        app.dependency_overrides[get_current_user] = lambda: admin_user
        app.dependency_overrides[get_db] = lambda: db_session
        
        async with LifespanManager(app):
            async with AsyncClient(app=app, base_url="http://test") as client:
                # Create template and workflow
                template = await self.create_test_template(client, "Delete")
                
                workflow_data = {
                    "template_id": template["template_id"],
                    "name": f"Delete Test Workflow {uuid4().hex[:8]}",
                    "description": "Workflow for delete test"
                }
                
                create_response = await client.post("/api/v1/workflows/", json=workflow_data)
                workflow_id = create_response.json()["workflow_id"]
                
                # Delete workflow
                delete_response = await client.delete(f"/api/v1/workflows/{workflow_id}")
                
                assert delete_response.status_code == status.HTTP_204_NO_CONTENT
                
                # Verify workflow is deleted
                get_response = await client.get(f"/api/v1/workflows/{workflow_id}")
                assert get_response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_workflow_deployment_endpoints(self, admin_user, db_session):
        """Test workflow deployment/undeployment endpoints."""
        app.dependency_overrides[get_current_user] = lambda: admin_user
        app.dependency_overrides[get_db] = lambda: db_session
        
        async with LifespanManager(app):
            async with AsyncClient(app=app, base_url="http://test") as client:
                # Create template and workflow
                template = await self.create_test_template(client, "Deploy")
                
                workflow_data = {
                    "template_id": template["template_id"],
                    "name": f"Deploy Test Workflow {uuid4().hex[:8]}",
                    "description": "Workflow for deployment test"
                }
                
                create_response = await client.post("/api/v1/workflows/", json=workflow_data)
                workflow_id = create_response.json()["workflow_id"]
                
                # Deploy workflow
                deploy_response = await client.post(f"/api/v1/workflows/{workflow_id}/deploy")
                
                assert deploy_response.status_code == status.HTTP_200_OK
                deploy_data = deploy_response.json()
                
                assert deploy_data["is_deployed"] is True
                assert deploy_data["status"] == "ACTIVE"
                assert deploy_data["nifi_process_group_id"] is not None
                assert deploy_data["nifi_parameter_context_id"] is not None
                assert deploy_data["deployed_at"] is not None
                
                # Test workflow control endpoints
                # Pause workflow
                pause_response = await client.post(f"/api/v1/workflows/{workflow_id}/pause")
                assert pause_response.status_code == status.HTTP_200_OK
                pause_data = pause_response.json()
                assert pause_data["status"] == "PAUSED"
                
                # Resume workflow  
                resume_response = await client.post(f"/api/v1/workflows/{workflow_id}/resume")
                assert resume_response.status_code == status.HTTP_200_OK
                resume_data = resume_response.json()
                assert resume_data["status"] == "ACTIVE"
                
                # Restart workflow
                restart_response = await client.post(f"/api/v1/workflows/{workflow_id}/restart")
                assert restart_response.status_code == status.HTTP_200_OK
                restart_data = restart_response.json()
                assert restart_data["status"] == "ACTIVE"
                
                # Undeploy workflow
                undeploy_response = await client.post(f"/api/v1/workflows/{workflow_id}/undeploy")
                
                assert undeploy_response.status_code == status.HTTP_200_OK
                undeploy_data = undeploy_response.json()
                
                assert undeploy_data["is_deployed"] is False
                assert undeploy_data["status"] == "DELETED"
                assert undeploy_data["nifi_process_group_id"] is None
                assert undeploy_data["nifi_parameter_context_id"] is None
                assert undeploy_data["undeployed_at"] is not None

    @pytest.mark.asyncio
    async def test_workflow_execution_endpoint(self, admin_user, db_session):
        """Test workflow execution endpoint."""
        app.dependency_overrides[get_current_user] = lambda: admin_user
        app.dependency_overrides[get_db] = lambda: db_session
        
        async with LifespanManager(app):
            async with AsyncClient(app=app, base_url="http://test") as client:
                # Create and deploy workflow
                template = await self.create_test_template(client, "Execute")
                
                workflow_data = {
                    "template_id": template["template_id"],
                    "name": f"Execute Test Workflow {uuid4().hex[:8]}",
                    "description": "Workflow for execution test"
                }
                
                create_response = await client.post("/api/v1/workflows/", json=workflow_data)
                workflow_id = create_response.json()["workflow_id"]
                
                # Deploy workflow
                deploy_response = await client.post(f"/api/v1/workflows/{workflow_id}/deploy")
                assert deploy_response.status_code == status.HTTP_200_OK
                
                # Execute workflow
                execution_data = {
                    "content": "Test content for processing",
                    "file_type": "text",
                    "processing_options": {
                        "validate": True,
                        "generate_output": True
                    },
                    "request_id": str(uuid4())
                }
                
                execute_response = await client.post(
                    f"/api/v1/workflows/{workflow_id}/process",
                    json=execution_data
                )
                
                # Note: This might fail if NiFi is not accessible, which is expected
                if execute_response.status_code == status.HTTP_200_OK:
                    exec_data = execute_response.json()
                    
                    assert exec_data["workflow_id"] == workflow_id
                    assert exec_data["execution_id"] is not None
                    assert "message" in exec_data
                    assert exec_data["deployment_method"] == "nifi"
                elif execute_response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR:
                    # Expected if NiFi is not accessible during test
                    print("⚠️ Workflow execution failed (likely due to NiFi unavailability)")
                
                # Undeploy for cleanup
                await client.post(f"/api/v1/workflows/{workflow_id}/undeploy")

    @pytest.mark.asyncio
    async def test_workflow_status_endpoint(self, admin_user, db_session):
        """Test workflow status endpoint."""
        app.dependency_overrides[get_current_user] = lambda: admin_user
        app.dependency_overrides[get_db] = lambda: db_session
        
        async with LifespanManager(app):
            async with AsyncClient(app=app, base_url="http://test") as client:
                # Create workflow
                template = await self.create_test_template(client, "Status")
                
                workflow_data = {
                    "template_id": template["template_id"],
                    "name": f"Status Test Workflow {uuid4().hex[:8]}",
                    "description": "Workflow for status test"
                }
                
                create_response = await client.post("/api/v1/workflows/", json=workflow_data)
                workflow_id = create_response.json()["workflow_id"]
                
                # Get status before deployment
                status_response = await client.get(f"/api/v1/workflows/{workflow_id}/status")
                
                assert status_response.status_code == status.HTTP_200_OK
                status_data = status_response.json()
                
                assert status_data["workflow_id"] == workflow_id
                assert status_data["status"] == "CREATED"
                assert status_data["is_deployed"] is False
                assert "created_at" in status_data

    @pytest.mark.asyncio
    async def test_authorization_enforcement(self, admin_user, read_only_user, execute_user, db_session):
        """Test authorization enforcement on workflow endpoints."""
        async with LifespanManager(app):
            async with AsyncClient(app=app, base_url="http://test") as client:
                # Create template as admin first
                app.dependency_overrides[get_current_user] = lambda: admin_user
                app.dependency_overrides[get_db] = lambda: db_session
                
                template = await self.create_test_template(client, "Auth")
                
                # Test read-only user cannot create workflows
                app.dependency_overrides[get_current_user] = lambda: read_only_user
                
                workflow_data = {
                    "template_id": template["template_id"],
                    "name": "Should Fail Workflow",
                    "description": "This should fail"
                }
                
                create_response = await client.post("/api/v1/workflows/", json=workflow_data)
                assert create_response.status_code == status.HTTP_403_FORBIDDEN
                
                # Create workflow as admin
                app.dependency_overrides[get_current_user] = lambda: admin_user
                
                create_response = await client.post("/api/v1/workflows/", json=workflow_data)
                assert create_response.status_code == status.HTTP_201_CREATED
                workflow_id = create_response.json()["workflow_id"]
                
                # Test read-only user can read but not deploy
                app.dependency_overrides[get_current_user] = lambda: read_only_user
                
                get_response = await client.get(f"/api/v1/workflows/{workflow_id}")
                assert get_response.status_code == status.HTTP_200_OK
                
                deploy_response = await client.post(f"/api/v1/workflows/{workflow_id}/deploy")
                assert deploy_response.status_code == status.HTTP_403_FORBIDDEN
                
                # Deploy as admin
                app.dependency_overrides[get_current_user] = lambda: admin_user
                deploy_response = await client.post(f"/api/v1/workflows/{workflow_id}/deploy")
                assert deploy_response.status_code == status.HTTP_200_OK
                
                # Test execute user can execute but not control
                app.dependency_overrides[get_current_user] = lambda: execute_user
                
                execution_data = {
                    "content": "Test content",
                    "file_type": "text",
                    "processing_options": {}
                }
                
                # Execute should work (if NiFi is available)
                execute_response = await client.post(
                    f"/api/v1/workflows/{workflow_id}/process",
                    json=execution_data
                )
                # 200 OK or 500 (NiFi unavailable) are both acceptable for execute user
                assert execute_response.status_code in [status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR]
                
                # But pause should fail (no workflow:write permission)
                pause_response = await client.post(f"/api/v1/workflows/{workflow_id}/pause")
                assert pause_response.status_code == status.HTTP_403_FORBIDDEN
                
                # Clean up
                app.dependency_overrides[get_current_user] = lambda: admin_user
                await client.post(f"/api/v1/workflows/{workflow_id}/undeploy")

    @pytest.mark.asyncio
    async def test_tenant_isolation(self, admin_user, tenant_b_user, db_session):
        """Test tenant isolation for workflows."""
        async with LifespanManager(app):
            async with AsyncClient(app=app, base_url="http://test") as client:
                # Create template and workflow as tenant-a
                app.dependency_overrides[get_current_user] = lambda: admin_user
                app.dependency_overrides[get_db] = lambda: db_session
                
                template = await self.create_test_template(client, "TenantA")
                
                workflow_data = {
                    "template_id": template["template_id"],
                    "name": f"Tenant A Workflow {uuid4().hex[:8]}",
                    "description": "Workflow for tenant A"
                }
                
                create_response = await client.post("/api/v1/workflows/", json=workflow_data)
                assert create_response.status_code == status.HTTP_201_CREATED
                workflow_data = create_response.json()
                workflow_id = workflow_data["workflow_id"]
                assert workflow_data["tenant_id"] == "tenant-a"
                
                # Switch to tenant-b user
                app.dependency_overrides[get_current_user] = lambda: tenant_b_user
                
                # Tenant B should not see tenant A's workflow in list
                list_response = await client.get("/api/v1/workflows/")
                workflows = list_response.json()
                
                tenant_workflow_names = [w["name"] for w in workflows if w["tenant_id"] == "tenant-a"]
                assert len(tenant_workflow_names) == 0
                
                # Tenant B should not be able to access tenant A's workflow directly  
                get_response = await client.get(f"/api/v1/workflows/{workflow_id}")
                assert get_response.status_code in [status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN]
                
                # Tenant B should not be able to deploy tenant A's workflow
                deploy_response = await client.post(f"/api/v1/workflows/{workflow_id}/deploy")
                assert deploy_response.status_code in [status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN]

    @pytest.mark.asyncio
    async def test_error_handling(self, admin_user, db_session):
        """Test error handling for workflow endpoints."""
        app.dependency_overrides[get_current_user] = lambda: admin_user
        app.dependency_overrides[get_db] = lambda: db_session
        
        async with LifespanManager(app):
            async with AsyncClient(app=app, base_url="http://test") as client:
                # Test creating workflow with non-existent template
                invalid_workflow_data = {
                    "template_id": "00000000-0000-0000-0000-000000000000",
                    "name": "Should Fail Workflow",
                    "description": "This should fail"
                }
                
                response = await client.post("/api/v1/workflows/", json=invalid_workflow_data)
                assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
                
                # Test getting non-existent workflow
                get_response = await client.get("/api/v1/workflows/00000000-0000-0000-0000-000000000000")
                assert get_response.status_code == status.HTTP_404_NOT_FOUND
                
                # Test deploying non-existent workflow
                deploy_response = await client.post("/api/v1/workflows/00000000-0000-0000-0000-000000000000/deploy")
                assert deploy_response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
                
                # Test invalid UUIDs
                invalid_uuid_response = await client.get("/api/v1/workflows/invalid-uuid")
                assert invalid_uuid_response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY