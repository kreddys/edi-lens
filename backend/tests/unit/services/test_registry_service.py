"""
Unit tests for RegistryService.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.registry_service import RegistryService
from src.models.registry_models import RegistryTemplate, WorkflowInstance, RegistryBucket


pytestmark = pytest.mark.unit


class TestRegistryService:
    """Unit tests for RegistryService functionality."""

    @pytest.fixture
    def mock_session(self):
        """Create a mocked async session."""
        session = AsyncMock(spec=AsyncSession)
        session.execute = AsyncMock()
        session.add = MagicMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.rollback = AsyncMock()
        return session

    @pytest.fixture
    def registry_service(self, mock_session):
        """Create RegistryService instance with mocked session."""
        return RegistryService(mock_session)

    @pytest.fixture
    def sample_flow_definition(self):
        """Create a sample flow definition for testing."""
        return {
            "identifier": "test-flow",
            "name": "Test Flow",
            "description": "Test flow definition",
            "processGroups": [],
            "processors": [
                {
                    "identifier": str(uuid4()),
                    "name": "Test Processor",
                    "type": "org.apache.nifi.processors.standard.LogMessage",
                    "position": {"x": 100, "y": 100},
                    "properties": {"Log Level": "INFO", "Log Message": "Test message"}
                }
            ],
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
        }

    @pytest.mark.asyncio
    async def test_create_template_success(self, registry_service, mock_session, sample_flow_definition):
        """Test successful template creation."""
        
        # Mock bucket creation/retrieval
        mock_bucket = RegistryBucket(
            bucket_id=uuid4(),
            name="test-bucket",
            scope="TENANT",
            tenant_id="tenant-test"
        )
        
        with patch.object(registry_service, '_ensure_bucket_exists', return_value=mock_bucket) as mock_bucket_method, \
             patch.object(registry_service, '_create_flow_in_registry', return_value=uuid4()) as mock_flow_method:
            
            template = await registry_service.create_template(
                name="Test Template",
                description="Test template description",
                flow_definition=sample_flow_definition,
                scope="TENANT",
                tenant_id="tenant-test"
            )
            
            # Verify template properties
            assert template.name == "Test Template"
            assert template.description == "Test template description"
            assert template.scope == "TENANT"
            assert template.tenant_id == "tenant-test"
            assert template.current_version == 1
            assert template.bucket_id == mock_bucket.bucket_id
            
            # Verify methods were called correctly
            mock_bucket_method.assert_called_once_with("TENANT", "tenant-test")
            mock_flow_method.assert_called_once()
            
            # Verify database operations
            mock_session.add.assert_called_once_with(template)
            mock_session.commit.assert_called_once()
            mock_session.refresh.assert_called_once_with(template)

    @pytest.mark.asyncio
    async def test_create_template_global_scope(self, registry_service, mock_session, sample_flow_definition):
        """Test creating a global scope template."""
        
        # Mock bucket creation/retrieval for global scope
        mock_bucket = RegistryBucket(
            bucket_id=uuid4(),
            name="edi-lens-global",
            scope="GLOBAL",
            tenant_id=None
        )
        
        with patch.object(registry_service, '_ensure_bucket_exists', return_value=mock_bucket), \
             patch.object(registry_service, '_create_flow_in_registry', return_value=uuid4()):
            
            template = await registry_service.create_template(
                name="Global Template",
                description="Global template description",
                flow_definition=sample_flow_definition,
                scope="GLOBAL"
            )
            
            # Verify global template properties
            assert template.scope == "GLOBAL"
            assert template.tenant_id is None
            assert template.bucket_id == mock_bucket.bucket_id

    @pytest.mark.asyncio
    async def test_create_template_registry_error_handling(self, registry_service, mock_session, sample_flow_definition):
        """Test error handling when Registry operations fail."""
        
        mock_bucket = RegistryBucket(
            bucket_id=uuid4(),
            name="test-bucket",
            scope="TENANT",
            tenant_id="tenant-test"
        )
        
        with patch.object(registry_service, '_ensure_bucket_exists', return_value=mock_bucket), \
             patch.object(registry_service, '_create_flow_in_registry', side_effect=Exception("Registry error")):
            
            with pytest.raises(Exception, match="Registry error"):
                await registry_service.create_template(
                    name="Test Template",
                    description="Test template description",
                    flow_definition=sample_flow_definition,
                    scope="TENANT",
                    tenant_id="tenant-test"
                )
            
            # Verify rollback was called
            mock_session.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_template_success(self, registry_service, mock_session, sample_flow_definition):
        """Test successful template update (creates new version)."""
        
        # Mock existing template
        existing_template = RegistryTemplate(
            template_id=uuid4(),
            bucket_id=uuid4(),
            name="Existing Template",
            description="Existing description",
            current_version=1,
            scope="TENANT",
            tenant_id="tenant-test"
        )
        
        # Mock template retrieval
        execute_mock = MagicMock()
        execute_mock.scalar_one.return_value = existing_template
        mock_session.execute = AsyncMock(return_value=execute_mock)
        
        with patch.object(registry_service, '_create_flow_version_in_registry', return_value=2) as mock_version_method:
            
            updated_template = await registry_service.update_template(
                template_id=existing_template.template_id,
                name="Updated Template",
                description="Updated description",
                flow_definition=sample_flow_definition
            )
            
            # Verify template was updated
            assert updated_template.name == "Updated Template"
            assert updated_template.description == "Updated description"
            assert updated_template.current_version == 2
            
            # Verify Registry version creation was called
            mock_version_method.assert_called_once()
            
            # Verify database operations
            mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_template_not_found(self, registry_service, mock_session):
        """Test updating non-existent template raises error."""
        
        # Mock template not found
        execute_mock = MagicMock()
        execute_mock.scalar_one.side_effect = Exception("Template not found")
        mock_session.execute = AsyncMock(return_value=execute_mock)
        
        with pytest.raises(Exception, match="Template not found"):
            await registry_service.update_template(
                template_id=uuid4(),
                name="Updated Template",
                description="Updated description",
                flow_definition={}
            )

    @pytest.mark.asyncio
    async def test_create_workflow_instance_success(self, registry_service, mock_session):
        """Test successful workflow instance creation."""
        
        template_id = uuid4()
        
        instance = await registry_service.create_workflow_instance(
            template_id=template_id,
            template_version=1,
            name="Test Workflow Instance",
            tenant_id="tenant-test",
            configuration={"test_param": "test_value"}
        )
        
        # Verify instance properties
        assert instance.template_id == template_id
        assert instance.template_version == 1
        assert instance.name == "Test Workflow Instance"
        assert instance.tenant_id == "tenant-test"
        assert instance.configuration["test_param"] == "test_value"
        assert instance.status == "CREATED"
        
        # Verify database operations
        mock_session.add.assert_called_once_with(instance)
        mock_session.commit.assert_called_once()
        mock_session.refresh.assert_called_once_with(instance)

    @pytest.mark.asyncio
    async def test_deploy_workflow_instance_success(self, registry_service, mock_session):
        """Test successful workflow instance deployment."""
        
        # Mock existing workflow instance
        instance = WorkflowInstance(
            workflow_id=uuid4(),
            template_id=uuid4(),
            template_version=1,
            name="Test Instance",
            tenant_id="tenant-test",
            configuration={},
            status="CREATED"
        )
        
        # Mock instance retrieval
        execute_mock = MagicMock()
        execute_mock.scalar_one.return_value = instance
        mock_session.execute = AsyncMock(return_value=execute_mock)
        
        # Mock deployment methods
        with patch.object(registry_service, '_deploy_to_nifi', return_value={"component": {"id": "pg-123"}}) as mock_deploy, \
             patch.object(registry_service, '_create_parameter_context', return_value={"component": {"id": "pc-456"}}) as mock_param:
            
            deployed_instance = await registry_service.deploy_workflow_instance(instance.workflow_id)
            
            # Verify deployment
            assert deployed_instance.status == "DEPLOYED"
            assert deployed_instance.nifi_process_group_id == "pg-123"
            assert deployed_instance.nifi_parameter_context_id == "pc-456"
            
            # Verify deployment methods were called
            mock_deploy.assert_called_once()
            mock_param.assert_called_once()
            
            # Verify database operations
            mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_template_flow_definition_success(self, registry_service):
        """Test retrieving flow definition from Registry."""
        
        template_id = uuid4()
        bucket_id = uuid4()
        
        # Mock Registry client
        mock_flow_definition = {"test": "flow"}
        
        with patch('src.services.registry_service.NiFiRegistryClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get_flow_version = AsyncMock(return_value={
                "versionedFlowSnapshot": {
                    "flowContents": mock_flow_definition
                }
            })
            mock_client_class.return_value = mock_client
            
            flow_definition = await registry_service.get_template_flow_definition(
                template_id, bucket_id, 1
            )
            
            # Verify flow definition was retrieved
            assert flow_definition == mock_flow_definition
            mock_client.get_flow_version.assert_called_once_with(str(bucket_id), str(template_id), 1)

    @pytest.mark.asyncio
    async def test_ensure_bucket_exists_creates_new_bucket(self, registry_service):
        """Test bucket creation when it doesn't exist."""
        
        bucket_id = uuid4()
        
        with patch('src.services.registry_service.NiFiRegistryClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            
            # Mock bucket doesn't exist initially
            mock_client.list_buckets = AsyncMock(return_value=[])
            mock_client.create_bucket = AsyncMock(return_value={
                "identifier": str(bucket_id),
                "name": "edi-lens-tenant-tenant-test"
            })
            mock_client_class.return_value = mock_client
            
            bucket = await registry_service._ensure_bucket_exists("TENANT", "tenant-test")
            
            # Verify bucket was created
            assert bucket.bucket_id == bucket_id
            assert bucket.name == "edi-lens-tenant-tenant-test"
            assert bucket.scope == "TENANT"
            assert bucket.tenant_id == "tenant-test"
            
            mock_client.create_bucket.assert_called_once()

    @pytest.mark.asyncio
    async def test_ensure_bucket_exists_returns_existing(self, registry_service):
        """Test bucket retrieval when it already exists."""
        
        existing_bucket_id = uuid4()
        
        with patch('src.services.registry_service.NiFiRegistryClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            
            # Mock existing bucket
            mock_client.list_buckets = AsyncMock(return_value=[{
                "identifier": str(existing_bucket_id),
                "name": "edi-lens-global"
            }])
            mock_client_class.return_value = mock_client
            
            bucket = await registry_service._ensure_bucket_exists("GLOBAL", None)
            
            # Verify existing bucket was returned
            assert bucket.bucket_id == existing_bucket_id
            assert bucket.name == "edi-lens-global"
            assert bucket.scope == "GLOBAL"
            assert bucket.tenant_id is None
            
            # Should not have called create_bucket
            mock_client.create_bucket.assert_not_called()

    @pytest.mark.asyncio
    async def test_deploy_from_registry_success(self, registry_service):
        """Test deploying a process group from Registry."""
        
        # Mock NiFi client
        mock_nifi_client = AsyncMock()
        
        with patch.object(registry_service, '_attempt_direct_import', return_value={"component": {"id": "pg-123"}}) as mock_import:
            
            result = await registry_service.deploy_from_registry(
                nifi_client=mock_nifi_client,
                parent_group_id="root",
                bucket_id=str(uuid4()),
                flow_id=str(uuid4()),
                flow_version=1,
                process_group_name="Test Deployment",
                position={"x": 100, "y": 100}
            )
            
            # Verify successful deployment
            assert result["component"]["id"] == "pg-123"
            mock_import.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_flow_in_registry_success(self, registry_service, sample_flow_definition):
        """Test creating a flow in Registry."""
        
        bucket_id = uuid4()
        flow_id = uuid4()
        
        with patch('src.services.registry_service.NiFiRegistryClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            
            # Mock flow creation
            mock_client.create_flow = AsyncMock(return_value={
                "identifier": str(flow_id),
                "name": "Test Flow"
            })
            mock_client.create_flow_version = AsyncMock(return_value={
                "version": 1
            })
            
            mock_client_class.return_value = mock_client
            
            created_flow_id = await registry_service._create_flow_in_registry(
                bucket_id, "Test Flow", "Test description", sample_flow_definition
            )
            
            # Verify flow was created
            assert created_flow_id == flow_id
            mock_client.create_flow.assert_called_once()
            mock_client.create_flow_version.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_flow_version_in_registry_success(self, registry_service, sample_flow_definition):
        """Test creating a new flow version in Registry."""
        
        bucket_id = uuid4()
        flow_id = uuid4()
        
        with patch('src.services.registry_service.NiFiRegistryClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            
            # Mock version creation
            mock_client.create_flow_version = AsyncMock(return_value={
                "version": 2
            })
            
            mock_client_class.return_value = mock_client
            
            version = await registry_service._create_flow_version_in_registry(
                bucket_id, flow_id, sample_flow_definition, "Updated version"
            )
            
            # Verify version was created
            assert version == 2
            mock_client.create_flow_version.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_flow_definition_success(self, registry_service, sample_flow_definition):
        """Test flow definition validation."""
        
        # Should not raise an exception for valid flow definition
        registry_service._validate_flow_definition(sample_flow_definition)

    @pytest.mark.asyncio
    async def test_validate_flow_definition_missing_required_fields(self, registry_service):
        """Test flow definition validation with missing fields."""
        
        invalid_flow = {"processors": []}  # Missing required fields
        
        with pytest.raises(ValueError, match="Flow definition missing required field"):
            registry_service._validate_flow_definition(invalid_flow)

    @pytest.mark.asyncio
    async def test_generate_bucket_name_global(self, registry_service):
        """Test bucket name generation for global scope."""
        
        bucket_name = registry_service._generate_bucket_name("GLOBAL", None)
        assert bucket_name == "edi-lens-global"

    @pytest.mark.asyncio
    async def test_generate_bucket_name_tenant(self, registry_service):
        """Test bucket name generation for tenant scope."""
        
        bucket_name = registry_service._generate_bucket_name("TENANT", "tenant-test")
        assert bucket_name == "edi-lens-tenant-tenant-test"

    @pytest.mark.asyncio
    async def test_generate_bucket_name_invalid_scope(self, registry_service):
        """Test bucket name generation with invalid scope."""
        
        with pytest.raises(ValueError, match="Invalid scope"):
            registry_service._generate_bucket_name("INVALID", None)