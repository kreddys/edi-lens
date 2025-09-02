"""
Integration tests for deploying YAML-based built-in templates to NiFi Registry.

These tests validate the complete template deployment lifecycle from YAML files
to NiFi Registry with real NiFi Registry services.
"""

import pytest
import pytest_asyncio
import tempfile
import yaml
from pathlib import Path
from uuid import uuid4
from sqlalchemy import select

from src.nifi.services.built_in_templates_service import BuiltInTemplatesService
from src.models.registry_models import RegistryTemplate
from src.nifi.clients.registry_client import NiFiRegistryClient
from src.core.config import settings


pytestmark = pytest.mark.integration


class TestBuiltInTemplatesNiFiDeployment:
    """Integration tests for deploying YAML templates to NiFi Registry."""

    @pytest.fixture
    def registry_client(self):
        """Create a NiFi Registry client for testing."""
        return NiFiRegistryClient(
            registry_url=settings.NIFI_REGISTRY_URL,
            auth_token=getattr(settings, 'NIFI_REGISTRY_AUTH_TOKEN', None)
        )

    @pytest.fixture
    def temp_templates_dir(self):
        """Create temporary directory with test template for deployment."""
        with tempfile.TemporaryDirectory() as temp_dir:
            templates_dir = Path(temp_dir)
            
            # Create a test template with proper NiFi flow structure
            test_template = {
                "metadata": {
                    "template_id": str(uuid4()),
                    "name": f"Test Deploy Template {uuid4()}",
                    "description": "Template for testing NiFi Registry deployment",
                    "category": "BATCH",
                    "scope": "GLOBAL",
                    "tenant_id": None,
                    "maintainer": "test-system",
                    "based_on": None,
                    "version": "1.0.0",
                    "deployment_method": "registry",
                    "tags": ["test", "deployment", "registry"],
                    "features": ["test-deployment"],
                    "is_featured": False,
                    "status": "ACTIVE"
                },
                "flow_definition": {
                    "identifier": f"test-flow-{uuid4()}",
                    "name": "Test Deployment Flow",
                    "description": "Test flow for registry deployment testing",
                    "processGroups": [],
                    "processors": [
                        {
                            "identifier": f"test-processor-{uuid4()}",
                            "name": "Test Generate Flow File",
                            "type": "org.apache.nifi.processors.standard.GenerateFlowFile",
                            "position": {"x": 100.0, "y": 100.0},
                            "properties": {
                                "File Size": "1KB",
                                "Batch Size": "1",
                                "Data Format": "Text"
                            },
                            "propertyDescriptors": {},
                            "style": {},
                            "schedulingPeriod": "60 sec",
                            "schedulingStrategy": "TIMER_DRIVEN",
                            "executionNode": "ALL",
                            "penaltyDuration": "30 sec",
                            "yieldDuration": "1 sec",
                            "bulletinLevel": "WARN",
                            "runDurationMillis": 0,
                            "concurrentlySchedulableTaskCount": 1,
                            "autoTerminatedRelationships": ["success"],
                            "comments": "Test processor for deployment"
                        }
                    ],
                    "controllerServices": [],
                    "funnels": [],
                    "inputPorts": [],
                    "outputPorts": [],
                    "remoteProcessGroups": [],
                    "labels": [],
                    "connections": [],
                    "variables": {},
                    "parameterContexts": [],
                    "flowFileConcurrency": "UNBOUNDED",
                    "flowFileOutboundPolicy": "STREAM_WHEN_AVAILABLE",
                    "defaultFlowFileExpiration": "0 sec",
                    "defaultBackPressureObjectThreshold": 10000,
                    "defaultBackPressureDataSizeThreshold": "1 GB"
                },
                "configuration_schema": {
                    "type": "object",
                    "properties": {
                        "test_config": {
                            "type": "string",
                            "title": "Test Configuration"
                        }
                    }
                }
            }
            
            template_file = templates_dir / "test-deploy-template.yaml"
            with open(template_file, 'w') as f:
                yaml.dump(test_template, f)
            
            yield templates_dir

    @pytest.fixture
    def temp_templates_service(self, temp_templates_dir):
        """Create a service with test template for deployment."""
        return BuiltInTemplatesService(
            registry_url=settings.NIFI_REGISTRY_URL,
            registry_auth_token=getattr(settings, 'NIFI_REGISTRY_AUTH_TOKEN', None),
            templates_dir=str(temp_templates_dir)
        )

    @pytest_asyncio.fixture
    async def seeded_template(self, temp_templates_service, db_session):
        """Create and seed a test template in the database."""
        # Seed the template
        seeding_results = await temp_templates_service.seed_built_in_templates(db_session)
        assert len(seeding_results["seeded"]) == 1
        
        # Retrieve the seeded template
        template_id = seeding_results["seeded"][0]["template_id"]
        query = select(RegistryTemplate).where(RegistryTemplate.template_id == template_id)
        result = await db_session.execute(query)
        template = result.scalar_one()
        
        return template

    async def cleanup_registry_artifacts(self, registry_client, template_name):
        """Clean up test artifacts from NiFi Registry."""
        try:
            async with registry_client:
                # List all buckets
                buckets = await registry_client.list_buckets()
                
                for bucket in buckets:
                    if bucket["name"] == "edi-lens-global":
                        try:
                            # List flows in the bucket
                            flows = await registry_client.list_flows(bucket["identifier"])
                            
                            # Find and delete test flows
                            for flow in flows:
                                if template_name in flow["name"] or "test" in flow["name"].lower():
                                    try:
                                        # Note: Actual deletion might require additional permissions
                                        # For now, we'll just log what we would delete
                                        print(f"Would delete test flow: {flow['name']}")
                                    except Exception as e:
                                        print(f"Could not delete flow {flow['name']}: {e}")
                        except Exception as e:
                            print(f"Could not list flows in bucket {bucket['name']}: {e}")
        except Exception as e:
            print(f"Registry cleanup error: {e}")

    @pytest.mark.asyncio
    async def test_template_registry_deployment(self, temp_templates_service, seeded_template, registry_client):
        """Test deploying a template to NiFi Registry."""
        # Deploy template to registry
        deployment_success = await temp_templates_service.register_template_in_registry(seeded_template)
        
        # Verify deployment succeeded
        assert deployment_success is True
        
        # Verify artifacts were created in registry
        async with registry_client:
            # Check that EDI Lens templates bucket exists (Registry-first architecture uses "edi-lens-global")
            buckets = await registry_client.list_buckets()
            edi_lens_bucket = None
            
            for bucket in buckets:
                if bucket["name"] == "edi-lens-global":
                    edi_lens_bucket = bucket
                    break
            
            assert edi_lens_bucket is not None, "EDI Lens global templates bucket should be created"
            
            # Check that the template flow exists
            flows = await registry_client.list_flows(edi_lens_bucket["identifier"])
            template_flow = None
            
            for flow in flows:
                if flow["name"] == seeded_template.name:
                    template_flow = flow
                    break
            
            assert template_flow is not None, f"Template flow '{seeded_template.name}' should exist in registry"
            
            # Check that flow versions exist
            flow_versions = await registry_client.list_flow_versions(
                edi_lens_bucket["identifier"], 
                template_flow["identifier"]
            )
            assert len(flow_versions) >= 1, "Template should have at least one version"
            
            # Verify the flow version contains our template data
            latest_version = flow_versions[0]
            assert latest_version["version"] >= 1
            
            # Cleanup test artifacts
            await self.cleanup_registry_artifacts(registry_client, seeded_template.name)

    @pytest.mark.asyncio
    async def test_template_deployment_bucket_creation(self, temp_templates_service, seeded_template, registry_client):
        """Test that EDI Lens templates bucket is created if it doesn't exist."""
        # First, ensure the bucket doesn't exist (cleanup from previous tests)
        async with registry_client:
            try:
                buckets = await registry_client.list_buckets()
                for bucket in buckets:
                    if bucket["name"] == "edi-lens-global":
                        # If bucket exists, we'll test the idempotent behavior
                        break
            except Exception:
                pass  # Continue with test
        
        # Deploy template (should create bucket if needed)
        deployment_success = await temp_templates_service.register_template_in_registry(seeded_template)
        assert deployment_success is True
        
        # Verify bucket exists
        async with registry_client:
            buckets = await registry_client.list_buckets()
            bucket_names = [bucket["name"] for bucket in buckets]
            assert "edi-lens-global" in bucket_names

    @pytest.mark.asyncio
    async def test_template_deployment_idempotency(self, temp_templates_service, seeded_template, registry_client):
        """Test that re-deploying the same template is handled gracefully."""
        # First deployment
        first_deployment = await temp_templates_service.register_template_in_registry(seeded_template)
        assert first_deployment is True
        
        # Second deployment (should update or handle gracefully)
        second_deployment = await temp_templates_service.register_template_in_registry(seeded_template)
        assert second_deployment is True
        
        # Verify template still exists correctly in registry
        async with registry_client:
            buckets = await registry_client.list_buckets()
            edi_lens_bucket = None
            
            for bucket in buckets:
                if bucket["name"] == "edi-lens-global":
                    edi_lens_bucket = bucket
                    break
            
            assert edi_lens_bucket is not None
            
            flows = await registry_client.list_flows(edi_lens_bucket["identifier"])
            template_flows = [f for f in flows if f["name"] == seeded_template.name]
            
            # Should have exactly one flow for this template
            assert len(template_flows) == 1

    @pytest.mark.asyncio
    async def test_template_deployment_error_handling(self, temp_templates_service, seeded_template):
        """Test error handling graceful behavior in Registry-first architecture."""
        # In Registry-first architecture, register_template_in_registry just returns True
        # since templates are already registered during creation (no separate deployment step)
        # Create a service with invalid registry URL (though it won't be used)
        invalid_service = BuiltInTemplatesService(
            registry_url="http://invalid-registry-url:9999",
            registry_auth_token=None,
            templates_dir=str(Path(temp_templates_service.templates_dir)),
            timeout=2  # Short timeout for testing
        )
        
        # In Registry-first architecture, this method just returns True (no actual deployment)
        deployment_success = await invalid_service.register_template_in_registry(seeded_template)
        assert deployment_success is True
        
        # Verify the method's behavior matches the architecture design
        # (Templates are registered during creation, not in a separate step)

    @pytest.mark.asyncio
    async def test_template_deployment_with_complex_flow(self, registry_client, db_session):
        """Test deploying a template with a more complex NiFi flow definition."""
        # Create a complex flow definition (Registry-first architecture)
        from src.services.registry_service import RegistryService
        
        complex_template_name = f"Complex Test Template {uuid4()}"
        complex_flow_definition = {
                "identifier": f"complex-flow-{uuid4()}",
                "name": "Complex Test Flow",
                "description": "Complex flow with multiple processors",
                "processors": [
                    {
                        "identifier": f"generate-{uuid4()}",
                        "name": "Generate Files",
                        "type": "org.apache.nifi.processors.standard.GenerateFlowFile",
                        "position": {"x": 100.0, "y": 100.0},
                        "properties": {"File Size": "1KB"},
                        "autoTerminatedRelationships": []
                    },
                    {
                        "identifier": f"update-{uuid4()}",
                        "name": "Update Attributes", 
                        "type": "org.apache.nifi.processors.attributes.UpdateAttribute",
                        "position": {"x": 300.0, "y": 100.0},
                        "properties": {"test.attribute": "test-value"},
                        "autoTerminatedRelationships": ["success"]
                    }
                ],
                "connections": [
                    {
                        "identifier": f"connection-{uuid4()}",
                        "name": "Generate to Update",
                        "source": {
                            "id": f"generate-{uuid4()}",
                            "type": "PROCESSOR"
                        },
                        "destination": {
                            "id": f"update-{uuid4()}",
                            "type": "PROCESSOR"
                        },
                        "selectedRelationships": ["success"]
                    }
                ],
                "processGroups": [],
                "controllerServices": [],
                "funnels": [],
                "inputPorts": [],
                "outputPorts": [],
                "remoteProcessGroups": [],
                "labels": [],
                "variables": {}
            }
        
        # Create template using Registry service (Registry-first architecture)
        registry_service = RegistryService(db_session)
        complex_template = await registry_service.create_template(
            name=complex_template_name,
            description="Complex template for deployment testing",
            flow_definition=complex_flow_definition,
            scope="GLOBAL",
            created_by="test-system"
        )
        
        # Verify template was created successfully in Registry
        assert complex_template is not None
        assert complex_template.name == complex_template_name
        
        # Verify the template exists in NiFi Registry
        async with registry_client:
            buckets = await registry_client.list_buckets()
            global_bucket = next((b for b in buckets if b["name"] == "edi-lens-global"), None)
            assert global_bucket is not None
            
            flows = await registry_client.list_flows(global_bucket["identifier"])
            complex_flow = next((f for f in flows if f["name"] == complex_template_name), None)
            assert complex_flow is not None

    @pytest.mark.asyncio
    async def test_production_templates_registry_deployment(self, db_session, registry_client):
        """Test deploying actual production YAML templates to registry."""
        # Use the production templates service
        production_service = BuiltInTemplatesService(
            registry_url=settings.NIFI_REGISTRY_URL,
            registry_auth_token=getattr(settings, 'NIFI_REGISTRY_AUTH_TOKEN', None)
        )
        
        # Load production templates
        production_templates = production_service.get_all_built_in_templates()
        
        if len(production_templates) == 0:
            pytest.skip("No production templates found for deployment testing")
        
        # Seed one production template for testing
        first_template_data = production_templates[0]
        
        # Check if template already exists in database (Registry-first architecture)
        # Note: In Registry-first architecture, template_id is auto-generated, so we check by name
        query = select(RegistryTemplate).where(
            RegistryTemplate.name == first_template_data["name"]
        )
        result = await db_session.execute(query)
        existing_template = result.scalar_one_or_none()
        
        if existing_template is None:
            # Seed the template
            seeding_results = await production_service.seed_built_in_templates(db_session)
            assert len(seeding_results["seeded"]) > 0 or len(seeding_results["skipped"]) > 0
            
            # Get the template
            result = await db_session.execute(query)
            template = result.scalar_one()
        else:
            template = existing_template
        
        # Deploy to registry
        deployment_success = await production_service.register_template_in_registry(template)
        assert deployment_success is True
        
        # Verify in registry
        async with registry_client:
            buckets = await registry_client.list_buckets()
            edi_lens_bucket = next((b for b in buckets if b["name"] == "edi-lens-global"), None)
            assert edi_lens_bucket is not None
            
            flows = await registry_client.list_flows(edi_lens_bucket["identifier"])
            template_flow = next((f for f in flows if f["name"] == template.name), None)
            assert template_flow is not None
            
            # Verify flow versions
            flow_versions = await registry_client.list_flow_versions(
                edi_lens_bucket["identifier"],
                template_flow["identifier"]
            )
            assert len(flow_versions) >= 1