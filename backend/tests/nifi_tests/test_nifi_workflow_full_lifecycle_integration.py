"""
Real integration tests for NiFi workflow service with actual NiFi services.

These tests validate the complete workflow lifecycle with real NiFi and NiFi Registry,
without mocking any external services.
"""

import pytest
import asyncio
from uuid import uuid4
from sqlalchemy import select

from src.services.nifi_workflow_service import NiFiWorkflowService, NiFiWorkflowDeploymentError
from src.models.workflow_template import Workflow, WorkflowTemplate
from src.core.config import settings
from src.core.database import get_db


pytestmark = pytest.mark.integration


class TestNiFiWorkflowDeploymentIntegration:
    """Real integration tests for complete NiFi workflow deployment lifecycle."""

    async def create_test_template(self, db_session):
        """Create a test template for workflow deployment."""
        template = None
        try:
            # Create a test template
            template_id = f"test-template-{uuid4()}"
            template = WorkflowTemplate(
                template_id=template_id,
                name=f"Test Template {uuid4()}",
                category="BATCH",
                scope="TENANT",
                tenant_id="tenant-123",
                flow_definition={
                    "test": "flow",
                    "description": "Test flow definition for integration testing"
                },
                configuration_schema={
                    "type": "object",
                    "properties": {
                        "test_param": {
                            "type": "string",
                            "default": "test_value"
                        }
                    }
                }
            )
            db_session.add(template)
            await db_session.commit()
            await db_session.refresh(template)
            
            return template
            
        except Exception as e:
            # Clean up in case of failure
            try:
                if template:
                    await db_session.delete(template)
                await db_session.commit()
            except:
                pass
            
            pytest.skip(f"Failed to create test template: {str(e)}")

    async def cleanup_test_template(self, template, db_session):
        """Clean up test template."""
        try:
            if template:
                await db_session.delete(template)
                await db_session.commit()
        except:
            pass

    async def create_test_workflow(self, db_session, test_template):
        """Create a test workflow for deployment."""
        workflow = None
        try:
            # Create a test workflow
            workflow_id = uuid4()
            workflow = Workflow(
                workflow_id=workflow_id,
                tenant_id="tenant-123",
                name=f"Test Workflow {uuid4()}",
                template_id=test_template.template_id,
                configuration={
                    "test_param": "integration_test_value",
                    "processing_options": {
                        "generate_ta1": True,
                        "generate_999": False
                    }
                },
                status="ACTIVE"
            )
            db_session.add(workflow)
            await db_session.commit()
            await db_session.refresh(workflow)
            
            return workflow
            
        except Exception as e:
            # Clean up in case of failure
            try:
                if workflow:
                    await db_session.delete(workflow)
                await db_session.commit()
            except:
                pass
            
            pytest.skip(f"Failed to create test workflow: {str(e)}")

    async def cleanup_test_workflow(self, workflow, db_session):
        """Clean up test workflow."""
        try:
            if workflow:
                await db_session.delete(workflow)
                await db_session.commit()
        except:
            pass

    @pytest.mark.asyncio
    async def test_full_workflow_deployment_lifecycle(self, db_session):
        """Test complete workflow deployment lifecycle with real NiFi services."""
        # Create test template and workflow directly in the test
        template = None
        workflow = None
        
        try:
            # Create a test template
            template_id = f"test-api-template-{uuid4()}"
            template = WorkflowTemplate(
                template_id=template_id,
                name=f"Test API Template {uuid4()}",
                category="BATCH",
                scope="TENANT",
                tenant_id="tenant-a",
                flow_definition={
                    "identifier": "test-flow",
                    "name": "Test Flow",
                    "description": "Test flow definition for API integration testing",
                    "processGroups": [],
                    "processors": [],
                    "controllerServices": [],
                    "funnels": [],
                    "inputPorts": [],
                    "outputPorts": [],
                    "remoteProcessGroups": [],
                    "labels": [],
                    "variables": {},
                    "connections": [],
                    "processGroupIdentifier": "test-flow",
                    "version": 1
                },
                configuration_schema={
                    "type": "object",
                    "properties": {
                        "test_param": {
                            "type": "string",
                            "default": "test_value"
                        }
                    }
                }
            )
            db_session.add(template)
            await db_session.commit()
            await db_session.refresh(template)
            
            # Create a test workflow
            workflow_id = uuid4()
            workflow = Workflow(
                workflow_id=workflow_id,
                tenant_id="tenant-a",
                name=f"Test API Workflow {uuid4()}",
                template_id=template_id,
                configuration={
                    "test_param": "api_test_value",
                    "processing_options": {
                        "generate_ta1": True,
                        "generate_999": False
                    }
                },
                status="ACTIVE"
            )
            db_session.add(workflow)
            await db_session.commit()
            await db_session.refresh(workflow)
            
            # Skip test if NiFi services are not accessible
            try:
                # Test NiFi connectivity first
                from src.nifi.clients.nifi_client import NiFiAPIClient
                async with NiFiAPIClient(
                    nifi_url=settings.NIFI_URL,
                    username=settings.NIFI_USERNAME,
                    password=settings.NIFI_PASSWORD
                ) as nifi_client:
                    nifi_health = await nifi_client.health_check()
                    if not nifi_health:
                        pytest.skip("NiFi is not accessible")
                
                # Test NiFi Registry connectivity
                from src.nifi.clients.registry_client import NiFiRegistryClient
                async with NiFiRegistryClient(
                    registry_url=settings.NIFI_REGISTRY_URL,
                    auth_token=settings.NIFI_REGISTRY_AUTH_TOKEN
                ) as registry_client:
                    try:
                        registry_info = await registry_client.get_registry_info()
                        if not registry_info:
                            pytest.skip("NiFi Registry is not accessible")
                    except:
                        pytest.skip("NiFi Registry is not accessible")
            except Exception as e:
                pytest.skip(f"NiFi services not accessible: {str(e)}")

            service = NiFiWorkflowService(db_session)
            deployed_workflow = None
            
            try:
                # 1. Deploy workflow to NiFi
                deployed_workflow = await service.deploy_workflow(workflow)
                
                # Verify deployment was successful
                assert deployed_workflow.nifi_process_group_id is not None
                assert deployed_workflow.nifi_parameter_context_id is not None
                assert deployed_workflow.status == "ACTIVE"
                assert deployed_workflow.is_deployed is True
                
                # Verify template was updated with registry info
                template_query = select(WorkflowTemplate).where(
                    WorkflowTemplate.template_id == workflow.template_id
                )
                template_result = await db_session.execute(template_query)
                updated_template = template_result.scalar_one_or_none()
                assert updated_template.nifi_registry_flow_id is not None
                assert updated_template.nifi_registry_bucket_id is not None
                
                # 2. Get workflow status
                status = await service.get_workflow_status(deployed_workflow)
                assert status["status"] == "ACTIVE"
                assert "nifi_status" in status
                assert "health_check" in status
                
                # 3. Stop workflow
                stopped_workflow = await service.stop_workflow(deployed_workflow)
                assert stopped_workflow.status == "PAUSED"
                
                # 4. Start workflow
                started_workflow = await service.start_workflow(stopped_workflow)
                assert started_workflow.status == "ACTIVE"
                
                # 5. Get status again
                status = await service.get_workflow_status(started_workflow)
                assert status["status"] == "ACTIVE"
                
                # 6. Stop workflow again for undeployment
                stopped_workflow = await service.stop_workflow(started_workflow)
                
                # 7. Undeploy workflow
                undeployed_workflow = await service.undeploy_workflow(stopped_workflow)
                assert undeployed_workflow.nifi_process_group_id is None
                assert undeployed_workflow.nifi_parameter_context_id is None
                assert undeployed_workflow.status == "DELETED"
                assert undeployed_workflow.is_deployed is False
                
            except Exception as e:
                pytest.fail(f"Workflow deployment lifecycle test failed: {str(e)}")
            finally:
                # Clean up test data
                try:
                    if deployed_workflow and deployed_workflow.nifi_process_group_id:
                        # Make sure workflow is stopped before undeploying
                        try:
                            await service.stop_workflow(deployed_workflow)
                        except:
                            pass  # Ignore errors in stop
                        
                        # Attempt to undeploy
                        try:
                            await service.undeploy_workflow(deployed_workflow)
                        except:
                            pass  # Ignore cleanup errors
                except:
                    pass
        
        finally:
            # Clean up test data
            try:
                if workflow:
                    await db_session.delete(workflow)
                if template:
                    await db_session.delete(template)
                await db_session.commit()
            except:
                pass

    @pytest.mark.asyncio
    async def test_workflow_deployment_error_handling(self, db_session):
        """Test error handling during workflow deployment."""
        

    @pytest.mark.asyncio
    async def test_undeploy_non_deployed_workflow(self, db_session):
        """Test undeploying a workflow that hasn't been deployed."""
        # Create test template and workflow directly in the test
        template = None
        workflow = None
        
        try:
            # Create a test template
            template_id = f"test-api-template-{uuid4()}"
            template = WorkflowTemplate(
                template_id=template_id,
                name=f"Test API Template {uuid4()}",
                category="BATCH",
                scope="TENANT",
                tenant_id="tenant-a",
                flow_definition={
                    "identifier": "test-flow",
                    "name": "Test Flow",
                    "description": "Test flow definition for API integration testing",
                    "processGroups": [],
                    "processors": [],
                    "controllerServices": [],
                    "funnels": [],
                    "inputPorts": [],
                    "outputPorts": [],
                    "remoteProcessGroups": [],
                    "labels": [],
                    "variables": {},
                    "connections": [],
                    "processGroupIdentifier": "test-flow",
                    "version": 1
                },
                configuration_schema={
                    "type": "object",
                    "properties": {
                        "test_param": {
                            "type": "string",
                            "default": "test_value"
                        }
                    }
                }
            )
            db_session.add(template)
            await db_session.commit()
            await db_session.refresh(template)
            
            # Create a test workflow
            workflow_id = uuid4()
            workflow = Workflow(
                workflow_id=workflow_id,
                tenant_id="tenant-a",
                name=f"Test API Workflow {uuid4()}",
                template_id=template_id,
                configuration={
                    "test_param": "api_test_value",
                    "processing_options": {
                        "generate_ta1": True,
                        "generate_999": False
                    }
                },
                status="ACTIVE"
            )
            db_session.add(workflow)
            await db_session.commit()
            await db_session.refresh(workflow)
            
            # Skip test if NiFi services are not accessible
            try:
                # Test NiFi connectivity first
                from src.nifi.clients.nifi_client import NiFiAPIClient
                async with NiFiAPIClient(
                    nifi_url=settings.NIFI_URL,
                    username=settings.NIFI_USERNAME,
                    password=settings.NIFI_PASSWORD
                ) as nifi_client:
                    nifi_health = await nifi_client.health_check()
                    if not nifi_health:
                        pytest.skip("NiFi is not accessible")
            except Exception as e:
                pytest.skip(f"NiFi service not accessible: {str(e)}")

            service = NiFiWorkflowService(db_session)
            
            try:
                # Try to undeploy a workflow that hasn't been deployed
                # This should raise a ValueError wrapped in NiFiWorkflowDeploymentError
                with pytest.raises(NiFiWorkflowDeploymentError, match="Workflow is not deployed to NiFi"):
                    await service.undeploy_workflow(workflow)
                    
            except Exception as e:
                pytest.fail(f"Undeploy error handling test failed: {str(e)}")
        
        finally:
            # Clean up test data
            try:
                if workflow:
                    await db_session.delete(workflow)
                if template:
                    await db_session.delete(template)
                await db_session.commit()
            except:
                pass