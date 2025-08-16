"""
Tests for workflow execution API endpoints.

Tests the new workflow execution functionality including:
- POST /api/workflows/{workflow_id}/process
- GET /api/workflows/{workflow_id}/status  
- POST /api/workflows/{workflow_id}/pause
- POST /api/workflows/{workflow_id}/resume
- POST /api/workflows/{workflow_id}/restart
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4

from src.main import app
from src.core.auth import get_current_user, User, RealmAccess
from src.models.workflow_template import Workflow, WorkflowTemplate
from src.api.schemas import WorkflowStatus


@pytest.fixture
def admin_user():
    """User with admin and execution permissions."""
    return User(
        sub="admin-user",
        preferred_username="admin",
        groups=["tenant-a"],
        realm_access=RealmAccess(roles=["admin", "workflow:write", "workflow:read", "workflow:execute"])
    )


@pytest.fixture
def read_only_user():
    """User with only read permissions."""
    return User(
        sub="read-user", 
        preferred_username="reader",
        groups=["tenant-a"],
        realm_access=RealmAccess(roles=["workflow:read"])
    )


@pytest.fixture(autouse=True)
def cleanup_overrides():
    """Cleanup dependency overrides after each test."""
    yield
    if get_current_user in app.dependency_overrides:
        del app.dependency_overrides[get_current_user]


async def create_test_workflow(db_session: AsyncSession) -> Workflow:
    """Helper function to create a test workflow for execution testing."""
    
    # First create a test template
    template = WorkflowTemplate(
        template_id="test-execution-template-v1.0",
        name="Test Execution Template",
        description="Template for testing workflow execution",
        scope="TENANT",
        tenant_id="tenant-a",
        category="BATCH",
        version="1.0",
        flow_definition={"processors": [], "connections": []},
        configuration_schema={"type": "object", "properties": {}},
        deployment_method="registry",
        status="ACTIVE",
        maintainer="test-user",
        usage_count=0
    )
    db_session.add(template)
    
    # Create test workflow
    workflow = Workflow(
        workflow_id=uuid4(),
        tenant_id="tenant-a",
        name="Test Execution Workflow",
        description="Workflow for testing execution endpoints",
        template_id="test-execution-template-v1.0",
        configuration={"input_path": "/test/path"},
        status=WorkflowStatus.ACTIVE,
        created_by="test-user"
    )
    db_session.add(workflow)
    await db_session.flush()
    await db_session.refresh(workflow)
    
    return workflow


@pytest.mark.asyncio
@pytest.mark.integration
async def test_execute_workflow_success(
    async_client: AsyncClient,
    db_session: AsyncSession,
    admin_user: User
):
    """Test successful workflow execution."""
    test_workflow = await create_test_workflow(db_session)
    
    # Print debug information
    print(f"[TEST] Created workflow with ID: {test_workflow.workflow_id}")
    print(f"[TEST] Workflow tenant ID: {test_workflow.tenant_id}")
    print(f"[TEST] Workflow template ID: {test_workflow.template_id}")
    
    # Override authentication
    app.dependency_overrides[get_current_user] = lambda: admin_user
    
    # Test workflow execution
    execution_request = {
        "edi_content": "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *250816*1030*U*00401*000000001*0*P*>~",
        "request_id": "test-request-123",
        "processing_options": {
            "generate_ta1": True,
            "generate_999": False
        }
    }
    
    headers = {"X-Tenant-ID": "tenant-a"}
    
    print(f"[TEST] Making request to: /api/v1/workflows/{test_workflow.workflow_id}/process")
    
    response = await async_client.post(
        f"/api/v1/workflows/{test_workflow.workflow_id}/process",
        json=execution_request,
        headers=headers
    )
    
    print(f"[TEST] Response status: {response.status_code}")
    print(f"[TEST] Response body: {response.text}")
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify response structure
    assert "valid" in data
    assert "validation_results" in data
    assert "processing_time_ms" in data
    assert "workflow_id" in data
    assert "processed_at" in data
    
    # Verify workflow ID matches
    assert data["workflow_id"] == str(test_workflow.workflow_id)
    
    # Verify request ID is echoed back
    assert data["request_id"] == "test-request-123"
    
    # Should have TA1 acknowledgment since we requested it
    assert data["ta1_acknowledgment"] is not None


@pytest.mark.asyncio  
@pytest.mark.integration
async def test_execute_workflow_invalid_workflow_id(
    async_client: AsyncClient,
    admin_user: User
):
    """Test workflow execution with invalid workflow ID."""
    
    app.dependency_overrides[get_current_user] = lambda: admin_user
    
    invalid_workflow_id = str(uuid4())
    execution_request = {
        "edi_content": "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *250816*1030*U*00401*000000001*0*P*>~"
    }
    
    headers = {"X-Tenant-ID": "tenant-a"}
    
    response = await async_client.post(
        f"/api/workflows/{invalid_workflow_id}/process",
        json=execution_request,
        headers=headers
    )
    
    assert response.status_code == 404


@pytest.mark.asyncio
@pytest.mark.integration  
async def test_get_workflow_status(
    async_client: AsyncClient,
    db_session: AsyncSession,
    admin_user: User
):
    """Test workflow status endpoint."""
    test_workflow = await create_test_workflow(db_session)
    
    app.dependency_overrides[get_current_user] = lambda: admin_user
    
    headers = {"X-Tenant-ID": "tenant-a"}
    
    response = await async_client.get(
        f"/api/v1/workflows/{test_workflow.workflow_id}/status",
        headers=headers
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify response structure
    assert "workflow_id" in data
    assert "status" in data
    assert "nifi_status" in data
    assert "deployment_status" in data
    assert "execution_count" in data
    assert "success_rate" in data
    assert "health_check" in data
    
    # Verify workflow ID matches
    assert data["workflow_id"] == str(test_workflow.workflow_id)
    
    # Verify status matches workflow status
    assert data["status"] == test_workflow.status


@pytest.mark.asyncio
@pytest.mark.integration
async def test_pause_workflow(
    async_client: AsyncClient,
    db_session: AsyncSession,
    admin_user: User
):
    """Test workflow pause endpoint."""
    test_workflow = await create_test_workflow(db_session)
    
    app.dependency_overrides[get_current_user] = lambda: admin_user
    
    headers = {"X-Tenant-ID": "tenant-a"}
    
    response = await async_client.post(
        f"/api/v1/workflows/{test_workflow.workflow_id}/pause",
        headers=headers
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify workflow was paused
    assert data["status"] == "PAUSED"
    assert data["workflow_id"] == str(test_workflow.workflow_id)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_resume_workflow(
    async_client: AsyncClient,
    db_session: AsyncSession,
    admin_user: User
):
    """Test workflow resume endpoint."""
    test_workflow = await create_test_workflow(db_session)
    
    app.dependency_overrides[get_current_user] = lambda: admin_user
    
    # First pause the workflow
    test_workflow.status = WorkflowStatus.PAUSED
    db_session.add(test_workflow)
    await db_session.flush()
    
    headers = {"X-Tenant-ID": "tenant-a"}
    
    response = await async_client.post(
        f"/api/v1/workflows/{test_workflow.workflow_id}/resume",
        headers=headers
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify workflow was resumed
    assert data["status"] == "ACTIVE"
    assert data["workflow_id"] == str(test_workflow.workflow_id)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_restart_workflow(
    async_client: AsyncClient,
    db_session: AsyncSession,
    admin_user: User
):
    """Test workflow restart endpoint."""
    test_workflow = await create_test_workflow(db_session)
    
    app.dependency_overrides[get_current_user] = lambda: admin_user
    
    headers = {"X-Tenant-ID": "tenant-a"}
    
    response = await async_client.post(
        f"/api/v1/workflows/{test_workflow.workflow_id}/restart",
        headers=headers
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify workflow was restarted (should be ACTIVE)
    assert data["status"] == "ACTIVE"
    assert data["workflow_id"] == str(test_workflow.workflow_id)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_workflow_execution_permissions(
    async_client: AsyncClient,
    db_session: AsyncSession,
    read_only_user: User
):
    """Test workflow execution endpoint requires workflow:execute permission."""
    test_workflow = await create_test_workflow(db_session)
    
    # User without workflow:execute permission
    app.dependency_overrides[get_current_user] = lambda: read_only_user
    
    execution_request = {
        "edi_content": "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *250816*1030*U*00401*000000001*0*P*>~"
    }
    
    headers = {"X-Tenant-ID": "tenant-a"}
    
    response = await async_client.post(
        f"/api/v1/workflows/{test_workflow.workflow_id}/process",
        json=execution_request,
        headers=headers
    )
    
    assert response.status_code == 403


@pytest.mark.asyncio
@pytest.mark.integration  
async def test_workflow_execution_validation_errors(
    async_client: AsyncClient,
    db_session: AsyncSession,
    admin_user: User
):
    """Test workflow execution with invalid EDI content generates validation errors."""
    test_workflow = await create_test_workflow(db_session)
    
    app.dependency_overrides[get_current_user] = lambda: admin_user
    
    # Test with invalid EDI content (doesn't start with ISA)
    execution_request = {
        "edi_content": "INVALID EDI CONTENT",
        "request_id": "test-validation-error"
    }
    
    headers = {"X-Tenant-ID": "tenant-a"}
    
    response = await async_client.post(
        f"/api/v1/workflows/{test_workflow.workflow_id}/process",
        json=execution_request,
        headers=headers
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Should be marked as invalid due to validation errors
    assert data["valid"] == False
    assert len(data["validation_results"]) > 0
    
    # Should have validation error about ISA segment
    validation_errors = data["validation_results"]
    isa_error = next((e for e in validation_errors if "ISA" in e["message"]), None)
    assert isa_error is not None
    assert isa_error["level"] == "error"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_processing_time_measurement(
    async_client: AsyncClient,
    db_session: AsyncSession,
    admin_user: User
):
    """Test that processing time is measured and returned."""
    test_workflow = await create_test_workflow(db_session)
    
    app.dependency_overrides[get_current_user] = lambda: admin_user
    
    execution_request = {
        "edi_content": "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *250816*1030*U*00401*000000001*0*P*>~"
    }
    
    headers = {"X-Tenant-ID": "tenant-a"}
    
    response = await async_client.post(
        f"/api/v1/workflows/{test_workflow.workflow_id}/process",
        json=execution_request,
        headers=headers
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Processing time should be positive and reasonable
    processing_time = data["processing_time_ms"]
    assert isinstance(processing_time, int)
    assert processing_time > 0
    assert processing_time < 5000  # Should be less than 5 seconds for mock processing

@pytest.mark.asyncio
@pytest.mark.integration
async def test_workflow_control_state_validation(
    async_client: AsyncClient,
    db_session: AsyncSession,
    admin_user: User
):
    """Test that workflow control endpoints validate current state."""
    test_workflow = await create_test_workflow(db_session)
    
    app.dependency_overrides[get_current_user] = lambda: admin_user
    headers = {"X-Tenant-ID": "tenant-a"}
    
    # Cannot resume an active workflow
    response = await async_client.post(
        f"/api/v1/workflows/{test_workflow.workflow_id}/resume",
        headers=headers
    )
    assert response.status_code == 400
    
    # Pause the workflow
    await async_client.post(
        f"/api/v1/workflows/{test_workflow.workflow_id}/pause",
        headers=headers
    )
    
    # Cannot pause an already paused workflow
    response = await async_client.post(
        f"/api/v1/workflows/{test_workflow.workflow_id}/pause",
        headers=headers
    )
    
    # Resume the workflow
    await async_client.post(
        f"/api/v1/workflows/{test_workflow.workflow_id}/resume",
        headers=headers
    )
    
    # Set to ERROR state
    test_workflow.status = WorkflowStatus.ERROR
    db_session.add(test_workflow)
    await db_session.flush()
    
    # Can restart an errored workflow
    response = await async_client.post(
        f"/api/v1/workflows/{test_workflow.workflow_id}/restart",
        headers=headers
    )
    
    # Set to DELETED state
    test_workflow.status = WorkflowStatus.DELETED
    db_session.add(test_workflow)
    await db_session.flush()
    
    # Cannot restart a deleted workflow
    response = await async_client.post(
        f"/api/v1/workflows/{test_workflow.workflow_id}/restart",
        headers=headers
    )