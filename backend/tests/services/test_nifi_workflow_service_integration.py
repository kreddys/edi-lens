"""
DEPRECATED: Old NiFiWorkflowService integration tests.

These tests are deprecated in favor of the new Registry-first architecture.
The old WorkflowTemplate and Workflow models have been replaced with
RegistryTemplate and WorkflowInstance models.

See test_registry_workflow_service_integration.py for the new tests.
"""

import pytest
import uuid
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession

# Note: These imports will fail because the old models were removed
# from src.services.nifi_workflow_service import NiFiWorkflowService, NiFiWorkflowDeploymentError
# from src.models.workflow_template import Workflow, WorkflowTemplate
from src.core.config import settings
from src.nifi.clients.nifi_client import NiFiAPIClient

pytestmark = [pytest.mark.integration]


@pytest.fixture
def nifi_workflow_service(db_session: AsyncSession):
    """DEPRECATED: Provides an instance of the NiFiWorkflowService."""
    pytest.skip("Deprecated: NiFiWorkflowService replaced by Registry-first architecture")


async def create_test_template(db_session: AsyncSession):
    """Helper function to create a test workflow template."""
    template = WorkflowTemplate(
        template_id=f"test-template-{uuid.uuid4()}",
        name="Test Workflow Template",
        description="A template for integration testing.",
        category="TEST",
        scope="TENANT",
        tenant_id="test-tenant",
        flow_definition={
            "processors": [
                {
                    "id": "test-processor",
                    "name": "GenerateFlowFile",
                    "type": "org.apache.nifi.processors.standard.GenerateFlowFile",
                    "properties": {
                        "Batch Size": "1",
                        "File Size": "1KB"
                    }
                }
            ]
        },
        configuration_schema={}
    )
    db_session.add(template)
    await db_session.commit()
    await db_session.refresh(template)
    return template


async def create_test_workflow(nifi_workflow_service, template):
    """DEPRECATED: Helper function to create a test workflow."""
    pytest.skip("Deprecated: Workflow model replaced by WorkflowInstance")


class TestNiFiWorkflowServiceIntegration:
    """DEPRECATED: Integration tests for the NiFiWorkflowService.
    
    These tests are deprecated. See test_registry_workflow_service_integration.py
    for the new Registry-first tests.
    """

    @pytest.mark.asyncio
    async def test_create_workflow(self, nifi_workflow_service, db_session: AsyncSession):
        """DEPRECATED: Tests the creation of a workflow."""
        pytest.skip("Deprecated: Use Registry-first architecture tests")
        template = await create_test_template(db_session)
        workflow = await create_test_workflow(nifi_workflow_service, template)

        assert workflow is not None
        assert workflow.name == "Test Workflow"
        assert workflow.template_id == template.template_id
        assert workflow.tenant_id == "test-tenant"
        assert workflow.created_by == "test-user"

        # Cleanup
        await db_session.delete(workflow)
        await db_session.delete(template)
        await db_session.commit()

    @pytest.mark.asyncio
    async def test_deploy_and_undeploy_workflow(self, nifi_workflow_service, db_session: AsyncSession):
        """DEPRECATED: Tests the deployment and undeployment of a workflow."""
        pytest.skip("Deprecated: Use Registry-first architecture tests")
        template = await create_test_template(db_session)
        workflow = await create_test_workflow(nifi_workflow_service, template)

        # Deploy the workflow
        try:
            deployed_workflow = await nifi_workflow_service.deploy_workflow(workflow)
        except NiFiWorkflowDeploymentError as e:
            pytest.skip(f"NiFi services not available for deployment testing: {e}")

        assert deployed_workflow.status == "ACTIVE"
        assert deployed_workflow.nifi_process_group_id is not None
        assert deployed_workflow.nifi_parameter_context_id is not None

        # Verify in NiFi
        async with NiFiAPIClient(settings.NIFI_URL, username=settings.NIFI_USERNAME, password=settings.NIFI_PASSWORD) as nifi_client:
            pg = await nifi_client.get_process_group(deployed_workflow.nifi_process_group_id)
            assert pg is not None

        # Undeploy the workflow
        undeployed_workflow = await nifi_workflow_service.undeploy_workflow(deployed_workflow)
        assert undeployed_workflow.status == "DELETED"
        assert undeployed_workflow.nifi_process_group_id is None

        # Verify in NiFi that the process group is deleted
        async with NiFiAPIClient(settings.NIFI_URL, username=settings.NIFI_USERNAME, password=settings.NIFI_PASSWORD) as nifi_client:
            with pytest.raises(Exception):
                await nifi_client.get_process_group(deployed_workflow.nifi_process_group_id)
        
        # Cleanup
        await db_session.delete(undeployed_workflow)
        await db_session.delete(template)
        await db_session.commit()

    @pytest.mark.asyncio
    async def test_start_stop_workflow(self, nifi_workflow_service, db_session: AsyncSession):
        """DEPRECATED: Tests starting and stopping a deployed workflow."""
        pytest.skip("Deprecated: Use Registry-first architecture tests")
        template = await create_test_template(db_session)
        workflow = await create_test_workflow(nifi_workflow_service, template)

        # Deploy the workflow
        try:
            deployed_workflow = await nifi_workflow_service.deploy_workflow(workflow)
        except NiFiWorkflowDeploymentError as e:
            pytest.skip(f"NiFi services not available for deployment testing: {e}")

        # Start the workflow
        started_workflow = await nifi_workflow_service.start_workflow(deployed_workflow)
        assert started_workflow.status == "ACTIVE"

        # Stop the workflow
        stopped_workflow = await nifi_workflow_service.stop_workflow(started_workflow)
        assert stopped_workflow.status == "PAUSED"

        # Add a small delay to allow NiFi to stop the process group
        await asyncio.sleep(2)

        # Cleanup
        await nifi_workflow_service.undeploy_workflow(stopped_workflow)
        await db_session.delete(stopped_workflow)
        await db_session.delete(template)
        await db_session.commit()

    @pytest.mark.asyncio
    async def test_get_workflow_status(self, nifi_workflow_service, db_session: AsyncSession):
        """DEPRECATED: Tests getting the status of a deployed workflow."""
        pytest.skip("Deprecated: Use Registry-first architecture tests")
        template = await create_test_template(db_session)
        workflow = await create_test_workflow(nifi_workflow_service, template)

        # Deploy the workflow
        try:
            deployed_workflow = await nifi_workflow_service.deploy_workflow(workflow)
        except NiFiWorkflowDeploymentError as e:
            pytest.skip(f"NiFi services not available for deployment testing: {e}")

        # Get status
        status = await nifi_workflow_service.get_workflow_status(deployed_workflow)
        assert status["status"] == "ACTIVE"
        assert status["nifi_status"] is not None

        # Cleanup
        await nifi_workflow_service.undeploy_workflow(deployed_workflow)
        await db_session.delete(deployed_workflow)
        await db_session.delete(template)
        await db_session.commit()
