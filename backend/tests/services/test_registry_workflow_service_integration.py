"""
Integration tests for Registry-first workflow service.

These tests validate the service's interaction with NiFi Registry and NiFi instance.
"""

import pytest
import uuid
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.registry_service import RegistryService, RegistryServiceError
from src.models.registry_models import RegistryTemplate, WorkflowInstance
from src.core.config import settings

pytestmark = [pytest.mark.integration]


@pytest.fixture
def registry_service(db_session: AsyncSession) -> RegistryService:
    """Provides an instance of the RegistryService."""
    return RegistryService(db_session)


def generate_test_flow_definition():
    """Generate a test flow definition."""
    return {
        "processors": [
            {
                "id": f"test-processor-{uuid.uuid4().hex[:8]}",
                "name": "Test Generate FlowFile",
                "type": "org.apache.nifi.processors.standard.GenerateFlowFile",
                "position": {"x": 100, "y": 100},
                "properties": {
                    "Batch Size": "1",
                    "File Size": "1KB",
                    "Data Format": "Text"
                }
            },
            {
                "id": f"test-log-{uuid.uuid4().hex[:8]}",
                "name": "Test Log Message",
                "type": "org.apache.nifi.processors.standard.LogMessage",
                "position": {"x": 400, "y": 100},
                "properties": {
                    "Log Level": "INFO"
                }
            }
        ],
        "connections": [
            {
                "id": f"test-connection-{uuid.uuid4().hex[:8]}",
                "source": {"id": "test-processor"},
                "destination": {"id": "test-log"},
                "selectedRelationships": ["success"]
            }
        ]
    }


async def create_test_registry_template(registry_service: RegistryService) -> RegistryTemplate:
    """Helper function to create a test Registry template."""
    try:
        template = await registry_service.create_template(
            name=f"Test Registry Template {uuid.uuid4().hex[:8]}",
            description="A template for Registry integration testing.",
            flow_definition=generate_test_flow_definition(),
            scope="GLOBAL",
            created_by="test-user"
        )
        return template
    except RegistryServiceError as e:
        pytest.skip(f"NiFi Registry not available for testing: {str(e)}")


async def create_test_workflow_instance(registry_service: RegistryService, template: RegistryTemplate) -> WorkflowInstance:
    """Helper function to create a test workflow instance."""
    workflow_data = {
        "name": f"Test Workflow Instance {uuid.uuid4().hex[:8]}",
        "tenant_id": "test-tenant",
        "configuration": {
            "batch_size": "5",
            "file_size": "2KB",
            "log_level": "DEBUG"
        },
        "description": "A test workflow instance.",
        "created_by": "test-user"
    }
    
    return await registry_service.create_workflow_instance(
        template_id=template.template_id,
        name=workflow_data["name"],
        tenant_id=workflow_data["tenant_id"],
        configuration=workflow_data["configuration"],
        description=workflow_data["description"],
        created_by=workflow_data["created_by"]
    )


