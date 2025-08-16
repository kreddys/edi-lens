"""
Unit tests for Workflow Deployment Service.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4

from src.nifi.services.deployment_service import WorkflowDeploymentService, WorkflowDeploymentResult
from src.models.workflow_template import Workflow, WorkflowTemplate
from src.core.auth import AuthContext

pytestmark = pytest.mark.unit


class TestWorkflowDeploymentService:
    """Test Workflow Deployment Service."""

    @pytest.fixture
    def deployment_service(self):
        """Create a deployment service fixture."""
        return WorkflowDeploymentService(
            nifi_url="http://localhost:8080",
            registry_url="http://localhost:18080",
            nifi_auth_token="nifi-token",
            registry_auth_token="registry-token"
        )

    @pytest.fixture
    def mock_workflow(self):
        """Create a mock workflow."""
        workflow = MagicMock()
        workflow.workflow_id = uuid4()
        workflow.name = "Test Workflow"
        workflow.template_id = "test-template-1"
        workflow.tenant_id = "tenant-a"
        workflow.status = "ACTIVE"
        workflow.configuration = {
            "input_path": "/sftp/tenant-a/in/",
            "validation_schema": "837.json"
        }
        workflow.nifi_process_group_id = None
        workflow.nifi_parameter_context_id = None
        return workflow

    @pytest.fixture
    def mock_template(self):
        """Create a mock template."""
        template = MagicMock()
        template.template_id = "test-template-1"
        template.name = "Test Template"
        template.description = "A test template"
        template.status = "ACTIVE"
        template.deployment_method = "registry"
        template.flow_definition = {
            "processors": [
                {
                    "id": "test-processor",
                    "type": "GetFile",
                    "name": "Test Processor",
                    "position": {"x": 100, "y": 100},
                    "properties": {"Input Directory": "${INPUT_PATH}"}
                }
            ],
            "connections": []
        }
        return template

    @pytest.fixture
    def mock_auth_context(self):
        """Create a mock auth context."""
        auth_context = MagicMock()
        auth_context.tenant_id = "tenant-a"
        auth_context.user_id = "user-123"
        return auth_context

    @pytest.mark.asyncio
    async def test_deployment_service_initialization(self):
        """Test deployment service initialization."""
        service = WorkflowDeploymentService(
            nifi_url="http://localhost:8080",
            registry_url="http://localhost:18080"
        )
        
        assert service.nifi_url == "http://localhost:8080"
        assert service.registry_url == "http://localhost:18080"
        assert service.nifi_auth_token is None
        assert service.registry_auth_token is None

    @pytest.mark.asyncio
    async def test_xml_flow_conversion(self, deployment_service, mock_workflow, mock_template):
        """Test XML flow definition conversion."""
        # Test the XML conversion method
        xml_flow = deployment_service._convert_json_to_nifi_xml(
            mock_template.flow_definition,
            mock_workflow
        )
        
        # Verify XML contains expected elements
        assert "<template" in xml_flow
        assert "<processors>" in xml_flow
        assert "<processor>" in xml_flow
        assert "test-processor" in xml_flow
        assert "Test Processor" in xml_flow
        assert "GetFile" in xml_flow
        assert "${INPUT_PATH}" in xml_flow

    @pytest.mark.asyncio
    async def test_deploy_workflow_registry_success(self, deployment_service, mock_workflow, mock_template, mock_auth_context):
        """Test successful workflow deployment via registry."""
        # Mock session
        mock_session = AsyncMock()
        
        # Mock database queries
        mock_session.execute.return_value.scalar_one_or_none.side_effect = [
            mock_workflow,  # First call for workflow
            mock_template   # Second call for template
        ]
        mock_session.commit = AsyncMock()
        
        # Mock the private methods
        with patch.object(deployment_service, '_get_workflow', return_value=mock_workflow), \
             patch.object(deployment_service, '_get_template', return_value=mock_template), \
             patch.object(deployment_service, '_validate_workflow_readiness'), \
             patch.object(deployment_service, '_deploy_via_registry') as mock_deploy:
            
            # Setup mock deployment result
            mock_deploy.return_value = WorkflowDeploymentResult(
                success=True,
                workflow_id=str(mock_workflow.workflow_id),
                nifi_process_group_id="pg-123",
                nifi_parameter_context_id="pc-456",
                deployment_method="registry",
                flow_version=1
            )
            
            # Test deployment
            result = await deployment_service.deploy_workflow(
                mock_session,
                str(mock_workflow.workflow_id),
                mock_auth_context
            )
            
            # Verify results
            assert result.success is True
            assert result.workflow_id == str(mock_workflow.workflow_id)
            assert result.nifi_process_group_id == "pg-123"
            assert result.nifi_parameter_context_id == "pc-456"
            assert result.deployment_method == "registry"

    @pytest.mark.asyncio
    async def test_deploy_workflow_xml_fallback(self, deployment_service, mock_workflow, mock_template, mock_auth_context):
        """Test workflow deployment fallback to XML method."""
        # Set template to use XML deployment
        mock_template.deployment_method = "xml"
        
        # Mock session
        mock_session = AsyncMock()
        
        # Mock the private methods
        with patch.object(deployment_service, '_get_workflow', return_value=mock_workflow), \
             patch.object(deployment_service, '_get_template', return_value=mock_template), \
             patch.object(deployment_service, '_validate_workflow_readiness'), \
             patch.object(deployment_service, '_deploy_via_xml') as mock_deploy:
            
            # Setup mock deployment result
            mock_deploy.return_value = WorkflowDeploymentResult(
                success=True,
                workflow_id=str(mock_workflow.workflow_id),
                nifi_process_group_id="pg-789",
                nifi_parameter_context_id="pc-101",
                deployment_method="xml",
                flow_version=1
            )
            
            # Test deployment
            result = await deployment_service.deploy_workflow(
                mock_session,
                str(mock_workflow.workflow_id),
                mock_auth_context
            )
            
            # Verify XML deployment was called
            mock_deploy.assert_called_once()
            assert result.deployment_method == "xml"

    @pytest.mark.asyncio
    async def test_deploy_workflow_validation_failure(self, deployment_service, mock_workflow, mock_template, mock_auth_context):
        """Test workflow deployment with validation failure."""
        # Set workflow to inactive status
        mock_workflow.status = "INACTIVE"
        
        # Mock session
        mock_session = AsyncMock()
        
        # Mock the private methods
        with patch.object(deployment_service, '_get_workflow', return_value=mock_workflow), \
             patch.object(deployment_service, '_get_template', return_value=mock_template):
            
            # Test deployment - should fail validation
            result = await deployment_service.deploy_workflow(
                mock_session,
                str(mock_workflow.workflow_id),
                mock_auth_context
            )
            
            # Verify deployment failed
            assert result.success is False
            assert "not in a deployable state" in result.error_message

    @pytest.mark.asyncio
    async def test_start_workflow(self, deployment_service, mock_workflow, mock_auth_context):
        """Test starting a deployed workflow."""
        # Set workflow as deployed
        mock_workflow.nifi_process_group_id = "pg-123"
        
        # Mock session
        mock_session = AsyncMock()
        
        # Mock NiFi client
        mock_nifi_client = AsyncMock()
        
        with patch.object(deployment_service, '_get_workflow', return_value=mock_workflow), \
             patch('src.nifi.services.deployment_service.NiFiAPIClient') as mock_client_class:
            
            # Setup mock context manager
            mock_client_class.return_value.__aenter__.return_value = mock_nifi_client
            mock_client_class.return_value.__aexit__.return_value = None
            
            # Test start workflow
            result = await deployment_service.start_workflow(
                mock_session,
                str(mock_workflow.workflow_id),
                mock_auth_context
            )
            
            # Verify workflow was started
            assert result is True
            mock_nifi_client.start_process_group.assert_called_once_with("pg-123")
            assert mock_workflow.status == "RUNNING"

    @pytest.mark.asyncio
    async def test_stop_workflow(self, deployment_service, mock_workflow, mock_auth_context):
        """Test stopping a running workflow."""
        # Set workflow as deployed and running
        mock_workflow.nifi_process_group_id = "pg-123"
        mock_workflow.status = "RUNNING"
        
        # Mock session
        mock_session = AsyncMock()
        
        # Mock NiFi client
        mock_nifi_client = AsyncMock()
        
        with patch.object(deployment_service, '_get_workflow', return_value=mock_workflow), \
             patch('src.nifi.services.deployment_service.NiFiAPIClient') as mock_client_class:
            
            # Setup mock context manager
            mock_client_class.return_value.__aenter__.return_value = mock_nifi_client
            mock_client_class.return_value.__aexit__.return_value = None
            
            # Test stop workflow
            result = await deployment_service.stop_workflow(
                mock_session,
                str(mock_workflow.workflow_id),
                mock_auth_context
            )
            
            # Verify workflow was stopped
            assert result is True
            mock_nifi_client.stop_process_group.assert_called_once_with("pg-123")
            assert mock_workflow.status == "STOPPED"

    @pytest.mark.asyncio
    async def test_undeploy_workflow(self, deployment_service, mock_workflow, mock_auth_context):
        """Test undeploying a workflow."""
        # Set workflow as deployed
        mock_workflow.nifi_process_group_id = "pg-123"
        mock_workflow.nifi_parameter_context_id = "pc-456"
        
        # Mock session
        mock_session = AsyncMock()
        
        # Mock NiFi client
        mock_nifi_client = AsyncMock()
        
        with patch.object(deployment_service, '_get_workflow', return_value=mock_workflow), \
             patch('src.nifi.services.deployment_service.NiFiAPIClient') as mock_client_class:
            
            # Setup mock context manager
            mock_client_class.return_value.__aenter__.return_value = mock_nifi_client
            mock_client_class.return_value.__aexit__.return_value = None
            
            # Test undeploy workflow
            result = await deployment_service.undeploy_workflow(
                mock_session,
                str(mock_workflow.workflow_id),
                mock_auth_context
            )
            
            # Verify workflow was undeployed
            assert result is True
            mock_nifi_client.delete_process_group.assert_called_once_with("pg-123")
            assert mock_workflow.nifi_process_group_id is None
            assert mock_workflow.nifi_parameter_context_id is None
            assert mock_workflow.status == "INACTIVE"

    @pytest.mark.asyncio
    async def test_restart_workflow(self, deployment_service, mock_workflow, mock_auth_context):
        """Test restarting a workflow."""
        # Mock session
        mock_session = AsyncMock()
        
        with patch.object(deployment_service, 'undeploy_workflow', return_value=True) as mock_undeploy, \
             patch.object(deployment_service, 'deploy_workflow') as mock_deploy:
            
            # Setup mock deployment result
            mock_deploy.return_value = WorkflowDeploymentResult(
                success=True,
                workflow_id=str(mock_workflow.workflow_id),
                nifi_process_group_id="pg-new",
                nifi_parameter_context_id="pc-new"
            )
            
            # Test restart workflow
            result = await deployment_service.restart_workflow(
                mock_session,
                str(mock_workflow.workflow_id),
                mock_auth_context
            )
            
            # Verify workflow was restarted
            mock_undeploy.assert_called_once()
            mock_deploy.assert_called_once()
            assert result.success is True