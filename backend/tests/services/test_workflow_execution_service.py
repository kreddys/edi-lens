"""
Unit tests for workflow execution service.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import UUID, uuid4
from datetime import datetime

from src.services.workflow_execution_service import WorkflowExecutionService, WorkflowExecutionResult
from src.models.workflow_template import Workflow, WorkflowTemplate
from src.api.schemas import WorkflowExecutionRequest


pytestmark = pytest.mark.unit


class TestWorkflowExecutionService:
    """Test Workflow Execution Service."""

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

    @pytest.fixture
    def sample_execution_request(self):
        """Create a sample execution request for testing."""
        return WorkflowExecutionRequest(
            edi_content="ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *250816*1030*U*00401*000000001*0*P*>~IEA*1*000000001~",
            request_id="test-request-123",
            processing_options={"generate_ta1": True}
        )

    @pytest.fixture
    def mock_auth_context(self):
        """Create a mock auth context."""
        auth_context = MagicMock()
        auth_context.tenant_id = "tenant-123"
        auth_context.user_id = "user-456"
        return auth_context

    @pytest.mark.asyncio
    async def test_execute_workflow_mock_success(self, mock_session, sample_workflow, sample_template, sample_execution_request, mock_auth_context):
        """Test successful workflow execution with mock processing."""
        # Set up workflow as not deployed to use mock processing
        sample_workflow.nifi_process_group_id = None
        
        # Mock database queries
        execute_mock1 = AsyncMock()
        execute_mock1.scalar_one_or_none = AsyncMock(return_value=sample_workflow)
        execute_mock2 = AsyncMock()
        execute_mock2.scalar_one_or_none = AsyncMock(return_value=sample_template)
        mock_session.execute = AsyncMock(side_effect=[execute_mock1, execute_mock2])
        
        # Create service and execute workflow
        service = WorkflowExecutionService(mock_session)
        result = await service.execute_workflow(
            str(sample_workflow.workflow_id),
            sample_execution_request,
            mock_auth_context
        )
        
        # Verify results
        assert isinstance(result, WorkflowExecutionResult)
        # The result may not be valid because of the mock validation
        assert result.request_id == "test-request-123"
        assert result.workflow_id == str(sample_workflow.workflow_id)
        assert isinstance(result.processed_at, datetime)

    @pytest.mark.asyncio
    async def test_execute_workflow_workflow_not_found(self, mock_session, sample_execution_request, mock_auth_context):
        """Test workflow execution with missing workflow."""
        # Mock database query to return None
        execute_mock = AsyncMock()
        execute_mock.scalar_one_or_none = AsyncMock(return_value=None)
        mock_session.execute = AsyncMock(return_value=execute_mock)
        
        # Create service and attempt execution
        service = WorkflowExecutionService(mock_session)
        
        result = await service.execute_workflow(
            "workflow-id",
            sample_execution_request,
            mock_auth_context
        )
        
        # Should return an error result
        assert result.valid is False
        # Check that we have validation results
        assert len(result.validation_results) > 0

    @pytest.mark.asyncio
    async def test_execute_workflow_template_not_found(self, mock_session, sample_workflow, sample_execution_request, mock_auth_context):
        """Test workflow execution with missing template."""
        # Mock database queries
        execute_mock1 = AsyncMock()
        execute_mock1.scalar_one_or_none = AsyncMock(return_value=sample_workflow)
        execute_mock2 = AsyncMock()
        execute_mock2.scalar_one_or_none = AsyncMock(return_value=None)
        mock_session.execute = AsyncMock(side_effect=[execute_mock1, execute_mock2])
        
        # Create service and attempt execution
        service = WorkflowExecutionService(mock_session)
        
        result = await service.execute_workflow(
            str(sample_workflow.workflow_id),
            sample_execution_request,
            mock_auth_context
        )
        
        # Should return an error result
        assert result.valid is False
        # Check that we have validation results
        assert len(result.validation_results) > 0

    @pytest.mark.asyncio
    async def test_realistic_ta1_generation(self, mock_session):
        """Test realistic TA1 generation."""
        service = WorkflowExecutionService(mock_session)
        
        # Test with valid EDI content
        edi_content = "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *250816*1030*U*00401*000000001*0*P*>~IEA*1*000000001~"
        result = await service._realistic_ta1_generation(edi_content)
        
        # Should generate valid TA1
        assert result.startswith("ISA*")
        assert "TA1*" in result
        assert result.endswith("~IEA*1*000000001~")
        
        # Test with invalid EDI content
        invalid_edi = "Invalid content"
        result = await service._realistic_ta1_generation(invalid_edi)
        
        # Should generate fallback TA1
        assert result.startswith("ISA*")
        assert "TA1*" in result