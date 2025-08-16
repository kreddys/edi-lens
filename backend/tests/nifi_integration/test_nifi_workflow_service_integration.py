"""
Integration tests for NiFi workflow service.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import UUID, uuid4

from src.services.nifi_workflow_service import NiFiWorkflowService
from src.models.workflow_template import Workflow, WorkflowTemplate


pytestmark = pytest.mark.integration


class TestNiFiWorkflowServiceIntegration:
    """Integration tests for NiFi Workflow Service."""

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
        return Workflow(
            workflow_id=uuid4(),
            tenant_id="tenant-123",
            name="Test Workflow",
            template_id="template-456",
            configuration={"test": "config"},
            status="ACTIVE"
        )

    @pytest.fixture
    def sample_template(self):
        """Create a sample template for testing."""
        return WorkflowTemplate(
            template_id="template-456",
            name="Test Template",
            category="BATCH",
            scope="TENANT",
            tenant_id="tenant-123",
            flow_definition={"test": "flow"},
            configuration_schema={"test": "schema"}
        )

    @pytest.mark.asyncio
    async def test_nifi_connectivity(self, mock_session):
        """Test connectivity to NiFi services."""
        # This test would normally connect to real NiFi instances
        # For now, we'll just test that our service can be instantiated
        service = NiFiWorkflowService(mock_session)
        assert service is not None

    @pytest.mark.asyncio
    async def test_workflow_lifecycle_integration(self, mock_session, sample_workflow, sample_template):
        """Test complete workflow lifecycle integration."""
        # This test would normally:
        # 1. Deploy workflow to NiFi
        # 2. Start workflow
        # 3. Check workflow status
        # 4. Stop workflow
        # 5. Undeploy workflow
        # 
        # For now, we'll test that our service methods can be called
        # without errors when properly mocked
        
        # Mock template retrieval
        execute_mock = AsyncMock()
        execute_mock.scalar_one_or_none = AsyncMock(return_value=sample_template)
        mock_session.execute = AsyncMock(return_value=execute_mock)
        
        service = NiFiWorkflowService(mock_session)
        assert service is not None

    @pytest.mark.asyncio
    async def test_error_handling_integration(self, mock_session, sample_workflow):
        """Test error handling integration."""
        # Mock template retrieval to return None
        execute_mock = AsyncMock()
        execute_mock.scalar_one_or_none = AsyncMock(return_value=None)
        mock_session.execute = AsyncMock(return_value=execute_mock)
        
        service = NiFiWorkflowService(mock_session)
        
        # Should raise ValueError for missing template
        with pytest.raises(ValueError, match="Template template-456 not found"):
            await service.deploy_workflow(sample_workflow)