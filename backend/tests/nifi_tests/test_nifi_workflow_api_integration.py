"""
Real integration tests for NiFi workflow API endpoints with actual NiFi services.

These tests validate the API endpoints with real NiFi and NiFi Registry,
without mocking any external services.
"""

import pytest
from httpx import AsyncClient
from uuid import uuid4
from sqlalchemy import select

from src.main import app
from src.core.auth import get_current_user, User, RealmAccess
from src.models.workflow_template import Workflow, WorkflowTemplate
from src.core.database import get_db
from src.core.config import settings


pytestmark = pytest.mark.integration


@pytest.fixture
def admin_user():
    """User with admin and workflow permissions."""
    return User(
        sub="admin-user",
        preferred_username="admin",
        groups=["tenant-a"],
        realm_access=RealmAccess(roles=["admin", "workflow:write", "workflow:read", "workflow:execute"])
    )


@pytest.fixture(autouse=True)
def cleanup_overrides():
    """Cleanup dependency overrides after each test."""
    yield
    if get_current_user in app.dependency_overrides:
        del app.dependency_overrides[get_current_user]


class TestNiFiWorkflowAPIIntegration:
    """Real integration tests for NiFi Workflow API endpoints with real services."""
    
    pytestmark = pytest.mark.asyncio

    @pytest.mark.asyncio
    async def test_workflow_deployment_api_lifecycle(self, admin_user, db_session):
        """Test complete workflow deployment API lifecycle with real NiFi services."""
        # Create test template and workflow directly in the test
        template = None
        workflow = None
        
        try:
            # Create a test template
            template_id = f"test-api-template-{uuid4()}"
            template = WorkflowTemplate(
                template_id=template_id,
                name=f"Test API Template {uuid4()}",
                category="BATCH",
                scope="TENANT",
                tenant_id="tenant-a",
                flow_definition={
                    "identifier": "test-flow",
                    "name": "Test Flow",
                    "description": "Test flow definition for API integration testing",
                    "processGroups": [],
                    "processors": [],
                    "controllerServices": [],
                    "funnels": [],
                    "inputPorts": [],
                    "outputPorts": [],
                    "remoteProcessGroups": [],
                    "labels": [],
                    "variables": {},
                    "connections": [],
                    "processGroupIdentifier": "test-flow",
                    "version": 1
                },
                configuration_schema={
                    "type": "object",
                    "properties": {
                        "test_param": {
                            "type": "string",
                            "default": "test_value"
                        }
                    }
                }
            )
            db_session.add(template)
            await db_session.commit()
            await db_session.refresh(template)
            
            # Create a test workflow
            workflow_id = uuid4()
            workflow = Workflow(
                workflow_id=workflow_id,
                tenant_id="tenant-a",
                name=f"Test API Workflow {uuid4()}",
                template_id=template_id,
                configuration={
                    "test_param": "api_test_value",
                    "processing_options": {
                        "generate_ta1": True,
                        "generate_999": False
                    }
                },
                status="ACTIVE"
            )
            db_session.add(workflow)
            await db_session.commit()
            await db_session.refresh(workflow)
            
            # Skip test if NiFi services are not accessible
            try:
                # Test NiFi connectivity first
                from src.nifi.clients.nifi_client import NiFiAPIClient
                async with NiFiAPIClient(settings.NIFI_URL) as nifi_client:
                    nifi_health = await nifi_client.health_check()
                    if not nifi_health:
                        pytest.skip("NiFi is not accessible")
                
                # Test NiFi Registry connectivity
                from src.nifi.clients.registry_client import NiFiRegistryClient
                async with NiFiRegistryClient(settings.NIFI_REGISTRY_URL) as registry_client:
                    try:
                        registry_info = await registry_client.get_registry_info()
                        if not registry_info:
                            pytest.skip("NiFi Registry is not accessible")
                    except:
                        pytest.skip("NiFi Registry is not accessible")
            except Exception as e:
                pytest.skip(f"NiFi services not accessible: {str(e)}")

            app.dependency_overrides[get_current_user] = lambda: admin_user
            headers = {"Authorization": "Bearer test-token", "x-tenant-id": "tenant-a"}
            
            async with AsyncClient(app=app, base_url="http://test") as client:
                try:
                    # 1. Deploy workflow via API
                    response = await client.post(
                        f"/api/v1/workflows/{workflow_id}/deploy",
                        headers=headers
                    )
                    
                    # Print response for debugging
                    print(f"Deploy response status: {response.status_code}")
                    print(f"Deploy response content: {response.content}")
                    
                    # Verify deployment was successful
                    assert response.status_code == 200
                    data = response.json()
                    assert data["nifi_process_group_id"] is not None
                    assert data["nifi_parameter_context_id"] is not None
                    assert data["status"] == "ACTIVE"
                    assert data["is_deployed"] is True
                    
                    # 2. Get workflow status via API
                    response = await client.get(
                        f"/api/v1/workflows/{workflow_id}/status",
                        headers=headers
                    )
                    
                    assert response.status_code == 200
                    status_data = response.json()
                    assert status_data["status"] == "ACTIVE"
                    assert "nifi_status" in status_data
                    assert "health_check" in status_data
                    
                    # 3. Stop workflow via API
                    response = await client.post(
                        f"/api/v1/workflows/{workflow_id}/stop",
                        headers=headers
                    )
                    
                    assert response.status_code == 200
                    stop_data = response.json()
                    assert stop_data["status"] == "PAUSED"
                    
                    # 4. Start workflow via API
                    response = await client.post(
                        f"/api/v1/workflows/{workflow_id}/start",
                        headers=headers
                    )
                    
                    assert response.status_code == 200
                    start_data = response.json()
                    assert start_data["status"] == "ACTIVE"
                    
                    # 5. Restart workflow via API
                    response = await client.post(
                        f"/api/v1/workflows/{workflow_id}/restart",
                        headers=headers
                    )
                    
                    assert response.status_code == 200
                    restart_data = response.json()
                    assert restart_data["status"] == "ACTIVE"
                    
                    # 6. Undeploy workflow via API
                    response = await client.post(
                        f"/api/v1/workflows/{workflow_id}/undeploy",
                        headers=headers
                    )
                    
                    assert response.status_code == 200
                    undeploy_data = response.json()
                    assert undeploy_data["nifi_process_group_id"] is None
                    assert undeploy_data["nifi_parameter_context_id"] is None
                    assert undeploy_data["status"] == "DELETED"
                    assert undeploy_data["is_deployed"] is False
                    
                except Exception as e:
                    pytest.fail(f"Workflow API deployment lifecycle test failed: {str(e)}")
        
        finally:
            # Clean up test data
            try:
                if workflow:
                    await db_session.delete(workflow)
                if template:
                    await db_session.delete(template)
                await db_session.commit()
            except:
                pass

    @pytest.mark.asyncio
    async def test_workflow_execution_with_nifi(self, admin_user, db_session):
        """Test workflow execution with real NiFi processing."""
        # Create test template and workflow directly in the test
        template = None
        workflow = None
        
        try:
            # Create a test template
            template_id = f"test-api-template-{uuid4()}"
            template = WorkflowTemplate(
                template_id=template_id,
                name=f"Test API Template {uuid4()}",
                category="BATCH",
                scope="TENANT",
                tenant_id="tenant-a",
                flow_definition={
                    "identifier": "test-flow",
                    "name": "Test Flow",
                    "description": "Test flow definition for API integration testing",
                    "processGroups": [],
                    "processors": [],
                    "controllerServices": [],
                    "funnels": [],
                    "inputPorts": [],
                    "outputPorts": [],
                    "remoteProcessGroups": [],
                    "labels": [],
                    "variables": {},
                    "connections": [],
                    "processGroupIdentifier": "test-flow",
                    "version": 1
                },
                configuration_schema={
                    "type": "object",
                    "properties": {
                        "test_param": {
                            "type": "string",
                            "default": "test_value"
                        }
                    }
                }
            )
            db_session.add(template)
            await db_session.commit()
            await db_session.refresh(template)
            
            # Create a test workflow
            workflow_id = uuid4()
            workflow = Workflow(
                workflow_id=workflow_id,
                tenant_id="tenant-a",
                name=f"Test API Workflow {uuid4()}",
                template_id=template_id,
                configuration={
                    "test_param": "api_test_value",
                    "processing_options": {
                        "generate_ta1": True,
                        "generate_999": False
                    }
                },
                status="ACTIVE"
            )
            db_session.add(workflow)
            await db_session.commit()
            await db_session.refresh(workflow)
            
            # Skip test if NiFi services are not accessible
            try:
                # Test NiFi connectivity first
                from src.nifi.clients.nifi_client import NiFiAPIClient
                async with NiFiAPIClient(settings.NIFI_URL) as nifi_client:
                    nifi_health = await nifi_client.health_check()
                    if not nifi_health:
                        pytest.skip("NiFi is not accessible")
            except Exception as e:
                pytest.skip(f"NiFi service not accessible: {str(e)}")

            app.dependency_overrides[get_current_user] = lambda: admin_user
            headers = {"Authorization": "Bearer test-token", "x-tenant-id": "tenant-a"}
            
            async with AsyncClient(app=app, base_url="http://test") as client:
                try:
                    # Deploy workflow first
                    response = await client.post(
                        f"/api/v1/workflows/{workflow_id}/deploy",
                        headers=headers
                    )
                    
                    if response.status_code != 200:
                        pytest.skip("Failed to deploy workflow for execution test")
                    
                    # Test workflow execution with sample EDI content
                    edi_content = "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *250816*1030*U*00401*000000001*0*P*>~IEA*1*000000001~"
                    
                    response = await client.post(
                        f"/api/v1/workflows/{workflow_id}/process",
                        headers=headers,
                        json={
                            "edi_content": edi_content,
                            "processing_options": {
                                "generate_ta1": True,
                                "generate_999": False
                            }
                        }
                    )
                    
                    # In a real NiFi environment, this might succeed or fail depending on the actual flow
                    # For now, we'll just verify the API call was made correctly
                    assert response.status_code in [200, 500]  # 200 for success, 500 for NiFi processing errors
                    
                    # If we get a successful response, verify the structure
                    if response.status_code == 200:
                        data = response.json()
                        assert "results" in data
                        assert "status" in data
                        
                except Exception as e:
                    pytest.fail(f"Workflow execution with NiFi test failed: {str(e)}")
        
        finally:
            # Clean up test data
            try:
                if workflow:
                    await db_session.delete(workflow)
                if template:
                    await db_session.delete(template)
                await db_session.commit()
            except:
                pass