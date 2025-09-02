"""
Unit tests for NiFi workflow service.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import UUID, uuid4

from src.services.nifi_workflow_service import NiFiWorkflowService, NiFiWorkflowDeploymentError
from src.models.workflow_template import Workflow
from src.models.registry_models import RegistryTemplate


pytestmark = pytest.mark.unit


class TestNiFiWorkflowService:
    """Test NiFi Workflow Service."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        session = AsyncMock()
        # Mock the commit and refresh methods to be no-ops
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.add = MagicMock()
        return session

    @pytest.fixture
    def sample_workflow(self):
        """Create a sample workflow for testing."""
        # Use the same UUID as the template for consistency
        template_uuid = "12345678-1234-5678-9012-123456789012"
        return Workflow(
            workflow_id=uuid4(),
            tenant_id="tenant-123",
            name="Test Workflow",
            template_id=template_uuid,
            configuration={"test": "config"},
            status="ACTIVE"
        )

    @pytest.fixture
    def sample_template(self):
        """Create a sample template for testing."""
        # Use a fixed UUID for consistent testing
        template_uuid = UUID("12345678-1234-5678-9012-123456789012")
        return RegistryTemplate(
            template_id=template_uuid,
            bucket_id=uuid4(),
            name="Test Template",
            description="Test template for testing",
            current_version=1,
            scope="TENANT",
            tenant_id="tenant-123"
        )

    @pytest.mark.asyncio
    async def test_deploy_workflow_success(self, mock_session, sample_workflow, sample_template):
        """Test successful workflow deployment."""
        # Mock template retrieval
        execute_mock = MagicMock()
        execute_mock.scalar_one_or_none.return_value = sample_template
        mock_session.execute = AsyncMock(return_value=execute_mock)
        
        # Mock registry service
        mock_registry_service = AsyncMock()
        mock_registry_service.deploy_from_registry = AsyncMock(return_value={"component": {"id": "pg-456"}})
        
        # Mock NiFi client
        mock_nifi_client = AsyncMock()
        mock_nifi_client.get_process_group = AsyncMock(return_value={"component": {"id": "root-789"}})
        mock_nifi_client.create_parameter_context = AsyncMock(return_value={"component": {"id": "param-123"}})
        
        # Create proper async context manager mock for the client
        class AsyncContextManagerMock:
            def __init__(self, return_value):
                self.return_value = return_value
            
            async def __aenter__(self):
                return self.return_value
            
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass
        
        mock_nifi_context = AsyncContextManagerMock(mock_nifi_client)
        
        with patch('src.services.nifi_workflow_service.NiFiAPIClient') as mock_nifi, \
             patch.object(NiFiWorkflowService, '_create_parameter_context', new=AsyncMock(return_value={"component": {"id": "param-123"}})):
            
            mock_nifi.return_value = mock_nifi_context
            
            # Create service and inject mock registry service
            service = NiFiWorkflowService(mock_session)
            service.registry_service = mock_registry_service
            
            result = await service.deploy_workflow(sample_workflow)
            
            # Verify results
            assert result.nifi_process_group_id == "pg-456"
            assert result.nifi_parameter_context_id == "param-123"
            assert result.status == "ACTIVE"

    @pytest.mark.asyncio
    async def test_deploy_workflow_template_not_found(self, mock_session, sample_workflow):
        """Test workflow deployment with missing template."""
        # Mock template retrieval to return None
        execute_mock = MagicMock()
        execute_mock.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=execute_mock)
        
        # Create service and attempt deployment
        service = NiFiWorkflowService(mock_session)
        
        with pytest.raises(NiFiWorkflowDeploymentError, match="Failed to deploy workflow: Template 12345678-1234-5678-9012-123456789012 not found"):
            await service.deploy_workflow(sample_workflow)

    @pytest.mark.asyncio
    async def test_deploy_workflow_nifi_error(self, mock_session, sample_workflow, sample_template):
        """Test workflow deployment with NiFi error."""
        # Mock template retrieval
        execute_mock = AsyncMock()
        execute_mock.scalar_one_or_none = AsyncMock(return_value=sample_template)
        mock_session.execute = AsyncMock(return_value=execute_mock)
        
        # Mock NiFi registry client to raise an exception
        mock_registry_client = AsyncMock()
        mock_registry_client.list_buckets = AsyncMock(side_effect=Exception("Connection failed"))
        
        with patch('src.services.nifi_workflow_service.NiFiRegistryClient') as mock_registry:
            mock_registry.return_value.__aenter__.return_value = mock_registry_client
            
            # Create service and attempt deployment
            service = NiFiWorkflowService(mock_session)
            
            with pytest.raises(NiFiWorkflowDeploymentError):
                await service.deploy_workflow(sample_workflow)
            
            # Verify workflow status was set to ERROR
            assert sample_workflow.status == "ERROR"

    @pytest.mark.asyncio
    async def test_undeploy_workflow_success(self, mock_session, sample_workflow):
        """Test successful workflow undeployment."""
        # Set up deployed workflow
        sample_workflow.nifi_process_group_id = "pg-123"
        sample_workflow.nifi_parameter_context_id = "param-456"
        
        # Mock NiFi client
        mock_nifi_client = AsyncMock()
        mock_nifi_client.get_process_group = AsyncMock(return_value={
            "revision": {"version": 1},
            "component": {"state": "STOPPED"}
        })
        mock_nifi_client.stop_process_group = AsyncMock(return_value={})
        mock_nifi_client.delete_process_group = AsyncMock(return_value=True)
        
        with patch('src.services.nifi_workflow_service.NiFiAPIClient') as mock_nifi:
            mock_nifi.return_value.__aenter__.return_value = mock_nifi_client
            
            # Create service and undeploy workflow
            service = NiFiWorkflowService(mock_session)
            result = await service.undeploy_workflow(sample_workflow)
            
            # Verify results
            assert result.nifi_process_group_id is None
            assert result.nifi_parameter_context_id is None
            assert result.status == "DELETED"

    @pytest.mark.asyncio
    async def test_undeploy_workflow_not_deployed(self, mock_session, sample_workflow):
        """Test undeployment of workflow that isn't deployed."""
        # Create service and attempt undeployment
        service = NiFiWorkflowService(mock_session)
        
        with pytest.raises(NiFiWorkflowDeploymentError, match="Workflow is not deployed to NiFi"):
            await service.undeploy_workflow(sample_workflow)

    @pytest.mark.asyncio
    async def test_start_workflow_success(self, mock_session, sample_workflow):
        """Test successful workflow start."""
        # Set up deployed workflow
        sample_workflow.nifi_process_group_id = "pg-123"
        
        # Mock NiFi client
        mock_nifi_client = AsyncMock()
        mock_nifi_client.start_process_group = AsyncMock(return_value={})
        
        with patch('src.services.nifi_workflow_service.NiFiAPIClient') as mock_nifi:
            mock_nifi.return_value.__aenter__.return_value = mock_nifi_client
            
            # Create service and start workflow
            service = NiFiWorkflowService(mock_session)
            result = await service.start_workflow(sample_workflow)
            
            # Verify results
            assert result.status == "ACTIVE"

    @pytest.mark.asyncio
    async def test_stop_workflow_success(self, mock_session, sample_workflow):
        """Test successful workflow stop."""
        # Set up deployed workflow
        sample_workflow.nifi_process_group_id = "pg-123"
        
        # Mock NiFi client
        mock_nifi_client = AsyncMock()
        mock_nifi_client.stop_process_group = AsyncMock(return_value={})
        
        with patch('src.services.nifi_workflow_service.NiFiAPIClient') as mock_nifi:
            mock_nifi.return_value.__aenter__.return_value = mock_nifi_client
            
            # Create service and stop workflow
            service = NiFiWorkflowService(mock_session)
            result = await service.stop_workflow(sample_workflow)
            
            # Verify results
            assert result.status == "PAUSED"

    @pytest.mark.asyncio
    async def test_get_workflow_status_not_deployed(self, mock_session, sample_workflow):
        """Test status retrieval for non-deployed workflow."""
        # Create service and get status
        service = NiFiWorkflowService(mock_session)
        result = await service.get_workflow_status(sample_workflow)
        
        # Verify results
        assert result["status"] == "NOT_DEPLOYED"
        assert result["nifi_status"] is None

    @pytest.mark.asyncio
    async def test_get_workflow_status_deployed(self, mock_session, sample_workflow):
        """Test status retrieval for deployed workflow."""
        # Set up deployed workflow
        sample_workflow.nifi_process_group_id = "pg-123"
        sample_workflow.status = "ACTIVE"
        
        # Mock NiFi client
        mock_nifi_client = AsyncMock()
        mock_nifi_client.get_process_group = AsyncMock(return_value={
            "component": {"state": "RUNNING"}
        })
        mock_nifi_client.get_flow_status = AsyncMock(return_value={
            "controllerStatus": {"activeThreadCount": 5}
        })
        
        with patch('src.services.nifi_workflow_service.NiFiAPIClient') as mock_nifi:
            mock_nifi.return_value.__aenter__.return_value = mock_nifi_client
            
            # Create service and get status
            service = NiFiWorkflowService(mock_session)
            result = await service.get_workflow_status(sample_workflow)
            
            # Verify results
            assert result["status"] == "ACTIVE"
            assert result["nifi_status"] == "RUNNING"
            assert result["health_check"]["status"] == "healthy"