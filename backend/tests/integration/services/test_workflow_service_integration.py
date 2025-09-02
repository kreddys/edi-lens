"""
Integration tests for WorkflowService with real NiFi and Registry.

Tests the complete WorkflowService functionality including:
- Workflow CRUD operations
- NiFi deployment from Registry to Canvas
- Workflow lifecycle management (start, stop, pause, resume)
- Workflow execution with real content processing
- Status monitoring with NiFi integration
"""

import pytest
import uuid
from uuid import UUID
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.workflow_service import WorkflowService, WorkflowServiceError
from src.services.template_service import TemplateService
from src.models.workflow_models import Workflow
from src.models.registry_models import RegistryTemplate
from src.core.auth import AuthContext
from src.api.schemas import WorkflowExecutionRequest
from src.nifi.clients.nifi_client import NiFiAPIClient
from src.core.config import settings

pytestmark = pytest.mark.integration


class TestWorkflowServiceIntegration:
    """Integration tests for WorkflowService with real NiFi and Registry."""

    @pytest.fixture(autouse=True)
    async def setup_services(self, db_session: AsyncSession):
        """Set up services for each test."""
        self.workflow_service = WorkflowService(db_session)
        self.template_service = TemplateService(db_session)
        self.session = db_session
        self.created_workflows = []
        self.created_templates = []
        self.deployed_process_groups = []
        self.deployed_parameter_contexts = []
        yield
        # Cleanup
        await self._cleanup_test_data()

    async def _cleanup_test_data(self):
        """Clean up test workflows, templates and NiFi resources."""
        try:
            # Clean up NiFi resources first
            if self.deployed_process_groups or self.deployed_parameter_contexts:
                async with NiFiAPIClient(
                    settings.NIFI_URL,
                    username=settings.NIFI_USERNAME,
                    password=settings.NIFI_PASSWORD
                ) as nifi_client:
                    # Stop and delete process groups
                    for pg_id in self.deployed_process_groups:
                        try:
                            # Stop first
                            await nifi_client.stop_process_group(pg_id)
                            # Then delete
                            await nifi_client.delete_process_group(pg_id, force=True)
                        except:
                            pass
                    
                    # Delete parameter contexts
                    for pc_id in self.deployed_parameter_contexts:
                        try:
                            await nifi_client.delete_parameter_context(pc_id)
                        except:
                            pass
            
            # Clean up database records
            for workflow in self.created_workflows:
                try:
                    await self.session.delete(workflow)
                except:
                    pass
            
            for template in self.created_templates:
                try:
                    await self.session.delete(template)
                except:
                    pass
            
            await self.session.commit()
            
        except Exception as e:
            print(f"Cleanup warning: {e}")

    def generate_test_flow_definition(self):
        """Generate a minimal test flow definition for templates."""
        return {
            "identifier": f"test-flow-{uuid.uuid4().hex[:8]}",
            "name": "Test Workflow Flow",
            "description": "Test flow for workflow integration testing", 
            "processors": [
                {
                    "identifier": str(uuid.uuid4()),
                    "name": "Generate Test Content",
                    "type": "org.apache.nifi.processors.standard.GenerateFlowFile",
                    "position": {"x": 100.0, "y": 100.0},
                    "properties": {
                        "File Size": "1KB",
                        "Batch Size": "1"
                    },
                    "schedulingStrategy": "TIMER_DRIVEN",
                    "schedulingPeriod": "60 sec",
                    "autoTerminatedRelationships": ["success"]
                }
            ],
            "processGroups": [],
            "connections": [],
            "controllerServices": [],
            "variables": {},
            "version": 1
        }

    async def create_test_template(self, name_suffix=""):
        """Create a test template for workflow testing."""
        template = await self.template_service.create_template(
            name=f"Test Workflow Template {name_suffix}",
            description="Template for workflow integration testing",
            flow_definition=self.generate_test_flow_definition(),
            scope="GLOBAL"
        )
        self.created_templates.append(template)
        return template

    @pytest.mark.asyncio
    async def test_workflow_crud_operations(self):
        """Test complete workflow CRUD operations."""
        # Create test template first
        template = await self.create_test_template("CRUD")
        
        # Create workflow
        workflow = await self.workflow_service.create_workflow(
            template_id=template.template_id,
            name="CRUD Test Workflow", 
            tenant_id="test-tenant",
            description="Testing CRUD operations",
            configuration={"test_param": "test_value"}
        )
        self.created_workflows.append(workflow)
        
        # Verify creation
        assert workflow.workflow_id is not None
        assert workflow.template_id == str(template.template_id)
        assert workflow.name == "CRUD Test Workflow"
        assert workflow.tenant_id == "test-tenant"
        assert workflow.status == "CREATED"
        assert workflow.is_deployed is False
        
        # Read workflow
        retrieved = await self.workflow_service.get_workflow(workflow.workflow_id)
        assert retrieved is not None
        assert retrieved.workflow_id == workflow.workflow_id
        assert retrieved.configuration["test_param"] == "test_value"
        
        # Update workflow
        updated = await self.workflow_service.update_workflow(
            workflow.workflow_id,
            name="Updated CRUD Workflow",
            description="Updated description",
            configuration={"test_param": "updated_value", "new_param": "new_value"}
        )
        assert updated.name == "Updated CRUD Workflow" 
        assert updated.description == "Updated description"
        assert updated.configuration["test_param"] == "updated_value"
        assert updated.configuration["new_param"] == "new_value"
        
        # List workflows
        workflows = await self.workflow_service.list_workflows(tenant_id="test-tenant")
        assert len(workflows) >= 1
        workflow_ids = [str(w.workflow_id) for w in workflows]
        assert str(workflow.workflow_id) in workflow_ids
        
        # Delete workflow
        deleted = await self.workflow_service.delete_workflow(workflow.workflow_id)
        assert deleted is True
        
        # Verify deletion
        deleted_workflow = await self.workflow_service.get_workflow(workflow.workflow_id)
        assert deleted_workflow is None

    @pytest.mark.asyncio
    async def test_workflow_deployment_lifecycle(self):
        """Test workflow deployment to NiFi Canvas from Registry."""
        # Create test template
        template = await self.create_test_template("Deploy")
        
        # Create workflow
        workflow = await self.workflow_service.create_workflow(
            template_id=template.template_id,
            name="Deploy Test Workflow",
            tenant_id="test-tenant",
            configuration={
                "batch_size": "10",
                "processing_mode": "test"
            }
        )
        self.created_workflows.append(workflow)
        
        # Deploy workflow
        deployed = await self.workflow_service.deploy_workflow(workflow.workflow_id)
        
        # Verify deployment
        assert deployed.is_deployed is True
        assert deployed.status == "ACTIVE"
        assert deployed.nifi_process_group_id is not None
        assert deployed.nifi_parameter_context_id is not None
        assert deployed.deployed_at is not None
        
        # Track for cleanup
        self.deployed_process_groups.append(deployed.nifi_process_group_id)
        self.deployed_parameter_contexts.append(deployed.nifi_parameter_context_id)
        
        # Verify NiFi process group exists
        async with NiFiAPIClient(
            settings.NIFI_URL,
            username=settings.NIFI_USERNAME,
            password=settings.NIFI_PASSWORD
        ) as nifi_client:
            # Check process group
            pg = await nifi_client.get_process_group(deployed.nifi_process_group_id)
            assert pg is not None
            assert deployed.name in pg["component"]["name"]
            
            # Check parameter context
            pc = await nifi_client.get_parameter_context(deployed.nifi_parameter_context_id)
            assert pc is not None
            # Should have parameters from configuration
            params = pc["component"]["parameters"]
            param_names = [p["parameter"]["name"] for p in params]
            assert "batch_size" in param_names or "processing_mode" in param_names
        
        # Test undeployment
        undeployed = await self.workflow_service.undeploy_workflow(workflow.workflow_id)
        
        # Verify undeployment
        assert undeployed.is_deployed is False
        assert undeployed.status == "DELETED"
        assert undeployed.nifi_process_group_id is None
        assert undeployed.nifi_parameter_context_id is None
        assert undeployed.undeployed_at is not None
        
        # Clear tracking since resources are cleaned up
        self.deployed_process_groups.clear()
        self.deployed_parameter_contexts.clear()

    @pytest.mark.asyncio
    async def test_workflow_lifecycle_control(self):
        """Test workflow lifecycle control (start, stop, pause, resume)."""
        # Create and deploy workflow
        template = await self.create_test_template("Control")
        
        workflow = await self.workflow_service.create_workflow(
            template_id=template.template_id,
            name="Control Test Workflow",
            tenant_id="test-tenant"
        )
        self.created_workflows.append(workflow)
        
        deployed = await self.workflow_service.deploy_workflow(workflow.workflow_id)
        self.deployed_process_groups.append(deployed.nifi_process_group_id)
        self.deployed_parameter_contexts.append(deployed.nifi_parameter_context_id)
        
        # Test pause (stop)
        paused = await self.workflow_service.control_workflow(workflow.workflow_id, "pause")
        assert paused.status == "PAUSED"
        
        # Test resume (start)
        resumed = await self.workflow_service.control_workflow(workflow.workflow_id, "resume")
        assert resumed.status == "ACTIVE"
        
        # Test stop
        stopped = await self.workflow_service.control_workflow(workflow.workflow_id, "stop")
        assert stopped.status == "PAUSED"
        
        # Test start
        started = await self.workflow_service.control_workflow(workflow.workflow_id, "start")
        assert started.status == "ACTIVE"
        
        # Test restart
        restarted = await self.workflow_service.control_workflow(workflow.workflow_id, "restart")
        assert restarted.status == "ACTIVE"
        
        # Clean up
        await self.workflow_service.undeploy_workflow(workflow.workflow_id)
        self.deployed_process_groups.clear()
        self.deployed_parameter_contexts.clear()

    @pytest.mark.asyncio
    async def test_workflow_execution(self):
        """Test workflow execution with content processing."""
        # Create and deploy workflow
        template = await self.create_test_template("Execution")
        
        workflow = await self.workflow_service.create_workflow(
            template_id=template.template_id,
            name="Execution Test Workflow",
            tenant_id="test-tenant",
            configuration={"processing_type": "test"}
        )
        self.created_workflows.append(workflow)
        
        deployed = await self.workflow_service.deploy_workflow(workflow.workflow_id)
        self.deployed_process_groups.append(deployed.nifi_process_group_id)
        self.deployed_parameter_contexts.append(deployed.nifi_parameter_context_id)
        
        # Create execution request
        execution_request = WorkflowExecutionRequest(
            content="Test content for processing",
            file_type="text",
            processing_options={"validate": True},
            request_id=str(uuid.uuid4())
        )
        
        auth_context = AuthContext(
            user_id="test-user",
            tenant_id="test-tenant",
            roles=["workflow:execute"]
        )
        
        # Execute workflow
        start_time = datetime.utcnow()
        result = await self.workflow_service.execute_workflow(
            str(deployed.workflow_id),
            execution_request,
            auth_context
        )
        execution_time = (datetime.utcnow() - start_time).total_seconds()
        
        # Verify execution result
        assert result.workflow_id == str(deployed.workflow_id)
        assert result.request_id == execution_request.request_id
        assert result.processing_time_ms > 0
        assert result.processed_at is not None
        assert isinstance(result.outputs, list)
        assert isinstance(result.metadata, dict)
        
        # Verify metadata indicates NiFi processing
        assert result.metadata["processing_method"] == "nifi"
        assert "workflow_id" in result.metadata
        assert "nifi_process_group_id" in result.metadata
        
        # Execution should complete reasonably quickly
        assert execution_time < 30, f"Execution took too long: {execution_time}s"
        
        print(f"✅ Workflow execution completed in {execution_time:.2f}s")
        print(f"   Result: {len(result.outputs)} outputs, {result.processing_time_ms}ms processing time")
        
        # Clean up
        await self.workflow_service.undeploy_workflow(workflow.workflow_id)
        self.deployed_process_groups.clear()
        self.deployed_parameter_contexts.clear()

    @pytest.mark.asyncio
    async def test_workflow_status_monitoring(self):
        """Test workflow status monitoring with NiFi integration."""
        # Create and deploy workflow
        template = await self.create_test_template("Status")
        
        workflow = await self.workflow_service.create_workflow(
            template_id=template.template_id,
            name="Status Test Workflow",
            tenant_id="test-tenant"
        )
        self.created_workflows.append(workflow)
        
        auth_context = AuthContext(
            user_id="test-user",
            tenant_id="test-tenant", 
            roles=["workflow:read"]
        )
        
        # Test status before deployment
        status_before = await self.workflow_service.get_workflow_status(
            str(workflow.workflow_id),
            auth_context
        )
        
        assert status_before["workflow_id"] == str(workflow.workflow_id)
        assert status_before["status"] == "CREATED"
        assert status_before["is_deployed"] is False
        assert status_before["name"] == "Status Test Workflow"
        assert status_before["created_at"] is not None
        
        # Deploy workflow
        deployed = await self.workflow_service.deploy_workflow(workflow.workflow_id)
        self.deployed_process_groups.append(deployed.nifi_process_group_id)
        self.deployed_parameter_contexts.append(deployed.nifi_parameter_context_id)
        
        # Test status after deployment
        status_after = await self.workflow_service.get_workflow_status(
            str(deployed.workflow_id),
            auth_context
        )
        
        assert status_after["status"] == "ACTIVE"
        assert status_after["is_deployed"] is True
        assert status_after["deployed_at"] is not None
        
        # Should have NiFi status information (if NiFi is accessible)
        if "nifi_status" in status_after and status_after["nifi_status"] != "UNKNOWN":
            nifi_status = status_after["nifi_status"]
            assert nifi_status in ["RUNNING", "STOPPED", "STARTING", "STOPPING"]
        
        print(f"✅ Status monitoring: {status_after['status']} (deployed: {status_after['is_deployed']})")
        
        # Clean up
        await self.workflow_service.undeploy_workflow(workflow.workflow_id)
        self.deployed_process_groups.clear()
        self.deployed_parameter_contexts.clear()

    @pytest.mark.asyncio
    async def test_multi_tenant_workflow_isolation(self):
        """Test tenant isolation for workflows."""
        template = await self.create_test_template("MultiTenant")
        
        # Create workflows for different tenants
        workflow_a = await self.workflow_service.create_workflow(
            template_id=template.template_id,
            name="Tenant A Workflow",
            tenant_id="tenant-a"
        )
        self.created_workflows.append(workflow_a)
        
        workflow_b = await self.workflow_service.create_workflow(
            template_id=template.template_id, 
            name="Tenant B Workflow",
            tenant_id="tenant-b"
        )
        self.created_workflows.append(workflow_b)
        
        # Test tenant-a can only see their workflows
        tenant_a_workflows = await self.workflow_service.list_workflows(tenant_id="tenant-a")
        tenant_a_names = [w.name for w in tenant_a_workflows]
        assert "Tenant A Workflow" in tenant_a_names
        assert "Tenant B Workflow" not in tenant_a_names
        
        # Test tenant-b can only see their workflows
        tenant_b_workflows = await self.workflow_service.list_workflows(tenant_id="tenant-b")
        tenant_b_names = [w.name for w in tenant_b_workflows]
        assert "Tenant B Workflow" in tenant_b_names
        assert "Tenant A Workflow" not in tenant_b_names

    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test error handling for various scenarios."""
        # Test creating workflow with non-existent template
        with pytest.raises(WorkflowServiceError):
            await self.workflow_service.create_workflow(
                template_id=UUID('00000000-0000-0000-0000-000000000000'),
                name="Should Fail",
                tenant_id="test-tenant"
            )
        
        # Test deploying non-existent workflow
        with pytest.raises(WorkflowServiceError):
            await self.workflow_service.deploy_workflow(UUID('00000000-0000-0000-0000-000000000000'))
        
        # Test controlling non-existent workflow
        with pytest.raises(WorkflowServiceError):
            await self.workflow_service.control_workflow(
                UUID('00000000-0000-0000-0000-000000000000'),
                "start"
            )
        
        # Test updating deployed workflow (should fail)
        if self.created_workflows:
            # Create and deploy a workflow
            template = await self.create_test_template("ErrorTest")
            workflow = await self.workflow_service.create_workflow(
                template_id=template.template_id,
                name="Error Test Workflow",
                tenant_id="test-tenant"
            )
            self.created_workflows.append(workflow)
            
            deployed = await self.workflow_service.deploy_workflow(workflow.workflow_id)
            self.deployed_process_groups.append(deployed.nifi_process_group_id)
            self.deployed_parameter_contexts.append(deployed.nifi_parameter_context_id)
            
            # Try to update deployed workflow (should fail)
            with pytest.raises(WorkflowServiceError):
                await self.workflow_service.update_workflow(
                    workflow.workflow_id,
                    name="Should Fail Update"
                )
            
            # Clean up
            await self.workflow_service.undeploy_workflow(workflow.workflow_id)
            self.deployed_process_groups.clear()
            self.deployed_parameter_contexts.clear()

    @pytest.mark.asyncio
    async def test_workflow_execution_validation(self):
        """Test workflow execution validation and error handling."""
        template = await self.create_test_template("ExecValidation")
        
        workflow = await self.workflow_service.create_workflow(
            template_id=template.template_id,
            name="Execution Validation Workflow",
            tenant_id="test-tenant"
        )
        self.created_workflows.append(workflow)
        
        execution_request = WorkflowExecutionRequest(
            content="Test content",
            file_type="text",
            processing_options={}
        )
        
        auth_context = AuthContext(
            user_id="test-user", 
            tenant_id="test-tenant",
            roles=["workflow:execute"]
        )
        
        # Test execution on non-deployed workflow (should fail)
        with pytest.raises(WorkflowServiceError):
            await self.workflow_service.execute_workflow(
                str(workflow.workflow_id),
                execution_request,
                auth_context
            )
        
        # Test execution with wrong tenant (should fail)
        deployed = await self.workflow_service.deploy_workflow(workflow.workflow_id)
        self.deployed_process_groups.append(deployed.nifi_process_group_id)
        self.deployed_parameter_contexts.append(deployed.nifi_parameter_context_id)
        
        wrong_tenant_context = AuthContext(
            user_id="test-user",
            tenant_id="wrong-tenant",
            roles=["workflow:execute"]
        )
        
        with pytest.raises(WorkflowServiceError):
            await self.workflow_service.execute_workflow(
                str(workflow.workflow_id),
                execution_request,
                wrong_tenant_context
            )
        
        # Clean up
        await self.workflow_service.undeploy_workflow(workflow.workflow_id)
        self.deployed_process_groups.clear()
        self.deployed_parameter_contexts.clear()