"""
Integration tests for TemplateService with real NiFi Registry.

Tests the complete TemplateService functionality including:
- Template CRUD operations with Registry integration
- Built-in template seeding from YAML files
- Registry bucket management
- Cross-tenant template access
"""

import pytest
import uuid
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.services.template_service import TemplateService, TemplateServiceError
from src.models.registry_models import RegistryTemplate, RegistryBucket
from src.nifi.clients.registry_client import NiFiRegistryClient
from src.core.config import settings

pytestmark = pytest.mark.integration


class TestTemplateServiceIntegration:
    """Integration tests for TemplateService with real NiFi Registry."""

    @pytest.fixture(autouse=True)
    async def setup_service(self, db_session: AsyncSession):
        """Set up TemplateService for each test."""
        self.service = TemplateService(db_session)
        self.session = db_session
        self.created_templates = []
        self.created_buckets = []
        yield
        # Cleanup
        await self._cleanup_test_data()

    async def _cleanup_test_data(self):
        """Clean up test templates and buckets."""
        try:
            # Clean up templates from database
            for template in self.created_templates:
                try:
                    await self.session.delete(template)
                except:
                    pass
            
            # Clean up buckets from database  
            for bucket in self.created_buckets:
                try:
                    await self.session.delete(bucket)
                except:
                    pass
            
            await self.session.commit()
            
            # Clean up from NiFi Registry
            async with NiFiRegistryClient(
                settings.NIFI_REGISTRY_URL,
                settings.NIFI_REGISTRY_AUTH_TOKEN
            ) as registry_client:
                try:
                    buckets = await registry_client.get_buckets()
                    for bucket in buckets:
                        if bucket["name"].startswith("test-"):
                            # Delete flows in bucket first
                            flows = await registry_client.get_flows(bucket["identifier"])
                            for flow in flows:
                                try:
                                    await registry_client.delete_flow(bucket["identifier"], flow["identifier"])
                                except:
                                    pass
                            # Delete bucket
                            try:
                                await registry_client.delete_bucket(bucket["identifier"])
                            except:
                                pass
                except:
                    pass
        except Exception as e:
            print(f"Cleanup warning: {e}")

    def generate_test_flow_definition(self):
        """Generate a minimal test flow definition."""
        return {
            "identifier": f"test-flow-{uuid.uuid4().hex[:8]}",
            "name": "Test Flow",
            "description": "Test flow for integration testing",
            "processors": [
                {
                    "identifier": str(uuid.uuid4()),
                    "name": "Generate Test Data",
                    "type": "org.apache.nifi.processors.standard.GenerateFlowFile",
                    "position": {"x": 100.0, "y": 100.0},
                    "properties": {"File Size": "1KB"},
                    "autoTerminatedRelationships": ["success"]
                }
            ],
            "processGroups": [],
            "connections": [],
            "controllerServices": [],
            "variables": {},
            "version": 1
        }

    @pytest.mark.asyncio
    async def test_create_template_with_registry_integration(self):
        """Test template creation with real NiFi Registry integration."""
        template_name = f"Test Template {uuid.uuid4().hex[:8]}"
        flow_definition = self.generate_test_flow_definition()
        
        # Create template
        template = await self.service.create_template(
            name=template_name,
            description="Integration test template",
            flow_definition=flow_definition,
            scope="TENANT", 
            tenant_id="test-tenant",
            category="TEST",
            version="1.0.0"
        )
        
        self.created_templates.append(template)
        
        # Verify database record
        assert template.template_id is not None
        assert template.name == template_name
        assert template.scope == "TENANT"
        assert template.tenant_id == "test-tenant"
        assert template.status == "ACTIVE"
        assert template.bucket_id is not None
        assert template.registry_flow_id is not None
        
        # Verify Registry integration
        async with NiFiRegistryClient(
            settings.NIFI_REGISTRY_URL,
            settings.NIFI_REGISTRY_AUTH_TOKEN
        ) as registry_client:
            # Check bucket exists
            bucket = await registry_client.get_bucket(str(template.bucket_id))
            assert bucket is not None
            assert "test-tenant" in bucket["name"]
            
            # Check flow exists
            flow = await registry_client.get_flow(str(template.bucket_id), str(template.registry_flow_id))
            assert flow is not None
            assert flow["name"] == template_name
            
            # Check flow version exists
            versions = await registry_client.get_flow_versions(str(template.bucket_id), str(template.registry_flow_id))
            assert len(versions) >= 1
            assert versions[0]["version"] == 1

    @pytest.mark.asyncio
    async def test_template_crud_operations(self):
        """Test complete template CRUD operations."""
        # Create
        template = await self.service.create_template(
            name="CRUD Test Template",
            description="Testing CRUD operations",
            flow_definition=self.generate_test_flow_definition(),
            scope="GLOBAL"
        )
        self.created_templates.append(template)
        
        # Read
        retrieved = await self.service.get_template(template.template_id)
        assert retrieved is not None
        assert retrieved.template_id == template.template_id
        assert retrieved.name == "CRUD Test Template"
        
        # Update
        updated = await self.service.update_template(
            template.template_id,
            name="Updated CRUD Template",
            description="Updated description"
        )
        assert updated.name == "Updated CRUD Template"
        assert updated.description == "Updated description"
        
        # List
        templates = await self.service.list_templates(limit=10)
        assert len(templates) >= 1
        template_ids = [str(t.template_id) for t in templates]
        assert str(template.template_id) in template_ids
        
        # Delete (soft)
        deleted = await self.service.delete_template(template.template_id)
        assert deleted is True
        
        # Verify soft delete
        deleted_template = await self.service.get_template(template.template_id)
        assert deleted_template.status == "INACTIVE"

    @pytest.mark.asyncio
    async def test_template_versioning(self):
        """Test template version management with Registry."""
        # Create initial template
        template = await self.service.create_template(
            name="Version Test Template", 
            description="Testing versioning",
            flow_definition=self.generate_test_flow_definition(),
            scope="GLOBAL",
            version="1.0.0"
        )
        self.created_templates.append(template)
        
        # Update with new version
        new_flow_def = self.generate_test_flow_definition()
        updated = await self.service.update_template(
            template.template_id,
            flow_definition=new_flow_def,
            version="1.1.0"
        )
        
        assert updated.current_version == "1.1.0"
        
        # Verify versions in Registry
        async with NiFiRegistryClient(
            settings.NIFI_REGISTRY_URL,
            settings.NIFI_REGISTRY_AUTH_TOKEN
        ) as registry_client:
            versions = await registry_client.get_flow_versions(
                str(template.bucket_id), 
                str(template.registry_flow_id)
            )
            assert len(versions) >= 2
            version_nums = [v["version"] for v in versions]
            assert 1 in version_nums
            assert 2 in version_nums  # Registry uses sequential numbering

    @pytest.mark.asyncio
    async def test_built_in_template_seeding(self):
        """Test seeding built-in templates from YAML files."""
        # Note: This test assumes built-in template YAML files exist
        try:
            results = await self.service.seed_templates()
            
            # Verify results structure
            assert "seeded" in results
            assert "skipped" in results  
            assert "errors" in results
            assert isinstance(results["seeded"], list)
            assert isinstance(results["skipped"], list)
            assert isinstance(results["errors"], list)
            
            # If templates were seeded, verify they exist in database
            if len(results["seeded"]) > 0:
                seeded_template = results["seeded"][0]
                template_id = UUID(seeded_template["template_id"])
                
                template = await self.service.get_template(template_id)
                assert template is not None
                assert template.status == "ACTIVE"
                self.created_templates.append(template)
                
                # Verify in Registry
                async with NiFiRegistryClient(
                    settings.NIFI_REGISTRY_URL,
                    settings.NIFI_REGISTRY_AUTH_TOKEN
                ) as registry_client:
                    flow = await registry_client.get_flow(
                        str(template.bucket_id), 
                        str(template.registry_flow_id)
                    )
                    assert flow is not None
                    
        except FileNotFoundError:
            # Skip if no built-in templates directory exists
            pytest.skip("No built-in templates directory found")

    @pytest.mark.asyncio
    async def test_cross_tenant_template_access(self):
        """Test tenant isolation and global template access."""
        # Create global template
        global_template = await self.service.create_template(
            name="Global Test Template",
            description="Global scope template",
            flow_definition=self.generate_test_flow_definition(),
            scope="GLOBAL"
        )
        self.created_templates.append(global_template)
        
        # Create tenant-specific template
        tenant_template = await self.service.create_template(
            name="Tenant Test Template", 
            description="Tenant scope template",
            flow_definition=self.generate_test_flow_definition(),
            scope="TENANT",
            tenant_id="tenant-a"
        )
        self.created_templates.append(tenant_template)
        
        # Test tenant-a can see both global and tenant templates
        tenant_a_templates = await self.service.list_templates(tenant_id="tenant-a")
        template_names = [t.name for t in tenant_a_templates]
        assert "Global Test Template" in template_names
        assert "Tenant Test Template" in template_names
        
        # Test tenant-b can only see global templates
        tenant_b_templates = await self.service.list_templates(tenant_id="tenant-b")
        template_names_b = [t.name for t in tenant_b_templates]
        assert "Global Test Template" in template_names_b
        assert "Tenant Test Template" not in template_names_b

    @pytest.mark.asyncio
    async def test_bucket_management(self):
        """Test automatic Registry bucket creation and management."""
        # Create template for new tenant (should create bucket)
        template = await self.service.create_template(
            name="Bucket Test Template",
            description="Testing bucket creation",
            flow_definition=self.generate_test_flow_definition(),
            scope="TENANT",
            tenant_id="new-test-tenant"
        )
        self.created_templates.append(template)
        
        # Verify bucket was created
        bucket_query = select(RegistryBucket).where(RegistryBucket.bucket_id == template.bucket_id)
        result = await self.session.execute(bucket_query)
        bucket = result.scalar_one_or_none()
        
        assert bucket is not None
        assert "new-test-tenant" in bucket.name
        assert bucket.tenant_id == "new-test-tenant"
        self.created_buckets.append(bucket)
        
        # Verify bucket exists in Registry
        async with NiFiRegistryClient(
            settings.NIFI_REGISTRY_URL,
            settings.NIFI_REGISTRY_AUTH_TOKEN
        ) as registry_client:
            registry_bucket = await registry_client.get_bucket(str(bucket.bucket_id))
            assert registry_bucket is not None
            assert registry_bucket["name"] == bucket.name

    @pytest.mark.asyncio
    async def test_template_flow_definition_retrieval(self):
        """Test retrieving flow definitions from Registry."""
        template = await self.service.create_template(
            name="Flow Definition Test",
            description="Testing flow definition retrieval",
            flow_definition=self.generate_test_flow_definition(),
            scope="GLOBAL",
            version="1.0.0"
        )
        self.created_templates.append(template)
        
        # Get flow definition from Registry
        flow_def = await self.service.get_template_flow_definition(template.template_id)
        
        assert flow_def is not None
        assert isinstance(flow_def, dict)
        # Should have basic NiFi flow structure
        assert "processors" in flow_def or "flowContents" in flow_def

    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test error handling for various scenarios."""
        # Test getting non-existent template
        non_existent = await self.service.get_template(UUID('00000000-0000-0000-0000-000000000000'))
        assert non_existent is None
        
        # Test updating non-existent template
        with pytest.raises(TemplateServiceError):
            await self.service.update_template(
                UUID('00000000-0000-0000-0000-000000000000'),
                name="Should Fail"
            )
        
        # Test deleting non-existent template
        deleted = await self.service.delete_template(UUID('00000000-0000-0000-0000-000000000000'))
        assert deleted is False