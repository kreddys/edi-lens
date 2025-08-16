"""
Integration tests for NiFi Deployment Service.

These tests run against actual NiFi and NiFi Registry services in Docker Compose.
"""

import pytest
import asyncio
from datetime import datetime
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.config import settings
from src.core.auth import AuthContext
from src.models.workflow_template import WorkflowTemplate, Workflow
from src.nifi.services.deployment_service import WorkflowDeploymentService
from src.nifi.services.built_in_templates_service import BuiltInTemplatesService
from src.nifi.clients.nifi_client import NiFiAPIClient
from src.nifi.clients.registry_client import NiFiRegistryClient

pytestmark = pytest.mark.integration


class TestNiFiDeploymentIntegration:
    """Integration tests for NiFi deployment functionality."""

    @pytest.fixture
    def deployment_service(self):
        """Create deployment service with real NiFi URLs."""
        return WorkflowDeploymentService(
            nifi_url=settings.NIFI_URL,
            registry_url=settings.NIFI_REGISTRY_URL,
            nifi_auth_token=getattr(settings, 'NIFI_AUTH_TOKEN', None),
            registry_auth_token=getattr(settings, 'NIFI_REGISTRY_AUTH_TOKEN', None)
        )

    @pytest.fixture
    def built_in_service(self):
        """Create built-in templates service."""
        return BuiltInTemplatesService(
            registry_url=settings.NIFI_REGISTRY_URL,
            registry_auth_token=getattr(settings, 'NIFI_REGISTRY_AUTH_TOKEN', None)
        )

    @pytest.fixture
    def auth_context(self):
        """Create test auth context."""
        return AuthContext(
            user_id="test-user-123",
            tenant_id="tenant-a",
            roles=["workflow:read", "workflow:write", "workflow:execute"]
        )

    @pytest.fixture
    async def test_template(self):
        """Create a test template in the database."""
        async with get_db() as session:
            # Create a simple test template
            template = WorkflowTemplate(
                template_id=f"test-template-{uuid4()}",
                name="Integration Test Template",
                description="A template for integration testing",
                category="BATCH",
                scope="GLOBAL",
                tenant_id=None,
                maintainer="integration-tests",
                version="1.0",
                deployment_method="registry",
                tags=["test", "integration"],
                features=["test-feature"],
                is_featured=False,
                status="ACTIVE",
                flow_definition={
                    "processors": [
                        {
                            "id": "test-get-file",
                            "type": "GetFile",
                            "name": "Test Get File",
                            "position": {"x": 100, "y": 100},
                            "properties": {
                                "Input Directory": "${INPUT_PATH}",
                                "File Filter": "${FILE_PATTERN}",
                                "Keep Source File": "false"
                            },
                            "auto_terminated_relationships": ["failure"],
                            "scheduling": {
                                "strategy": "TIMER_DRIVEN",
                                "period": "10 sec"
                            }
                        },
                        {
                            "id": "test-log-message",
                            "type": "LogMessage",
                            "name": "Test Log Message",
                            "position": {"x": 300, "y": 100},
                            "properties": {
                                "Log Level": "INFO",
                                "Log Message": "Processing file: ${filename}"
                            },
                            "auto_terminated_relationships": ["success"]
                        }
                    ],
                    "connections": [
                        {
                            "source": "test-get-file",
                            "destination": "test-log-message",
                            "relationship": "success"
                        }
                    ],
                    "parameter_contexts": [
                        {
                            "name": "test-parameters",
                            "description": "Test parameter context",
                            "parameters": [
                                {
                                    "name": "INPUT_PATH",
                                    "description": "Input directory path",
                                    "sensitive": False
                                },
                                {
                                    "name": "FILE_PATTERN",
                                    "description": "File pattern to match",
                                    "sensitive": False,
                                    "value": "*.txt"
                                }
                            ]
                        }
                    ]
                },
                configuration_schema={
                    "type": "object",
                    "required": ["input_path"],
                    "properties": {
                        "input_path": {
                            "type": "string",
                            "title": "Input Path",
                            "description": "Directory to monitor for files"
                        },
                        "file_pattern": {
                            "type": "string",
                            "title": "File Pattern",
                            "description": "Pattern for matching files",
                            "default": "*.txt"
                        }
                    }
                }
            )
            
            session.add(template)
            await session.commit()
            await session.refresh(template)
            
            yield template
            
            # Cleanup
            await session.delete(template)
            await session.commit()

    @pytest.fixture
    async def test_workflow(self, test_template, auth_context):
        """Create a test workflow in the database."""
        async with get_db() as session:
            workflow = Workflow(
                workflow_id=uuid4(),
                name="Integration Test Workflow",
                description="A workflow for integration testing",
                template_id=test_template.template_id,
                tenant_id=auth_context.tenant_id,
                created_by=auth_context.user_id,
                status="ACTIVE",
                configuration={
                    "input_path": "/tmp/test-input",
                    "file_pattern": "*.txt"
                }
            )
            
            session.add(workflow)
            await session.commit()
            await session.refresh(workflow)
            
            yield workflow
            
            # Cleanup
            await session.delete(workflow)
            await session.commit()

    @pytest.mark.asyncio
    async def test_nifi_connectivity(self):
        """Test basic connectivity to NiFi and Registry services."""
        # Test NiFi connectivity
        async with NiFiAPIClient(settings.NIFI_URL) as nifi_client:
            health = await nifi_client.health_check()
            assert health is True, "NiFi should be accessible"
            
            # Test system diagnostics
            diagnostics = await nifi_client.get_system_diagnostics()
            assert "systemDiagnostics" in diagnostics
        
        # Test Registry connectivity
        async with NiFiRegistryClient(settings.NIFI_REGISTRY_URL) as registry_client:
            registry_info = await registry_client.get_registry_info()
            assert "buildInfo" in registry_info or "version" in registry_info

    @pytest.mark.asyncio
    async def test_template_registration_in_registry(self, test_template, built_in_service):
        """Test registering a template in actual NiFi Registry."""
        # Register template
        success = await built_in_service.register_template_in_registry(test_template)
        assert success is True, "Template registration should succeed"
        
        # Verify template exists in Registry
        async with NiFiRegistryClient(settings.NIFI_REGISTRY_URL) as registry_client:
            buckets = await registry_client.list_buckets()
            
            # Find our bucket
            test_bucket = None
            for bucket in buckets:
                if bucket["name"] == "edi-lens-templates":
                    test_bucket = bucket
                    break
            
            assert test_bucket is not None, "EDI Lens templates bucket should exist"
            
            # Check flows in bucket
            flows = await registry_client.list_flows(test_bucket["identifier"])
            template_flow = None
            for flow in flows:
                if flow["name"] == test_template.name:
                    template_flow = flow
                    break
            
            assert template_flow is not None, "Template flow should exist in Registry"
            
            # Check flow versions
            versions = await registry_client.list_flow_versions(
                test_bucket["identifier"],
                template_flow["identifier"]
            )
            assert len(versions) > 0, "Flow should have at least one version"

    @pytest.mark.asyncio
    async def test_built_in_template_seeding(self, built_in_service):
        """Test seeding built-in templates to database."""
        async with get_db() as session:
            # Get initial template count
            from sqlalchemy import func, select
            initial_count_query = select(func.count(WorkflowTemplate.template_id))
            initial_result = await session.execute(initial_count_query)
            initial_count = initial_result.scalar()
            
            # Seed built-in templates
            results = await built_in_service.seed_built_in_templates(session)
            
            # Verify results
            assert isinstance(results, dict)
            assert "seeded" in results
            assert "skipped" in results
            assert "errors" in results
            
            # Check that templates were added (or skipped if they already exist)
            total_processed = len(results["seeded"]) + len(results["skipped"])
            assert total_processed == 3, "Should process 3 built-in templates"
            
            # Verify database has more templates (if any were seeded)
            final_count_query = select(func.count(WorkflowTemplate.template_id))
            final_result = await session.execute(final_count_query)
            final_count = final_result.scalar()
            
            seeded_count = len(results["seeded"])
            assert final_count >= initial_count + seeded_count

    @pytest.mark.asyncio
    async def test_workflow_deployment_lifecycle(self, deployment_service, test_workflow, auth_context):
        """Test complete workflow deployment lifecycle."""
        workflow_id = str(test_workflow.workflow_id)
        
        try:
            # 1. Deploy workflow
            deploy_result = await deployment_service.deploy_workflow(
                None,  # We'll handle session internally
                workflow_id,
                auth_context
            )
            
            # Verify deployment succeeded
            assert deploy_result.success is True, f"Deployment should succeed: {deploy_result.error_message}"
            assert deploy_result.nifi_process_group_id is not None
            assert deploy_result.nifi_parameter_context_id is not None
            assert deploy_result.deployment_method in ["registry", "xml"]
            
            # Verify workflow was updated in database
            async with get_db() as session:
                from sqlalchemy import select
                query = select(Workflow).where(Workflow.workflow_id == test_workflow.workflow_id)
                result = await session.execute(query)
                updated_workflow = result.scalar_one()
                
                assert updated_workflow.nifi_process_group_id == deploy_result.nifi_process_group_id
                assert updated_workflow.nifi_parameter_context_id == deploy_result.nifi_parameter_context_id
                assert updated_workflow.status == "ACTIVE"
            
            # 2. Start workflow
            async with get_db() as session:
                start_result = await deployment_service.start_workflow(
                    session,
                    workflow_id,
                    auth_context
                )
                assert start_result is True, "Starting workflow should succeed"
            
            # 3. Stop workflow
            async with get_db() as session:
                stop_result = await deployment_service.stop_workflow(
                    session,
                    workflow_id,
                    auth_context
                )
                assert stop_result is True, "Stopping workflow should succeed"
            
            # 4. Undeploy workflow
            async with get_db() as session:
                undeploy_result = await deployment_service.undeploy_workflow(
                    session,
                    workflow_id,
                    auth_context
                )
                assert undeploy_result is True, "Undeploying workflow should succeed"
            
            # Verify workflow was cleaned up in database
            async with get_db() as session:
                query = select(Workflow).where(Workflow.workflow_id == test_workflow.workflow_id)
                result = await session.execute(query)
                cleaned_workflow = result.scalar_one()
                
                assert cleaned_workflow.nifi_process_group_id is None
                assert cleaned_workflow.nifi_parameter_context_id is None
                assert cleaned_workflow.status == "INACTIVE"
                
        except Exception as e:
            # Cleanup on failure
            try:
                async with get_db() as session:
                    await deployment_service.undeploy_workflow(
                        session,
                        workflow_id,
                        auth_context
                    )
            except:
                pass  # Best effort cleanup
            raise e

    @pytest.mark.asyncio
    async def test_parameter_context_creation(self, deployment_service, test_workflow):
        """Test parameter context creation in NiFi."""
        async with NiFiAPIClient(settings.NIFI_URL) as nifi_client:
            # Load template for context
            async with get_db() as session:
                from sqlalchemy import select
                template_query = select(WorkflowTemplate).where(
                    WorkflowTemplate.template_id == test_workflow.template_id
                )
                template_result = await session.execute(template_query)
                template = template_result.scalar_one()
            
            # Create parameter context
            param_context = await deployment_service._create_parameter_context(
                nifi_client,
                test_workflow,
                template
            )
            
            assert param_context is not None
            assert "component" in param_context
            assert "id" in param_context["component"]
            
            # Verify context exists in NiFi
            context_id = param_context["component"]["id"]
            retrieved_context = await nifi_client.get_parameter_context(context_id)
            
            assert retrieved_context["component"]["name"] == f"workflow-{test_workflow.workflow_id}-config"
            
            # Check parameters were created
            parameters = retrieved_context["component"]["parameters"]
            param_names = [p["parameter"]["name"] for p in parameters]
            
            assert "INPUT_PATH" in param_names
            assert "FILE_PATTERN" in param_names
            assert "TENANT_ID" in param_names
            assert "WORKFLOW_ID" in param_names

    @pytest.mark.asyncio
    async def test_xml_flow_conversion(self, deployment_service, test_template, test_workflow):
        """Test XML flow conversion functionality."""
        # Test XML conversion
        xml_flow = deployment_service._convert_json_to_nifi_xml(
            test_template.flow_definition,
            test_workflow
        )
        
        # Verify XML structure
        assert xml_flow.startswith("<template")
        assert "<processors>" in xml_flow
        assert "<processor>" in xml_flow
        assert "test-get-file" in xml_flow
        assert "GetFile" in xml_flow
        assert "${INPUT_PATH}" in xml_flow
        assert "<connections>" in xml_flow
        assert "<connection>" in xml_flow
        
        # Verify XML is well-formed
        import xml.etree.ElementTree as ET
        try:
            root = ET.fromstring(xml_flow)
            assert root.tag == "template"
        except ET.ParseError as e:
            pytest.fail(f"Generated XML is not well-formed: {e}")

    @pytest.mark.asyncio
    async def test_deployment_error_handling(self, deployment_service, auth_context):
        """Test error handling in deployment service."""
        # Test with non-existent workflow
        fake_workflow_id = str(uuid4())
        
        async with get_db() as session:
            result = await deployment_service.deploy_workflow(
                session,
                fake_workflow_id,
                auth_context
            )
            
            assert result.success is False
            assert "not found" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_workflow_restart(self, deployment_service, test_workflow, auth_context):
        """Test workflow restart functionality."""
        workflow_id = str(test_workflow.workflow_id)
        
        try:
            # First deploy the workflow
            async with get_db() as session:
                deploy_result = await deployment_service.deploy_workflow(
                    session,
                    workflow_id,
                    auth_context
                )
                assert deploy_result.success is True
            
            # Now restart it
            async with get_db() as session:
                restart_result = await deployment_service.restart_workflow(
                    session,
                    workflow_id,
                    auth_context
                )
                
                assert restart_result.success is True
                assert restart_result.nifi_process_group_id is not None
                assert restart_result.nifi_parameter_context_id is not None
                
        finally:
            # Cleanup
            try:
                async with get_db() as session:
                    await deployment_service.undeploy_workflow(
                        session,
                        workflow_id,
                        auth_context
                    )
            except:
                pass