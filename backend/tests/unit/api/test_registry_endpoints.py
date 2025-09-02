"""
Unit tests for Registry Template API endpoints.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.endpoints.registry_templates import router, create_workflow_response
from src.models.registry_models import RegistryTemplate, WorkflowInstance
from src.services.registry_service import RegistryService, RegistryServiceError
from src.core.auth import AuthContext, User, RealmAccess
from src.api.schemas import (
    RegistryTemplateCreateRequest, RegistryTemplateUpdateRequest,
    WorkflowInstanceCreateRequest, RegistryTemplateResponse, WorkflowInstanceResponse
)


pytestmark = pytest.mark.unit


class TestRegistryTemplateEndpoints:
    """Unit tests for registry template API endpoints."""

    @pytest.fixture
    def mock_session(self):
        """Create a mocked async session."""
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def admin_auth_context(self):
        """Create an admin auth context."""
        admin_user = User(
            sub="admin-user-123",
            preferred_username="admin-user",
            email="admin@example.com",
            groups=["tenant-admin"],
            realm_access=RealmAccess(roles=["admin", "user"])
        )
        return AuthContext(user=admin_user, tenant_id="tenant-admin")

    @pytest.fixture
    def user_auth_context(self):
        """Create a regular user auth context."""
        regular_user = User(
            sub="user-123",
            preferred_username="test-user",
            email="user@example.com",
            groups=["tenant-test"],
            realm_access=RealmAccess(roles=["user"])
        )
        return AuthContext(user=regular_user, tenant_id="tenant-test")

    @pytest.fixture
    def sample_template(self):
        """Create a sample registry template for testing."""
        return RegistryTemplate(
            template_id=uuid4(),
            bucket_id=uuid4(),
            name="Test Template",
            description="Test template for API testing",
            current_version=1,
            scope="TENANT",
            tenant_id="tenant-test",
            status="ACTIVE",
            is_featured=False,
            usage_count=0,
            created_by="user-123",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

    @pytest.fixture
    def sample_workflow_instance(self, sample_template):
        """Create a sample workflow instance for testing."""
        return WorkflowInstance(
            workflow_id=uuid4(),
            template_id=sample_template.template_id,
            template_version=1,
            name="Test Workflow Instance",
            description="Test workflow instance",
            tenant_id="tenant-test",
            configuration={"param1": "value1"},
            status="CREATED",
            created_by="user-123",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

    @pytest.fixture
    def create_template_request(self):
        """Create a template creation request."""
        return RegistryTemplateCreateRequest(
            name="New Test Template",
            description="New template for testing",
            flow_definition={
                "identifier": str(uuid4()),
                "name": "Test Flow",
                "description": "Test flow definition",
                "processors": [],
                "connections": [],
                "processGroups": [],
                "controllerServices": []
            }
        )

    @pytest.fixture
    def update_template_request(self):
        """Create a template update request."""
        return RegistryTemplateUpdateRequest(
            name="Updated Test Template",
            description="Updated template description",
            flow_definition={
                "identifier": str(uuid4()),
                "name": "Updated Test Flow",
                "description": "Updated test flow definition",
                "processors": [],
                "connections": [],
                "processGroups": [],
                "controllerServices": []
            }
        )

    @pytest.fixture
    def create_workflow_request(self):
        """Create a workflow instance creation request."""
        return WorkflowInstanceCreateRequest(
            name="New Test Workflow",
            description="New workflow for testing",
            configuration={"test_param": "test_value"}
        )

    @pytest.mark.asyncio
    async def test_create_template_success_admin(self, mock_session, admin_auth_context, create_template_request, sample_template):
        """Test successful template creation by admin user."""
        
        with patch('src.api.endpoints.registry_templates.RegistryService') as mock_service:
            mock_service_instance = AsyncMock()
            mock_service_instance.create_template.return_value = sample_template
            mock_service.return_value = mock_service_instance
            
            # Import and call endpoint function directly
            from src.api.endpoints.registry_templates import create_template
            
            result = await create_template(
                template_data=create_template_request,
                session=mock_session,
                auth_context=admin_auth_context
            )
            
            # Verify template creation
            mock_service_instance.create_template.assert_called_once_with(
                name=create_template_request.name,
                description=create_template_request.description,
                flow_definition=create_template_request.flow_definition,
                scope="GLOBAL",  # Admin creates global templates
                tenant_id=None,  # Global scope has no tenant_id
                created_by=admin_auth_context.user_id
            )
            
            # Verify response
            assert result.name == sample_template.name
            assert result.template_id == sample_template.template_id

    @pytest.mark.asyncio
    async def test_create_template_success_user(self, mock_session, user_auth_context, create_template_request, sample_template):
        """Test successful template creation by regular user."""
        
        # Adjust sample template for tenant scope
        sample_template.scope = "TENANT"
        sample_template.tenant_id = user_auth_context.tenant_id
        
        with patch('src.api.endpoints.registry_templates.RegistryService') as mock_service:
            mock_service_instance = AsyncMock()
            mock_service_instance.create_template.return_value = sample_template
            mock_service.return_value = mock_service_instance
            
            from src.api.endpoints.registry_templates import create_template
            
            result = await create_template(
                template_data=create_template_request,
                session=mock_session,
                auth_context=user_auth_context
            )
            
            # Verify template creation with tenant scope
            mock_service_instance.create_template.assert_called_once_with(
                name=create_template_request.name,
                description=create_template_request.description,
                flow_definition=create_template_request.flow_definition,
                scope="TENANT",  # User creates tenant templates
                tenant_id=user_auth_context.tenant_id,
                created_by=user_auth_context.user_id
            )

    @pytest.mark.asyncio
    async def test_create_template_registry_error(self, mock_session, user_auth_context, create_template_request):
        """Test template creation with registry service error."""
        
        with patch('src.api.endpoints.registry_templates.RegistryService') as mock_service:
            mock_service_instance = AsyncMock()
            mock_service_instance.create_template.side_effect = RegistryServiceError("Registry connection failed")
            mock_service.return_value = mock_service_instance
            
            from src.api.endpoints.registry_templates import create_template
            
            with pytest.raises(HTTPException) as exc_info:
                await create_template(
                    template_data=create_template_request,
                    session=mock_session,
                    auth_context=user_auth_context
                )
            
            assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert "Registry connection failed" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_create_template_user_no_tenant(self, mock_session, create_template_request):
        """Test template creation by user without tenant ID."""
        
        no_tenant_user = User(
            sub="user-no-tenant",
            preferred_username="user-no-tenant",
            email="user@example.com",
            groups=[],
            realm_access=RealmAccess(roles=["user"])
        )
        user_no_tenant = AuthContext(user=no_tenant_user, tenant_id=None)
        
        from src.api.endpoints.registry_templates import create_template
        
        with pytest.raises(HTTPException) as exc_info:
            await create_template(
                template_data=create_template_request,
                session=mock_session,
                auth_context=user_no_tenant
            )
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Tenant ID required" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_list_templates_admin(self, mock_session, admin_auth_context, sample_template):
        """Test template listing by admin user."""
        
        templates = [sample_template]
        
        with patch('src.api.endpoints.registry_templates.RegistryService') as mock_service:
            mock_service_instance = AsyncMock()
            mock_service_instance.list_templates.return_value = templates
            mock_service.return_value = mock_service_instance
            
            from src.api.endpoints.registry_templates import list_templates
            
            result = await list_templates(
                scope=None,
                session=mock_session,
                auth_context=admin_auth_context
            )
            
            # Admin should see all templates
            mock_service_instance.list_templates.assert_called_once_with(scope=None)
            assert len(result) == 1
            assert result[0].template_id == sample_template.template_id

    @pytest.mark.asyncio
    async def test_list_templates_user(self, mock_session, user_auth_context, sample_template):
        """Test template listing by regular user."""
        
        # Create global and tenant templates
        global_template = RegistryTemplate(
            template_id=uuid4(),
            bucket_id=uuid4(),
            name="Global Template",
            description="Global template",
            current_version=1,
            scope="GLOBAL",
            tenant_id=None,
            status="ACTIVE"
        )
        
        tenant_template = sample_template  # Tenant template
        
        with patch('src.api.endpoints.registry_templates.RegistryService') as mock_service:
            mock_service_instance = AsyncMock()
            mock_service_instance.list_templates.side_effect = [
                [global_template],  # Global templates call
                [tenant_template]   # Tenant templates call
            ]
            mock_service.return_value = mock_service_instance
            
            from src.api.endpoints.registry_templates import list_templates
            
            result = await list_templates(
                scope=None,
                session=mock_session,
                auth_context=user_auth_context
            )
            
            # User should see global + tenant templates
            assert mock_service_instance.list_templates.call_count == 2
            assert len(result) == 2
            template_ids = [t.template_id for t in result]
            assert global_template.template_id in template_ids
            assert tenant_template.template_id in template_ids

    @pytest.mark.asyncio
    async def test_get_template_success(self, mock_session, user_auth_context, sample_template):
        """Test successful template retrieval."""
        
        with patch('src.api.endpoints.registry_templates.RegistryService') as mock_service:
            mock_service_instance = AsyncMock()
            mock_service_instance.get_template.return_value = sample_template
            mock_service.return_value = mock_service_instance
            
            from src.api.endpoints.registry_templates import get_template
            
            result = await get_template(
                template_id=sample_template.template_id,
                session=mock_session,
                auth_context=user_auth_context
            )
            
            mock_service_instance.get_template.assert_called_once_with(sample_template.template_id)
            assert result.template_id == sample_template.template_id

    @pytest.mark.asyncio
    async def test_get_template_flow_definition_success(self, mock_session, user_auth_context, sample_template):
        """Test successful template flow definition retrieval."""
        
        flow_definition = {
            "identifier": "test-flow",
            "name": "Test Flow",
            "processors": []
        }
        
        with patch('src.api.endpoints.registry_templates.RegistryService') as mock_service:
            mock_service_instance = AsyncMock()
            mock_service_instance.get_template.return_value = sample_template
            mock_service_instance.get_template_flow_definition.return_value = flow_definition
            mock_service.return_value = mock_service_instance
            
            from src.api.endpoints.registry_templates import get_template_flow_definition
            
            result = await get_template_flow_definition(
                template_id=sample_template.template_id,
                version=1,
                session=mock_session,
                auth_context=user_auth_context
            )
            
            mock_service_instance.get_template_flow_definition.assert_called_once_with(
                sample_template.template_id, sample_template.bucket_id, 1
            )
            assert result.flow_definition == flow_definition

    @pytest.mark.asyncio
    async def test_create_workflow_instance_success(self, mock_session, user_auth_context, sample_template, sample_workflow_instance, create_workflow_request):
        """Test successful workflow instance creation."""
        
        with patch('src.api.endpoints.registry_templates.RegistryService') as mock_service:
            mock_service_instance = AsyncMock()
            mock_service_instance.create_workflow_instance.return_value = sample_workflow_instance
            mock_service.return_value = mock_service_instance
            
            from src.api.endpoints.registry_templates import create_workflow_instance
            
            result = await create_workflow_instance(
                template_id=sample_template.template_id,
                workflow_data=create_workflow_request,
                session=mock_session,
                auth_context=user_auth_context
            )
            
            mock_service_instance.create_workflow_instance.assert_called_once_with(
                template_id=sample_template.template_id,
                template_version=None,  # Uses latest version
                name=create_workflow_request.name,
                tenant_id=user_auth_context.tenant_id,
                configuration=create_workflow_request.configuration,
                description=create_workflow_request.description,
                created_by=user_auth_context.user_id
            )
            assert result.workflow_id == sample_workflow_instance.workflow_id

    def test_create_workflow_response_helper(self, sample_workflow_instance, sample_template):
        """Test create_workflow_response helper function."""
        
        # Mock the template relationship
        sample_workflow_instance.template = sample_template
        
        result = create_workflow_response(sample_workflow_instance, include_template=True)
        
        assert isinstance(result, WorkflowInstanceResponse)
        assert result.workflow_id == sample_workflow_instance.workflow_id
        assert result.template_id == sample_workflow_instance.template_id
        assert result.template is not None
        assert result.template.template_id == sample_template.template_id

    def test_create_workflow_response_no_template(self, sample_workflow_instance):
        """Test create_workflow_response helper without template."""
        
        result = create_workflow_response(sample_workflow_instance, include_template=False)
        
        assert isinstance(result, WorkflowInstanceResponse)
        assert result.workflow_id == sample_workflow_instance.workflow_id
        assert result.template is None

    def test_create_workflow_response_template_access_error(self, sample_workflow_instance, sample_template):
        """Test create_workflow_response helper with template access error."""
        
        # Mock template that raises error on access
        mock_template = MagicMock()
        mock_template.name = MagicMock(side_effect=Exception("Access error"))
        sample_workflow_instance.template = mock_template
        
        result = create_workflow_response(sample_workflow_instance, include_template=True)
        
        assert isinstance(result, WorkflowInstanceResponse)
        assert result.workflow_id == sample_workflow_instance.workflow_id
        assert result.template is None  # Should be None due to access error


class TestRegistryEndpointsErrorHandling:
    """Test error handling in registry endpoints."""

    @pytest.fixture
    def mock_session(self):
        """Create a mocked async session."""
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def user_auth_context(self):
        """Create a user auth context."""
        test_user = User(
            sub="user-123",
            preferred_username="test-user",
            email="user@example.com",
            groups=["tenant-test"],
            realm_access=RealmAccess(roles=["user"])
        )
        return AuthContext(user=test_user, tenant_id="tenant-test")

    @pytest.mark.asyncio
    async def test_create_template_unexpected_error(self, mock_session, user_auth_context):
        """Test template creation with unexpected error."""
        
        create_request = RegistryTemplateCreateRequest(
            name="Test Template",
            description="Test description",
            flow_definition={}
        )
        
        with patch('src.api.endpoints.registry_templates.RegistryService') as mock_service:
            mock_service_instance = AsyncMock()
            mock_service_instance.create_template.side_effect = Exception("Unexpected error")
            mock_service.return_value = mock_service_instance
            
            from src.api.endpoints.registry_templates import create_template
            
            with pytest.raises(HTTPException) as exc_info:
                await create_template(
                    template_data=create_request,
                    session=mock_session,
                    auth_context=user_auth_context
                )
            
            assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert "Failed to create template" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_list_templates_service_error(self, mock_session, user_auth_context):
        """Test template listing with service error."""
        
        with patch('src.api.endpoints.registry_templates.RegistryService') as mock_service:
            mock_service_instance = AsyncMock()
            mock_service_instance.list_templates.side_effect = Exception("Service error")
            mock_service.return_value = mock_service_instance
            
            from src.api.endpoints.registry_templates import list_templates
            
            with pytest.raises(HTTPException) as exc_info:
                await list_templates(
                    scope=None,
                    session=mock_session,
                    auth_context=user_auth_context
                )
            
            assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR