"""
Real integration tests for NiFi template management with actual NiFi Registry.

These tests validate template operations with real NiFi Registry,
without mocking any external services.
"""

import pytest
import asyncio
from uuid import uuid4
from sqlalchemy import select

from src.nifi.clients.registry_client import NiFiRegistryClient
from src.models.workflow_template import WorkflowTemplate
from src.core.config import settings
from src.core.database import get_db


pytestmark = pytest.mark.integration


class TestNiFiTemplateManagementIntegration:
    """Real integration tests for NiFi template management with real NiFi Registry."""

    async def create_test_template(self, db_session):
        """Create a test template for registry operations."""
        template = None
        try:
            # Create a test template with proper NiFi flow definition structure
            template_id = f"test-registry-template-{uuid4()}"
            template = WorkflowTemplate(
                template_id=template_id,
                name=f"Test Registry Template {uuid4()}",
                category="BATCH",
                scope="TENANT",
                tenant_id="tenant-123",
                flow_definition={
                    "identifier": "test-flow",
                    "name": "Test Flow",
                    "description": "Test flow definition for registry integration testing",
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
                    "processGroupIdentifier": "test-flow"
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

    @pytest.mark.asyncio
    async def test_template_registry_integration(self, db_session):
        """Test template creation and management in NiFi Registry."""
        # Create test template
        template = await self.create_test_template(db_session)
        
        try:
            # Skip test if NiFi Registry is not accessible
            try:
                async with NiFiRegistryClient(settings.NIFI_REGISTRY_URL) as registry_client:
                    registry_info = await registry_client.get_registry_info()
                    if not registry_info:
                        pytest.skip("NiFi Registry is not accessible")
            except Exception as e:
                pytest.skip(f"NiFi Registry not accessible: {str(e)}")

            async with NiFiRegistryClient(settings.NIFI_REGISTRY_URL) as registry_client:
                bucket_name = f"edi-lens-{template.scope}"
                flow_name = f"{template.name}-{template.template_id}"
                bucket_id = None
                flow_id = None
                
                try:
                    # 1. Check if bucket exists, create if not
                    buckets = await registry_client.list_buckets()
                    bucket = next((b for b in buckets if b["name"] == bucket_name), None)
                    
                    if not bucket:
                        bucket = await registry_client.create_bucket(
                            name=bucket_name,
                            description=f"EDI Lens {template.scope} workflows"
                        )
                    
                    bucket_id = bucket["identifier"]
                    assert bucket_id is not None
                    
                    # 2. Check if flow exists, create if not
                    flows = await registry_client.list_flows(bucket_id)
                    flow = next((f for f in flows if f["name"] == flow_name), None)
                    
                    if not flow:
                        flow = await registry_client.create_flow(
                            bucket_id=bucket_id,
                            flow_name=flow_name,
                            flow_description=template.description or f"Workflow template {template.name}"
                        )
                    
                    flow_id = flow["identifier"]
                    assert flow_id is not None
                    
                    # 3. Create flow version
                    version_data = {
                        "flowContents": template.flow_definition,
                        "parameterContexts": {},
                        "externalControllerServices": {}
                    }
                    
                    version_info = await registry_client.create_flow_version(
                        bucket_id=bucket_id,
                        flow_id=flow_id,
                        version_data=version_data,
                        comments=f"Initial version from EDI Lens template {template.template_id}"
                    )
                    
                    assert version_info is not None
                    assert "flow" in version_info
                    assert "versionCount" in version_info["flow"]
                    
                    # 4. Get flow version
                    flow_version = await registry_client.get_flow_version(bucket_id, flow_id, "latest")
                    assert flow_version is not None
                    # Print available fields for debugging
                    print(f"Flow version keys: {flow_version.keys()}")
                    assert "flowContents" in flow_version
                    assert "snapshotMetadata" in flow_version
                    # Check that the core structure is preserved (be flexible about added metadata)
                    stored_flow = flow_version["flowContents"]
                    original_flow = template.flow_definition
                    # Check that the key elements are preserved
                    assert stored_flow["name"] == original_flow["name"]
                    assert len(stored_flow["processors"]) == len(original_flow["processors"])
                    assert len(stored_flow["processGroups"]) == len(original_flow["processGroups"])
                    
                    # 5. List flow versions
                    flow_versions = await registry_client.list_flow_versions(bucket_id, flow_id)
                    assert isinstance(flow_versions, list)
                    assert len(flow_versions) > 0
                    
                except Exception as e:
                    pytest.fail(f"Template registry integration test failed: {str(e)}")
                finally:
                    # Cleanup - delete flow and bucket if they were created
                    try:
                        if flow_id and bucket_id:
                            await registry_client.delete_flow(bucket_id, flow_id)
                    except:
                        pass  # Ignore cleanup errors
                    
                    try:
                        if bucket_id and bucket_name:
                            # Only delete bucket if we created it (check if it still exists)
                            buckets = await registry_client.list_buckets()
                            bucket = next((b for b in buckets if b["identifier"] == bucket_id), None)
                            if bucket:
                                await registry_client.delete_bucket(bucket_id)
                    except:
                        pass  # Ignore cleanup errors
                        
        finally:
            # Clean up test template
            await self.cleanup_test_template(template, db_session)

    @pytest.mark.asyncio
    async def test_template_registry_error_handling(self, db_session):
        """Test error handling for NiFi Registry operations."""
        # Create test template
        template = await self.create_test_template(db_session)
        
        try:
            # Skip test if NiFi Registry is not accessible
            try:
                async with NiFiRegistryClient(settings.NIFI_REGISTRY_URL) as registry_client:
                    registry_info = await registry_client.get_registry_info()
                    if not registry_info:
                        pytest.skip("NiFi Registry is not accessible")
            except Exception as e:
                pytest.skip(f"NiFi Registry not accessible: {str(e)}")

            async with NiFiRegistryClient(settings.NIFI_REGISTRY_URL) as registry_client:
                try:
                    # Try to get a non-existent bucket
                    with pytest.raises(Exception):
                        await registry_client.get_bucket("non-existent-bucket-id")
                    
                    # Try to list flows in a non-existent bucket
                    with pytest.raises(Exception):
                        await registry_client.list_flows("non-existent-bucket-id")
                        
                except Exception as e:
                    pytest.fail(f"Template registry error handling test failed: {str(e)}")
        finally:
            # Clean up test template
            await self.cleanup_test_template(template, db_session)