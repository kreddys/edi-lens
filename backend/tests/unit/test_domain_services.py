"""
Unit tests for domain-based services.

These tests use mocks and don't require actual NiFi/Registry instances.
They test the business logic and error handling of our domain services.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.services.nifi_flow_deployment import NiFiFlowDeployment, NiFiFlowDeploymentError
from src.services.nifi_flow_management import NiFiFlowManagement, NiFiFlowManagementError
from src.services.nifi_parameter_management import NiFiParameterManagement, NiFiParameterManagementError
from src.services.registry_bucket_management import RegistryBucketManagement, RegistryBucketManagementError
from src.services.registry_flow_management import RegistryFlowManagement, RegistryFlowManagementError
from src.services.registry_version_management import RegistryVersionManagement, RegistryVersionManagementError
from src.services.integration_bridge import IntegrationBridge, IntegrationBridgeError
from src.services.workflow_orchestrator import WorkflowOrchestrator, WorkflowOrchestratorError


class TestNiFiFlowDeployment:
    """Test NiFi flow deployment service."""

    @pytest.fixture
    def mock_nifi_client(self):
        """Mock NiFi unified client."""
        client = MagicMock()
        client.process_groups = MagicMock()
        client.processors = MagicMock()
        client.connections = MagicMock()
        client.parameter_contexts = MagicMock()
        return client

    @pytest.fixture
    def deployment_service(self, mock_nifi_client):
        """NiFi flow deployment service with mocked client."""
        return NiFiFlowDeployment(mock_nifi_client)

    @pytest.mark.asyncio
    async def test_deploy_flow_success(self, deployment_service, mock_nifi_client):
        """Test successful flow deployment."""
        # Mock successful responses
        mock_nifi_client.parameter_contexts.create_parameter_context = AsyncMock(
            return_value={"id": "param-ctx-123"}
        )
        mock_nifi_client.process_groups.create_process_group = AsyncMock(
            return_value={"id": "pg-123"}
        )
        mock_nifi_client.process_groups.set_parameter_context = AsyncMock()

        # Mock processor deployment
        deployment_service._deploy_processors = AsyncMock(
            return_value=({"proc-1": "proc-id-1"}, [])
        )
        deployment_service._deploy_connections = AsyncMock(return_value=[])
        deployment_service._validate_components = AsyncMock(return_value=[])

        flow_definition = {
            "processors": [{"name": "TestProcessor", "type": "org.apache.nifi.processor.TestProcessor"}],
            "connections": []
        }
        parameters = {"param1": "value1"}

        result = await deployment_service.deploy_flow(
            flow_definition=flow_definition,
            flow_name="test-flow",
            parameters=parameters
        )

        assert result["success"] is True
        assert result["process_group_id"] == "pg-123"
        assert result["parameter_context_id"] == "param-ctx-123"
        assert len(result["failures"]) == 0

    @pytest.mark.asyncio
    async def test_deploy_flow_with_failures(self, deployment_service, mock_nifi_client):
        """Test flow deployment with component failures."""
        # Mock successful infrastructure creation
        mock_nifi_client.parameter_contexts.create_parameter_context = AsyncMock(
            return_value={"id": "param-ctx-123"}
        )
        mock_nifi_client.process_groups.create_process_group = AsyncMock(
            return_value={"id": "pg-123"}
        )
        mock_nifi_client.process_groups.set_parameter_context = AsyncMock()

        # Mock processor deployment with failures
        deployment_service._deploy_processors = AsyncMock(
            return_value=({}, [{"component_type": "processor", "component_name": "FailedProcessor", "error_type": "creation", "message": "Invalid configuration"}])
        )
        deployment_service._deploy_connections = AsyncMock(return_value=[])
        deployment_service._validate_components = AsyncMock(return_value=[])

        # Mock cleanup
        deployment_service.cleanup_failed_deployment = AsyncMock()

        flow_definition = {
            "processors": [{"name": "FailedProcessor", "type": "invalid.processor"}],
            "connections": []
        }

        result = await deployment_service.deploy_flow(
            flow_definition=flow_definition,
            flow_name="test-flow"
        )

        assert result["success"] is False
        assert len(result["failures"]) == 1
        assert result["failures"][0]["component_name"] == "FailedProcessor"
        deployment_service.cleanup_failed_deployment.assert_called_once()

    @pytest.mark.asyncio
    async def test_deploy_flow_exception_handling(self, deployment_service, mock_nifi_client):
        """Test deployment with unexpected exceptions."""
        # Mock exception during process group creation
        mock_nifi_client.process_groups.create_process_group = AsyncMock(
            side_effect=Exception("NiFi connection failed")
        )

        flow_definition = {"processors": [], "connections": []}

        result = await deployment_service.deploy_flow(
            flow_definition=flow_definition,
            flow_name="test-flow"
        )

        assert result["success"] is False
        assert len(result["failures"]) == 1
        assert result["failures"][0]["component_type"] == "deployment"
        assert "NiFi connection failed" in result["failures"][0]["message"]


class TestNiFiFlowManagement:
    """Test NiFi flow management service."""

    @pytest.fixture
    def mock_nifi_client(self):
        """Mock NiFi unified client."""
        client = MagicMock()
        client.process_groups = MagicMock()
        client.processors = MagicMock()
        return client

    @pytest.fixture
    def flow_management_service(self, mock_nifi_client):
        """NiFi flow management service with mocked client."""
        return NiFiFlowManagement(mock_nifi_client)

    @pytest.mark.asyncio
    async def test_start_flow_success(self, flow_management_service, mock_nifi_client):
        """Test successful flow start."""
        # Mock processors response
        flow_management_service._get_processors_in_group = AsyncMock(
            return_value=[
                {"id": "proc-1", "component": {"name": "Processor1"}},
                {"id": "proc-2", "component": {"name": "Processor2"}}
            ]
        )
        mock_nifi_client.processors.start_processor = AsyncMock()

        result = await flow_management_service.start_flow("pg-123")

        assert result["success"] is True
        assert result["total_processors"] == 2
        assert result["started_processors"] == 2
        assert len(result["failed_processors"]) == 0
        assert result["status"] == "running"

    @pytest.mark.asyncio
    async def test_start_flow_partial_failure(self, flow_management_service, mock_nifi_client):
        """Test flow start with some processor failures."""
        # Mock processors response
        flow_management_service._get_processors_in_group = AsyncMock(
            return_value=[
                {"id": "proc-1", "component": {"name": "Processor1"}},
                {"id": "proc-2", "component": {"name": "Processor2"}}
            ]
        )

        # Mock first processor succeeds, second fails
        mock_nifi_client.processors.start_processor = AsyncMock(
            side_effect=[None, Exception("Processor configuration invalid")]
        )

        result = await flow_management_service.start_flow("pg-123")

        assert result["success"] is False
        assert result["total_processors"] == 2
        assert result["started_processors"] == 1
        assert len(result["failed_processors"]) == 1
        assert result["failed_processors"][0]["processor_name"] == "Processor2"
        assert result["status"] == "partially_running"

    @pytest.mark.asyncio
    async def test_get_flow_status(self, flow_management_service, mock_nifi_client):
        """Test getting comprehensive flow status."""
        # Mock process group response
        mock_nifi_client.process_groups.get_process_group = AsyncMock(
            return_value={"component": {"name": "TestFlow"}}
        )

        # Mock processors response
        flow_management_service._get_processors_in_group = AsyncMock(
            return_value=[
                {"id": "proc-1", "component": {"name": "Processor1", "state": "RUNNING", "validationStatus": "VALID"}},
                {"id": "proc-2", "component": {"name": "Processor2", "state": "STOPPED", "validationStatus": "VALID"}}
            ]
        )

        result = await flow_management_service.get_flow_status("pg-123")

        assert result["process_group_id"] == "pg-123"
        assert result["process_group_name"] == "TestFlow"
        assert result["overall_status"] == "partially_running"
        assert result["total_processors"] == 2
        assert result["running_processors"] == 1
        assert result["stopped_processors"] == 1
        assert result["invalid_processors"] == 0


class TestRegistryBucketManagement:
    """Test Registry bucket management service."""

    @pytest.fixture
    def mock_registry_client(self):
        """Mock Registry unified client."""
        client = MagicMock()
        client.buckets = MagicMock()
        return client

    @pytest.fixture
    def bucket_management_service(self, mock_registry_client):
        """Registry bucket management service with mocked client."""
        return RegistryBucketManagement(mock_registry_client)

    @pytest.mark.asyncio
    async def test_create_bucket_success(self, bucket_management_service, mock_registry_client):
        """Test successful bucket creation."""
        mock_registry_client.buckets.create_bucket = AsyncMock(
            return_value={
                "identifier": "bucket-123",
                "name": "test-bucket",
                "createdTimestamp": 1234567890
            }
        )

        result = await bucket_management_service.create_bucket(
            name="test-bucket",
            description="Test bucket"
        )

        assert result["success"] is True
        assert result["bucket_id"] == "bucket-123"
        assert result["name"] == "test-bucket"

    @pytest.mark.asyncio
    async def test_get_or_create_bucket_existing(self, bucket_management_service, mock_registry_client):
        """Test get_or_create with existing bucket."""
        # Mock list_buckets to return existing bucket
        bucket_management_service.list_buckets = AsyncMock(
            return_value=[{"bucket_id": "bucket-123", "name": "existing-bucket"}]
        )

        result = await bucket_management_service.get_or_create_bucket("existing-bucket")

        assert result["bucket_id"] == "bucket-123"
        assert result["name"] == "existing-bucket"

    @pytest.mark.asyncio
    async def test_get_or_create_bucket_new(self, bucket_management_service, mock_registry_client):
        """Test get_or_create with new bucket."""
        # Mock list_buckets to return empty
        bucket_management_service.list_buckets = AsyncMock(return_value=[])

        # Mock create_bucket
        bucket_management_service.create_bucket = AsyncMock(
            return_value={"success": True, "bucket_id": "bucket-456", "name": "new-bucket"}
        )

        result = await bucket_management_service.get_or_create_bucket("new-bucket")

        assert result["bucket_id"] == "bucket-456"
        assert result["name"] == "new-bucket"


class TestWorkflowOrchestrator:
    """Test workflow orchestrator."""

    @pytest.fixture
    def mock_nifi_client(self):
        """Mock NiFi client."""
        return MagicMock()

    @pytest.fixture
    def mock_registry_client(self):
        """Mock Registry client."""
        return MagicMock()

    @pytest.fixture
    def orchestrator(self, mock_nifi_client, mock_registry_client):
        """Workflow orchestrator with mocked clients."""
        return WorkflowOrchestrator(mock_nifi_client, mock_registry_client)

    @pytest.mark.asyncio
    async def test_deploy_and_register_flow_success(self, orchestrator):
        """Test successful deploy and register workflow."""
        # Mock successful NiFi deployment
        orchestrator.nifi_deployment.deploy_flow = AsyncMock(
            return_value={
                "success": True,
                "process_group_id": "pg-123",
                "parameter_context_id": "param-ctx-123",
                "summary": {"total_processors": 2, "created_processors": 2}
            }
        )

        # Mock successful bucket creation
        orchestrator.registry_bucket_mgmt.get_or_create_bucket = AsyncMock(
            return_value={"bucket_id": "bucket-123"}
        )

        # Mock successful Registry upload
        orchestrator.integration_bridge.upload_flow_to_registry = AsyncMock(
            return_value={
                "success": True,
                "flow_id": "flow-123",
                "version": 1,
                "created_timestamp": 1234567890
            }
        )

        flow_definition = {
            "processors": [{"name": "TestProcessor", "type": "org.apache.nifi.processor.TestProcessor"}],
            "connections": []
        }

        result = await orchestrator.deploy_and_register_flow(
            flow_definition=flow_definition,
            flow_name="test-flow",
            bucket_name="test-bucket"
        )

        assert result["success"] is True
        assert result["stage"] == "completed"
        assert result["process_group_id"] == "pg-123"
        assert "nifi_deployment" in result
        assert "registry_upload" in result

    @pytest.mark.asyncio
    async def test_deploy_and_register_flow_nifi_failure(self, orchestrator):
        """Test deploy and register with NiFi deployment failure."""
        # Mock failed NiFi deployment
        orchestrator.nifi_deployment.deploy_flow = AsyncMock(
            return_value={
                "success": False,
                "failures": [{"component_type": "processor", "message": "Invalid configuration"}]
            }
        )

        flow_definition = {"processors": [], "connections": []}

        result = await orchestrator.deploy_and_register_flow(
            flow_definition=flow_definition,
            flow_name="test-flow",
            bucket_name="test-bucket"
        )

        assert result["success"] is False
        assert result["stage"] == "nifi_deployment"
        assert "Flow deployment to NiFi failed" in result["message"]

    @pytest.mark.asyncio
    async def test_deploy_and_register_flow_registry_failure(self, orchestrator):
        """Test deploy and register with Registry upload failure."""
        # Mock successful NiFi deployment
        orchestrator.nifi_deployment.deploy_flow = AsyncMock(
            return_value={
                "success": True,
                "process_group_id": "pg-123",
                "summary": {"total_processors": 1}
            }
        )

        # Mock successful bucket creation
        orchestrator.registry_bucket_mgmt.get_or_create_bucket = AsyncMock(
            return_value={"bucket_id": "bucket-123"}
        )

        # Mock failed Registry upload
        orchestrator.integration_bridge.upload_flow_to_registry = AsyncMock(
            side_effect=Exception("Registry connection failed")
        )

        flow_definition = {"processors": [], "connections": []}

        result = await orchestrator.deploy_and_register_flow(
            flow_definition=flow_definition,
            flow_name="test-flow",
            bucket_name="test-bucket"
        )

        assert result["success"] is False
        assert result["stage"] == "registry_upload"
        assert "Registry upload failed" in result["message"]
        assert result["process_group_id"] == "pg-123"  # NiFi deployment succeeded


if __name__ == "__main__":
    pytest.main([__file__, "-v"])