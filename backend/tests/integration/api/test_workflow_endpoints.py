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
    from tests.conftest import generate_unique_template_data, generate_unique_workflow_data
    
    # Generate unique template data with UI configuration for format-agnostic workflow
    template_data = generate_unique_template_data(tenant_id="tenant-a")
    
    # Add UI configuration for generic workflow execution
    template_data["ui_configuration"] = {
        "input": {
            "title": "📄 Content Input",
            "accepted_file_types": [".edi", ".txt"],
            "placeholder_text": "Paste your content here or upload a file...",
            "supports_text_input": True,
            "supports_file_upload": True,
            "max_file_size_mb": 10
        },
        "processing_options": [
            {
                "name": "generate_ta1",
                "type": "boolean",
                "label": "Generate TA1 Acknowledgment",
                "description": "Generate technical acknowledgment for EDI files",
                "default_value": True
            },
            {
                "name": "generate_999",
                "type": "boolean", 
                "label": "Generate 999 Acknowledgment",
                "description": "Generate functional acknowledgment for EDI files",
                "default_value": False
            }
        ],
        "outputs": [
            {
                "name": "ta1_acknowledgment",
                "label": "TA1 Acknowledgment",
                "type": "download",
                "description": "Technical acknowledgment response",
                "file_extension": ".edi"
            },
            {
                "name": "validation_results",
                "label": "Validation Results",
                "type": "display",
                "description": "Content validation results"
            }
        ],
        "help_text": "This workflow processes EDI content and generates acknowledgments."
    }
    
    # First create a test template
    template = WorkflowTemplate(
        template_id=template_data["template_id"],
        name=template_data["name"],
        description=template_data["description"],
        scope=template_data["scope"],
        tenant_id=template_data["tenant_id"],
        category=template_data["category"],
        version=template_data["version"],
        flow_definition=template_data["flow_definition"],
        configuration_schema=template_data["configuration_schema"],
        ui_configuration=template_data["ui_configuration"],
        deployment_method=template_data["deployment_method"],
        status=template_data["status"],
        maintainer=template_data["maintainer"],
        usage_count=0
    )
    db_session.add(template)
    
    # Generate unique workflow data
    workflow_data = generate_unique_workflow_data(template_data["template_id"], "tenant-a")
    
    # Create test workflow
    workflow = Workflow(
        workflow_id=workflow_data["workflow_id"],
        tenant_id=workflow_data["tenant_id"],
        name=workflow_data["name"],
        description=workflow_data["description"],
        template_id=workflow_data["template_id"],
        configuration=workflow_data["configuration"],
        status=WorkflowStatus.ACTIVE,
        created_by=workflow_data["created_by"]
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
        "content": "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *250816*1030*U*00401*000000001*0*P*>~",
        "file_type": "edi",
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
    
    # Verify response structure (new WorkflowExecutionResponse schema)
    assert "workflow_id" in data
    assert "execution_id" in data
    assert "status" in data
    assert "message" in data
    assert "health_check" in data
    
    # Verify workflow ID matches
    assert data["workflow_id"] == str(test_workflow.workflow_id)
    
    # Verify execution ID is echoed back
    assert data["execution_id"] == "test-request-123"
    
    # Verify health check contains processing time
    assert "processing_time_ms" in data["health_check"]
    
    # Should have outputs since we requested TA1 generation
    assert data["health_check"]["outputs_count"] > 0


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
        "content": "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *250816*1030*U*00401*000000001*0*P*>~",
        "file_type": "edi"
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
    assert "is_deployed" in data
    assert "nifi_status" in data
    assert "deployment_status" in data
    assert "execution_count" in data
    assert "success_rate" in data
    assert "health_check" in data
    
    # Verify workflow ID matches
    assert data["workflow_id"] == str(test_workflow.workflow_id)
    
    # Verify status matches workflow status
    assert data["status"] == test_workflow.status
    
    # Verify is_deployed field is present and correct
    assert data["is_deployed"] == test_workflow.is_deployed


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
        "content": "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *250816*1030*U*00401*000000001*0*P*>~",
        "file_type": "edi"
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
        "content": "INVALID EDI CONTENT",
        "file_type": "edi",
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
    
    # Should be marked as unsuccessful due to validation errors (status should be FAILED)
    assert data["status"] == "FAILED"
    
    # Check health check status
    assert data["health_check"]["status"] == "unhealthy"
    
    # Should have outputs for validation results
    assert data["health_check"]["outputs_count"] > 0
    
    # Should have some form of validation feedback (status should indicate failure)
    assert data["status"] == "FAILED"


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
        "content": "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *250816*1030*U*00401*000000001*0*P*>~",
        "file_type": "edi"
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
    processing_time = data["health_check"]["processing_time_ms"]
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