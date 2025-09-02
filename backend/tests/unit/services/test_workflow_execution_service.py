"""
Unit tests for WorkflowExecutionService.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.workflow_execution_service import WorkflowExecutionService, WorkflowExecutionResult, WorkflowStatusService
from src.models.workflow_template import Workflow
from src.models.registry_models import RegistryTemplate
from src.core.auth import AuthContext, User, RealmAccess
from src.api.schemas import WorkflowExecutionRequest, ValidationFinding, FindingLocation


pytestmark = pytest.mark.unit


class TestWorkflowExecutionService:
    """Unit tests for WorkflowExecutionService functionality."""

    @pytest.fixture
    def mock_session(self):
        """Create a mocked async session."""
        session = AsyncMock(spec=AsyncSession)
        session.execute = AsyncMock()
        return session

    @pytest.fixture
    def execution_service(self, mock_session):
        """Create WorkflowExecutionService instance with mocked session."""
        return WorkflowExecutionService(mock_session)

    @pytest.fixture
    def auth_context(self):
        """Create a test auth context."""
        test_user = User(
            sub="test-user-123",
            preferred_username="test-user",
            email="test@example.com",
            groups=["tenant-test"],
            realm_access=RealmAccess(roles=["user"])
        )
        return AuthContext(user=test_user, tenant_id="tenant-test")

    @pytest.fixture
    def sample_workflow(self):
        """Create a sample workflow for testing."""
        return Workflow(
            workflow_id=uuid4(),
            template_id=uuid4(),
            name="Test Workflow",
            tenant_id="tenant-test",
            status="ACTIVE",
            is_deployed=False,
            configuration={"test_param": "test_value"}
        )

    @pytest.fixture
    def sample_template(self):
        """Create a sample registry template for testing."""
        return RegistryTemplate(
            template_id=uuid4(),
            bucket_id=uuid4(),
            name="Test Template",
            description="Test template for testing",
            current_version=1,
            scope="TENANT",
            tenant_id="tenant-test",
            status="ACTIVE",
            ui_configuration={
                "outputs": [
                    {
                        "name": "validation_report",
                        "type": "display",
                        "label": "Validation Report"
                    },
                    {
                        "name": "processed_file",
                        "type": "download",
                        "label": "Processed File",
                        "file_extension": ".csv",
                        "mime_type": "text/csv"
                    }
                ]
            }
        )

    @pytest.fixture
    def execution_request(self):
        """Create a sample execution request."""
        return WorkflowExecutionRequest(
            content="Test EDI content",
            file_type="edi",
            processing_options={"validate": True},
            request_id="test-request-123"
        )

    @pytest.mark.asyncio
    async def test_execute_workflow_success_mock_processing(self, execution_service, mock_session, auth_context, sample_workflow, sample_template, execution_request):
        """Test successful workflow execution with mock processing."""
        
        # Mock workflow and template retrieval
        workflow_result = MagicMock()
        workflow_result.scalar_one_or_none.return_value = sample_workflow
        
        template_result = MagicMock()
        template_result.scalar_one_or_none.return_value = sample_template
        
        mock_session.execute.side_effect = [workflow_result, template_result]
        
        # Mock the output generation
        with patch.object(execution_service, '_generate_realistic_outputs', return_value=[
            {
                "name": "validation_report",
                "type": "display",
                "content": "Validation passed",
                "metadata": {"has_errors": False}
            }
        ]) as mock_outputs:
            
            result = await execution_service.execute_workflow(
                str(sample_workflow.workflow_id),
                execution_request,
                auth_context
            )
            
            # Verify result
            assert isinstance(result, WorkflowExecutionResult)
            assert result.valid is True
            assert result.workflow_id == str(sample_workflow.workflow_id)
            assert result.request_id == "test-request-123"
            assert result.processing_time_ms > 0
            assert len(result.outputs) == 1
            assert result.outputs[0]["name"] == "validation_report"
            
            # Verify outputs were generated correctly
            mock_outputs.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_workflow_success_nifi_processing(self, execution_service, mock_session, auth_context, sample_workflow, sample_template, execution_request):
        """Test successful workflow execution with NiFi processing."""
        
        # Set workflow as deployed
        sample_workflow.is_deployed = True
        sample_workflow.nifi_process_group_id = "pg-123"
        
        # Mock workflow and template retrieval
        workflow_result = MagicMock()
        workflow_result.scalar_one_or_none.return_value = sample_workflow
        
        template_result = MagicMock()
        template_result.scalar_one_or_none.return_value = sample_template
        
        mock_session.execute.side_effect = [workflow_result, template_result]
        
        # Mock NiFi workflow service for validation
        with patch('src.services.workflow_execution_service.NiFiWorkflowService') as mock_nifi_service:
            mock_service_instance = AsyncMock()
            mock_service_instance.get_workflow_status.return_value = {"nifi_status": "RUNNING"}
            mock_nifi_service.return_value = mock_service_instance
            
            # Mock the NiFi processing
            with patch.object(execution_service, '_process_content_nifi', return_value={
                "valid": True,
                "outputs": [{"name": "processed_file", "type": "download", "content": "processed", "metadata": {"has_errors": False}}],
                "metadata": {"processing_method": "nifi"}
            }) as mock_nifi_process:
                
                result = await execution_service.execute_workflow(
                    str(sample_workflow.workflow_id),
                    execution_request,
                    auth_context
                )
                
                # Verify result
                assert result.valid is True
                assert result.metadata["processing_method"] == "nifi"
                mock_nifi_process.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_workflow_not_found(self, execution_service, mock_session, auth_context, execution_request):
        """Test workflow execution with non-existent workflow."""
        
        # Mock workflow not found
        workflow_result = MagicMock()
        workflow_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = workflow_result
        
        with pytest.raises(ValueError, match="Workflow .* not found or access denied"):
            await execution_service.execute_workflow(
                str(uuid4()),
                execution_request,
                auth_context
            )

    @pytest.mark.asyncio
    async def test_execute_workflow_tenant_isolation(self, execution_service, mock_session, auth_context, sample_workflow, execution_request):
        """Test workflow execution respects tenant isolation."""
        
        # Set workflow for different tenant
        sample_workflow.tenant_id = "other-tenant"
        
        # Mock workflow found but wrong tenant
        workflow_result = MagicMock()
        workflow_result.scalar_one_or_none.return_value = None  # Returns None due to tenant filter
        mock_session.execute.return_value = workflow_result
        
        with pytest.raises(ValueError, match="Workflow .* not found or access denied"):
            await execution_service.execute_workflow(
                str(sample_workflow.workflow_id),
                execution_request,
                auth_context
            )

    @pytest.mark.asyncio
    async def test_execute_workflow_inactive_status(self, execution_service, mock_session, auth_context, sample_workflow, sample_template, execution_request):
        """Test workflow execution with inactive workflow."""
        
        # Set workflow as inactive
        sample_workflow.status = "PAUSED"
        
        # Mock workflow and template retrieval
        workflow_result = MagicMock()
        workflow_result.scalar_one_or_none.return_value = sample_workflow
        
        template_result = MagicMock()
        template_result.scalar_one_or_none.return_value = sample_template
        
        mock_session.execute.side_effect = [workflow_result, template_result]
        
        with pytest.raises(ValueError, match="Workflow .* is not active"):
            await execution_service.execute_workflow(
                str(sample_workflow.workflow_id),
                execution_request,
                auth_context
            )

    @pytest.mark.asyncio
    async def test_execute_workflow_template_not_found(self, execution_service, mock_session, auth_context, sample_workflow, execution_request):
        """Test workflow execution with missing template."""
        
        # Mock workflow found but template not found
        workflow_result = MagicMock()
        workflow_result.scalar_one_or_none.return_value = sample_workflow
        
        template_result = MagicMock()
        template_result.scalar_one_or_none.return_value = None
        
        mock_session.execute.side_effect = [workflow_result, template_result]
        
        with pytest.raises(ValueError, match="Template .* not found"):
            await execution_service.execute_workflow(
                str(sample_workflow.workflow_id),
                execution_request,
                auth_context
            )

    @pytest.mark.asyncio
    async def test_execute_workflow_error_handling(self, execution_service, mock_session, auth_context, sample_workflow, sample_template, execution_request):
        """Test workflow execution error handling."""
        
        # Mock workflow and template retrieval
        workflow_result = MagicMock()
        workflow_result.scalar_one_or_none.return_value = sample_workflow
        
        template_result = MagicMock()
        template_result.scalar_one_or_none.return_value = sample_template
        
        mock_session.execute.side_effect = [workflow_result, template_result]
        
        # Mock processing to raise exception
        with patch.object(execution_service, '_process_content_mock', side_effect=Exception("Processing failed")):
            
            result = await execution_service.execute_workflow(
                str(sample_workflow.workflow_id),
                execution_request,
                auth_context
            )
            
            # Verify error handling
            assert result.valid is False
            assert len(result.outputs) == 1
            assert "error_report" in result.outputs[0]["name"]
            assert "Processing failed" in result.outputs[0]["content"]
            assert result.processing_time_ms > 0

    @pytest.mark.asyncio
    async def test_generate_realistic_outputs_display(self, execution_service, sample_template):
        """Test generation of display outputs."""
        
        outputs = await execution_service._generate_realistic_outputs(
            "Test content",
            "text",
            sample_template,
            {"validate": True}
        )
        
        # Should have display output
        display_outputs = [o for o in outputs if o["type"] == "display"]
        assert len(display_outputs) >= 1
        
        display_output = display_outputs[0]
        assert display_output["name"] == "validation_report"
        assert "content" in display_output
        assert display_output["metadata"]["format"] == "text"

    @pytest.mark.asyncio
    async def test_generate_realistic_outputs_download(self, execution_service, sample_template):
        """Test generation of download outputs."""
        
        # Mock the content processing
        with patch.object(execution_service, '_process_content_by_template', return_value="processed,content"):
            
            outputs = await execution_service._generate_realistic_outputs(
                "Test content",
                "csv",
                sample_template,
                {"format": "csv"}
            )
            
            # Should have download output
            download_outputs = [o for o in outputs if o["type"] == "download"]
            assert len(download_outputs) >= 1
            
            download_output = download_outputs[0]
            assert download_output["name"] == "processed_file"
            assert download_output["type"] == "download"
            assert download_output["content"] == "processed,content"
            assert download_output["download_filename"].endswith(".csv")
            assert download_output["mime_type"] == "text/csv"

    @pytest.mark.asyncio
    async def test_realistic_ta1_generation(self, execution_service):
        """Test TA1 acknowledgment generation."""
        
        edi_content = "ISA*00*          *00*          *ZZ*SENDER123      *ZZ*RECEIVER456    *250816*1031*U*00401*000000001*0*P*>~"
        
        ta1 = await execution_service._realistic_ta1_generation(edi_content)
        
        # Verify TA1 structure
        assert ta1.startswith("ISA*")
        assert "TA1*" in ta1
        assert ta1.endswith("~")
        assert "RECEIVER456" in ta1  # Should swap sender/receiver
        assert "SENDER123" in ta1

    @pytest.mark.asyncio
    async def test_realistic_ta1_generation_fallback(self, execution_service):
        """Test TA1 generation fallback for invalid EDI."""
        
        invalid_edi = "Invalid EDI content"
        
        ta1 = await execution_service._realistic_ta1_generation(invalid_edi)
        
        # Should generate fallback TA1
        assert ta1.startswith("ISA*")
        assert "TA1*" in ta1
        assert ta1.endswith("~")

    @pytest.mark.asyncio
    async def test_mock_edi_validation(self, execution_service):
        """Test mock EDI validation functionality."""
        
        # Test with invalid EDI (no ISA start)
        invalid_edi = "GS*HC*SENDER*RECEIVER*20250816*1031*1*X*005010~"
        
        findings = await execution_service._mock_edi_validation(invalid_edi, {})
        
        # Should have error for missing ISA
        error_findings = [f for f in findings if f.level == "error"]
        assert len(error_findings) > 0
        assert any("ISA segment" in finding.message for finding in error_findings)

    @pytest.mark.asyncio
    async def test_mock_999_generation(self, execution_service):
        """Test 999 functional acknowledgment generation."""
        
        validation_findings = [
            ValidationFinding(
                level="error",
                code="E001",
                message="Test error",
                location=FindingLocation(
                    segment_id="ST",
                    segment_instance=1,
                    element_position=1,
                    line_number=2
                )
            )
        ]
        
        edi_content = "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *250816*1031*U*00401*000000001*0*P*>~"
        
        ack999 = await execution_service._realistic_999_generation(edi_content, validation_findings)
        
        # Should generate 999 with errors
        assert ack999 is not None
        assert ack999.startswith("ISA*")
        assert "ST*999*" in ack999
        assert "AK3*ST*1*8*E001" in ack999  # Error reference
        assert ack999.endswith("~")

    @pytest.mark.asyncio
    async def test_mock_999_generation_no_errors(self, execution_service):
        """Test 999 generation with no validation findings."""
        
        edi_content = "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *250816*1031*U*00401*000000001*0*P*>~"
        
        ack999 = await execution_service._realistic_999_generation(edi_content, [])
        
        # Should return None for no errors
        assert ack999 is None


class TestWorkflowStatusService:
    """Unit tests for WorkflowStatusService functionality."""

    @pytest.fixture
    def mock_session(self):
        """Create a mocked async session."""
        session = AsyncMock(spec=AsyncSession)
        session.execute = AsyncMock()
        return session

    @pytest.fixture
    def status_service(self, mock_session):
        """Create WorkflowStatusService instance with mocked session."""
        return WorkflowStatusService(mock_session)

    @pytest.fixture
    def auth_context(self):
        """Create a test auth context."""
        test_user = User(
            sub="test-user-123",
            preferred_username="test-user",
            email="test@example.com",
            groups=["tenant-test"],
            realm_access=RealmAccess(roles=["user"])
        )
        return AuthContext(user=test_user, tenant_id="tenant-test")

    @pytest.fixture
    def sample_workflow_deployed(self):
        """Create a sample deployed workflow for testing."""
        return Workflow(
            workflow_id=uuid4(),
            template_id=uuid4(),
            name="Test Deployed Workflow",
            tenant_id="tenant-test",
            status="ACTIVE",
            is_deployed=True,
            nifi_process_group_id="pg-123",
            nifi_parameter_context_id="pc-456",
            flow_version=1
        )

    @pytest.fixture
    def sample_workflow_mock(self):
        """Create a sample non-deployed workflow for testing."""
        return Workflow(
            workflow_id=uuid4(),
            template_id=uuid4(),
            name="Test Mock Workflow",
            tenant_id="tenant-test",
            status="ACTIVE",
            is_deployed=False
        )

    @pytest.mark.asyncio
    async def test_get_detailed_status_deployed_workflow(self, status_service, mock_session, auth_context, sample_workflow_deployed):
        """Test getting status for deployed workflow."""
        
        # Mock workflow retrieval
        workflow_result = MagicMock()
        workflow_result.scalar_one_or_none.return_value = sample_workflow_deployed
        mock_session.execute.return_value = workflow_result
        
        # Mock NiFi workflow service
        mock_nifi_status = {
            "workflow_id": str(sample_workflow_deployed.workflow_id),
            "status": "ACTIVE",
            "nifi_status": "RUNNING",
            "process_group_id": "pg-123"
        }
        
        with patch('src.services.workflow_execution_service.NiFiWorkflowService') as mock_nifi_service:
            mock_service_instance = AsyncMock()
            mock_service_instance.get_workflow_status.return_value = mock_nifi_status
            mock_nifi_service.return_value = mock_service_instance
            
            status = await status_service.get_detailed_status(
                str(sample_workflow_deployed.workflow_id),
                auth_context
            )
            
            # Verify deployed workflow status
            assert status["workflow_id"] == str(sample_workflow_deployed.workflow_id)
            assert status["is_deployed"] is True
            assert status["nifi_status"] == "RUNNING"
            assert status["process_group_id"] == "pg-123"
            
            # Verify NiFi service was called
            mock_service_instance.get_workflow_status.assert_called_once_with(sample_workflow_deployed)

    @pytest.mark.asyncio
    async def test_get_detailed_status_mock_workflow(self, status_service, mock_session, auth_context, sample_workflow_mock):
        """Test getting status for non-deployed workflow."""
        
        # Mock workflow retrieval
        workflow_result = MagicMock()
        workflow_result.scalar_one_or_none.return_value = sample_workflow_mock
        mock_session.execute.return_value = workflow_result
        
        status = await status_service.get_detailed_status(
            str(sample_workflow_mock.workflow_id),
            auth_context
        )
        
        # Verify mock workflow status
        assert status["workflow_id"] == str(sample_workflow_mock.workflow_id)
        assert status["is_deployed"] is False
        assert status["nifi_status"] == "RUNNING"  # Mock status for ACTIVE workflow
        assert status["deployment_status"] == "NOT_DEPLOYED"
        assert "execution_count" in status
        assert "success_rate" in status
        assert "health_check" in status

    @pytest.mark.asyncio
    async def test_get_detailed_status_workflow_not_found(self, status_service, mock_session, auth_context):
        """Test getting status for non-existent workflow."""
        
        # Mock workflow not found
        workflow_result = MagicMock()
        workflow_result.scalar_one_or_none.return_value = None
        
        debug_result = MagicMock()
        debug_result.scalar_one_or_none.return_value = None
        
        mock_session.execute.side_effect = [workflow_result, debug_result]
        
        with pytest.raises(ValueError, match="Workflow .* not found or access denied"):
            await status_service.get_detailed_status(
                str(uuid4()),
                auth_context
            )

    @pytest.mark.asyncio
    async def test_get_detailed_status_tenant_access_denied(self, status_service, mock_session, auth_context, sample_workflow_mock):
        """Test getting status with tenant access denial."""
        
        # Mock workflow not found for user's tenant but exists for different tenant
        workflow_result = MagicMock()
        workflow_result.scalar_one_or_none.return_value = None
        
        # But debug query finds it with different tenant
        other_tenant_workflow = Workflow(
            workflow_id=sample_workflow_mock.workflow_id,
            template_id=uuid4(),
            name="Other Tenant Workflow",
            tenant_id="other-tenant",
            status="ACTIVE",
            is_deployed=False
        )
        
        debug_result = MagicMock()
        debug_result.scalar_one_or_none.return_value = other_tenant_workflow
        
        mock_session.execute.side_effect = [workflow_result, debug_result]
        
        with pytest.raises(ValueError, match="Workflow .* found but access denied"):
            await status_service.get_detailed_status(
                str(sample_workflow_mock.workflow_id),
                auth_context
            )

    @pytest.mark.asyncio
    async def test_mock_status_methods(self, status_service, sample_workflow_mock):
        """Test mock status generation methods."""
        
        # Test different workflow statuses
        sample_workflow_mock.status = "ACTIVE"
        assert status_service._mock_nifi_status(sample_workflow_mock) == "RUNNING"
        
        sample_workflow_mock.status = "PAUSED"
        assert status_service._mock_nifi_status(sample_workflow_mock) == "STOPPED"
        
        sample_workflow_mock.status = "ERROR"
        assert status_service._mock_nifi_status(sample_workflow_mock) == "INVALID"
        
        # Test deployment status
        sample_workflow_mock.nifi_process_group_id = "pg-123"
        assert status_service._mock_deployment_status(sample_workflow_mock) == "DEPLOYED"
        
        sample_workflow_mock.nifi_process_group_id = None
        assert status_service._mock_deployment_status(sample_workflow_mock) == "NOT_DEPLOYED"
        
        # Test health check
        sample_workflow_mock.status = "ACTIVE"
        health = status_service._mock_health_check(sample_workflow_mock)
        assert health["status"] == "healthy"
        assert health["issues"] == []
        
        sample_workflow_mock.status = "ERROR"
        health = status_service._mock_health_check(sample_workflow_mock)
        assert health["status"] == "unhealthy"
        assert len(health["issues"]) > 0