class TestRegistryWorkflowServiceIntegration:
    """Integration tests for the Registry-first workflow service."""

    @pytest.mark.asyncio
    async def test_create_registry_template(self, registry_service: RegistryService):
        """Tests the creation of a Registry template."""
        template = await create_test_registry_template(registry_service)

        assert template is not None
        assert template.name.startswith("Test Registry Template")
        assert template.scope == "GLOBAL"
        assert template.current_version == 1
        assert template.template_id is not None
        assert template.bucket_id is not None

    @pytest.mark.asyncio
    async def test_create_workflow_instance(self, registry_service: RegistryService):
        """Tests the creation of a workflow instance from Registry template."""
        template = await create_test_registry_template(registry_service)
        workflow = await create_test_workflow_instance(registry_service, template)

        assert workflow is not None
        assert workflow.name.startswith("Test Workflow Instance")
        assert workflow.template_id == template.template_id
        assert workflow.template_version == template.current_version
        assert workflow.tenant_id == "test-tenant"
        assert workflow.status == "CREATED"
        assert workflow.configuration["batch_size"] == "5"

    @pytest.mark.asyncio
    async def test_template_versioning(self, registry_service: RegistryService):
        """Tests Registry template versioning."""
        template = await create_test_registry_template(registry_service)
        
        # Update template to create version 2
        updated_flow = generate_test_flow_definition()
        updated_flow["processors"].append({
            "id": f"test-putfile-{uuid.uuid4().hex[:8]}",
            "name": "Test Put File",
            "type": "org.apache.nifi.processors.standard.PutFile",
            "position": {"x": 700, "y": 100},
            "properties": {
                "Directory": "/tmp/test-output"
            }
        })
        
        updated_template = await registry_service.update_template(
            template_id=template.template_id,
            flow_definition=updated_flow,
            comments="Added PutFile processor for testing",
            updated_by="test-user"
        )
        
        assert updated_template.current_version == 2
        
        # Verify we can get both versions
        v1_flow = await registry_service.get_template_flow_definition(template.template_id, version=1)
        v2_flow = await registry_service.get_template_flow_definition(template.template_id, version=2)
        
        assert len(v1_flow["processors"]) == 2  # Original processors
        assert len(v2_flow["processors"]) == 3  # Original + PutFile

    @pytest.mark.asyncio
    async def test_workflow_instance_with_relationships(self, registry_service: RegistryService):
        """Tests workflow instance creation with template relationships."""
        template = await create_test_registry_template(registry_service)
        workflow = await create_test_workflow_instance(registry_service, template)
        
        # Get workflow with template relationship
        workflow_with_template = await registry_service.get_workflow_instance(workflow.workflow_id)
        
        assert workflow_with_template is not None
        assert workflow_with_template.template is not None
        assert workflow_with_template.template.name == template.name
        assert workflow_with_template.template.template_id == template.template_id

    @pytest.mark.asyncio
    async def test_deploy_workflow_instance(self, registry_service: RegistryService):
        """Tests deploying a workflow instance to NiFi (if available)."""
        template = await create_test_registry_template(registry_service)
        workflow = await create_test_workflow_instance(registry_service, template)
        
        # Attempt to deploy the workflow
        try:
            deployed_workflow = await registry_service.deploy_workflow_instance(workflow.workflow_id)
            
            # If deployment succeeds, verify the deployment
            assert deployed_workflow.status == "DEPLOYED"
            assert deployed_workflow.nifi_process_group_id is not None
            assert deployed_workflow.deployed_at is not None
            
            # Note: We don't test actual NiFi operations here as they require
            # a fully configured NiFi instance with Registry integration
            
        except RegistryServiceError as e:
            # Skip if NiFi deployment is not available
            if "NiFi" in str(e) or "deployment" in str(e).lower():
                pytest.skip(f"NiFi deployment not available for testing: {str(e)}")
            else:
                raise

    @pytest.mark.asyncio
    async def test_list_templates_and_workflows(self, registry_service: RegistryService):
        """Tests listing templates and workflow instances."""
        # Create a test template and workflow
        template = await create_test_registry_template(registry_service)
        workflow = await create_test_workflow_instance(registry_service, template)
        
        # List templates
        templates = await registry_service.list_templates(scope="GLOBAL")
        assert len(templates) > 0
        
        # Find our template
        our_template = next((t for t in templates if t.template_id == template.template_id), None)
        assert our_template is not None
        assert our_template.name == template.name
        
        # List workflow instances
        workflows = await registry_service.list_workflow_instances(tenant_id="test-tenant")
        assert len(workflows) > 0
        
        # Find our workflow
        our_workflow = next((w for w in workflows if w.workflow_id == workflow.workflow_id), None)
        assert our_workflow is not None
        assert our_workflow.name == workflow.name

    @pytest.mark.asyncio
    async def test_flow_definition_retrieval(self, registry_service: RegistryService):
        """Tests retrieving flow definitions from Registry."""
        template = await create_test_registry_template(registry_service)
        
        # Get flow definition
        flow_definition = await registry_service.get_template_flow_definition(template.template_id)
        
        assert flow_definition is not None
        assert "processors" in flow_definition
        assert "connections" in flow_definition
        assert len(flow_definition["processors"]) == 2  # GenerateFlowFile + LogMessage
        assert len(flow_definition["connections"]) == 1

    @pytest.mark.asyncio
    async def test_multi_tenant_templates(self, registry_service: RegistryService):
        """Tests multi-tenant template organization."""
        # Create global template
        global_template = await registry_service.create_template(
            name=f"Global Test Template {uuid.uuid4().hex[:8]}",
            description="Global template for testing",
            flow_definition=generate_test_flow_definition(),
            scope="GLOBAL",
            created_by="test-user"
        )
        
        # Create tenant template
        tenant_template = await registry_service.create_template(
            name=f"Tenant Test Template {uuid.uuid4().hex[:8]}",
            description="Tenant template for testing",
            flow_definition=generate_test_flow_definition(),
            scope="TENANT",
            tenant_id="test-tenant",
            created_by="test-user"
        )
        
        # Verify different buckets
        assert global_template.bucket_id != tenant_template.bucket_id
        assert global_template.scope == "GLOBAL"
        assert tenant_template.scope == "TENANT"
        assert tenant_template.tenant_id == "test-tenant"
        
        # List templates by scope
        global_templates = await registry_service.list_templates(scope="GLOBAL")
        tenant_templates = await registry_service.list_templates(scope="TENANT", tenant_id="test-tenant")
        
        # Find our templates
        found_global = any(t.template_id == global_template.template_id for t in global_templates)
        found_tenant = any(t.template_id == tenant_template.template_id for t in tenant_templates)
        
        assert found_global
        assert found_tenant

    @pytest.mark.asyncio
    async def test_error_handling(self, registry_service: RegistryService):
        """Tests error handling in Registry operations."""
        # Test template not found
        with pytest.raises(Exception):
            await registry_service.get_template_flow_definition(uuid.uuid4())
        
        # Test workflow instance not found
        with pytest.raises(Exception):
            await registry_service.deploy_workflow_instance(uuid.uuid4())
        
        # Test invalid scope
        with pytest.raises(Exception):
            await registry_service.create_template(
                name="Invalid Template",
                description="Test",
                flow_definition=generate_test_flow_definition(),
                scope="TENANT",  # Missing tenant_id
                created_by="test"
            )

    @pytest.mark.asyncio
    async def test_template_usage_tracking(self, registry_service: RegistryService):
        """Tests template usage count tracking."""
        template = await create_test_registry_template(registry_service)
        initial_usage = template.usage_count
        
        # Create workflow instance (should increment usage)
        workflow = await create_test_workflow_instance(registry_service, template)
        
        # Get updated template
        updated_template = await registry_service.get_template(template.template_id)
        assert updated_template.usage_count == initial_usage + 1