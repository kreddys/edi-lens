"""
Integration tests for Template API endpoints (/api/v1/templates/).

Tests the complete template API functionality including:
- Template CRUD operations through HTTP
- Authentication and authorization validation
- Request/response schema validation
- Built-in template seeding endpoint
"""

import pytest
from uuid import uuid4
from httpx import AsyncClient
from asgi_lifespan import LifespanManager
from fastapi import status

from src.main import app
from src.core.auth import get_current_user, User, RealmAccess
from src.core.database import get_db

pytestmark = pytest.mark.integration


@pytest.fixture
def admin_user():
    """User with admin permissions."""
    return User(
        sub="admin-user",
        preferred_username="admin", 
        groups=["tenant-a"],
        realm_access=RealmAccess(roles=["admin", "workflow:write", "workflow:read"])
    )


@pytest.fixture
def regular_user():
    """User with limited permissions."""
    return User(
        sub="regular-user",
        preferred_username="regular",
        groups=["tenant-a"], 
        realm_access=RealmAccess(roles=["workflow:read"])
    )


@pytest.fixture
def tenant_b_user():
    """User from different tenant."""
    return User(
        sub="tenant-b-user",
        preferred_username="tenant-b-user",
        groups=["tenant-b"],
        realm_access=RealmAccess(roles=["workflow:write", "workflow:read"])
    )


@pytest.fixture(autouse=True)
def cleanup_overrides():
    """Cleanup dependency overrides after each test.""" 
    yield
    app.dependency_overrides.clear()


class TestTemplateEndpoints:
    """Integration tests for template API endpoints."""
    
    @property
    def tenant_headers(self):
        """Standard headers with tenant ID."""
        return {"x-tenant-id": "tenant-a"}
    
    @property  
    def tenant_b_headers(self):
        """Headers for tenant B."""
        return {"x-tenant-id": "tenant-b"}

    def generate_test_flow_definition(self):
        """Generate a test flow definition."""
        return {
            "identifier": f"test-flow-{uuid4().hex[:8]}",
            "name": "Test API Flow",
            "description": "Test flow for API endpoint testing",
            "processors": [
                {
                    "identifier": str(uuid4()),
                    "name": "Test Processor",
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
    async def test_create_template_endpoint(self, admin_user, db_session):
        """Test template creation endpoint."""
        app.dependency_overrides[get_current_user] = lambda: admin_user
        app.dependency_overrides[get_db] = lambda: db_session
        
        async with LifespanManager(app):
            async with AsyncClient(app=app, base_url="http://test") as client:
                template_data = {
                    "name": f"API Test Template {uuid4().hex[:8]}",
                    "description": "Template created via API endpoint test",
                    "flow_definition": self.generate_test_flow_definition()
                }
                
                response = await client.post(
                    "/api/v1/templates/", 
                    json=template_data,
                    headers=self.tenant_headers
                )
                
                assert response.status_code == status.HTTP_201_CREATED
                data = response.json()
                
                # Verify HTTP response structure
                assert "template_id" in data
                assert data["name"] == template_data["name"] 
                assert data["description"] == template_data["description"]
                assert data["scope"] == "GLOBAL"  # Admin users create GLOBAL templates
                assert data["tenant_id"] is None  # GLOBAL templates have no tenant_id
                assert data["status"] == "ACTIVE"
                assert data["current_version"] == 1  # Integer version, not string
                assert data["usage_count"] == 0
                assert "bucket_id" in data
                assert "created_at" in data
                assert "updated_at" in data
                
                template_id = data["template_id"]
                bucket_id = data["bucket_id"]
                
                # ========================================
                # Validate Registry-First Architecture
                # ========================================
                
                # 1. Verify template exists in DATABASE with correct references
                from src.services.template_service import TemplateService
                from uuid import UUID
                
                template_service = TemplateService(db_session)
                db_template = await template_service.get_template(UUID(template_id))
                
                assert db_template is not None, "Template not found in database"
                assert str(db_template.template_id) == template_id
                assert str(db_template.bucket_id) == bucket_id
                assert db_template.name == template_data["name"]
                assert db_template.description == template_data["description"]
                assert db_template.scope == "GLOBAL"
                assert db_template.status == "ACTIVE"
                assert db_template.current_version == 1
                assert db_template.created_by == "admin-user"  # From auth context
                
                # 2. Verify bucket exists in DATABASE
                from src.models.registry_models import RegistryBucket
                from sqlalchemy import select
                
                bucket_query = select(RegistryBucket).where(RegistryBucket.bucket_id == UUID(bucket_id))
                bucket_result = await db_session.execute(bucket_query)
                db_bucket = bucket_result.scalar_one_or_none()
                
                assert db_bucket is not None, "Bucket not found in database"
                assert str(db_bucket.bucket_id) == bucket_id
                assert db_bucket.scope == "GLOBAL"
                assert db_bucket.tenant_id is None  # Global buckets have no tenant
                assert db_bucket.name == "global-templates"
                
                # 3. Verify template exists in NiFi REGISTRY
                from src.nifi.clients.registry_client import NiFiRegistryClient
                from src.core.config import settings
                
                async with NiFiRegistryClient(
                    settings.NIFI_REGISTRY_URL,
                    settings.NIFI_REGISTRY_AUTH_TOKEN
                ) as registry_client:
                    # Verify bucket exists in Registry
                    registry_bucket = await registry_client.get_bucket(bucket_id)
                    assert registry_bucket is not None, "Bucket not found in NiFi Registry"
                    assert registry_bucket["identifier"] == bucket_id
                    assert registry_bucket["name"] == "global-templates"
                    assert "global scope" in registry_bucket["description"].lower()
                    
                    # Verify flow exists in Registry
                    registry_flow = await registry_client.get_flow(bucket_id, template_id)
                    assert registry_flow is not None, "Flow not found in NiFi Registry"
                    assert registry_flow["identifier"] == template_id
                    assert registry_flow["name"] == template_data["name"]
                    assert registry_flow["description"] == template_data["description"]
                    assert registry_flow["bucketIdentifier"] == bucket_id
                    
                    # Verify flow version exists in Registry
                    flow_versions = await registry_client.list_flow_versions(bucket_id, template_id)
                    assert len(flow_versions) >= 1, "Flow version not found in NiFi Registry"
                    
                    latest_version = flow_versions[0]  # Versions are ordered by version number desc
                    assert latest_version["version"] == 1
                    assert latest_version["flowIdentifier"] == template_id
                    assert latest_version["bucketIdentifier"] == bucket_id
                    
                    # Verify flow definition can be retrieved
                    flow_definition = await registry_client.get_flow_version(
                        bucket_id, template_id, latest_version["version"]
                    )
                    assert flow_definition is not None, "Flow definition not retrievable from Registry"
                    
                    # Validate flow definition structure matches what we sent
                    flow_contents = flow_definition.get("flowContents", {})
                    assert "processors" in flow_contents
                    assert len(flow_contents["processors"]) == 1  # Our test flow has 1 processor
                    
                    test_processor = flow_contents["processors"][0]
                    assert test_processor["name"] == "Test Processor"
                    assert test_processor["type"] == "org.apache.nifi.processors.standard.GenerateFlowFile"
                    assert "File Size" in test_processor.get("properties", {})
                
                # 4. Verify Registry-Database ID consistency
                assert str(db_template.template_id) == registry_flow["identifier"]
                assert str(db_template.bucket_id) == registry_bucket["identifier"]
                
                print(f"✅ Registry-First Validation Complete:")
                print(f"   📊 Template ID: {template_id}")
                print(f"   🗂️  Bucket ID: {bucket_id}")
                print(f"   🏛️  Database: ✅ Template + Bucket records")
                print(f"   🔗 Registry: ✅ Bucket + Flow + Version")
                print(f"   🔄 Sync: ✅ IDs consistent across systems")

    @pytest.mark.asyncio
    async def test_get_template_endpoint(self, admin_user, db_session):
        """Test template retrieval endpoint."""
        app.dependency_overrides[get_current_user] = lambda: admin_user
        app.dependency_overrides[get_db] = lambda: db_session
        
        async with LifespanManager(app):
            async with AsyncClient(app=app, base_url="http://test") as client:
                # Create template first
                template_data = {
                    "name": f"Get Test Template {uuid4().hex[:8]}",
                    "description": "Template for get endpoint test",
                    "flow_definition": self.generate_test_flow_definition()
                }
                
                create_response = await client.post("/api/v1/templates/", json=template_data, headers=self.tenant_headers)
                
                # Debug logging for failed requests
                if create_response.status_code != status.HTTP_201_CREATED:
                    print(f"CREATE TEMPLATE FAILED:")
                    print(f"  Request data: {template_data}")
                    print(f"  Response status: {create_response.status_code}")
                    print(f"  Response headers: {dict(create_response.headers)}")
                    try:
                        error_detail = create_response.json()
                        print(f"  Response JSON: {error_detail}")
                    except:
                        print(f"  Response text: {create_response.text}")
                
                assert create_response.status_code == status.HTTP_201_CREATED
                template_id = create_response.json()["template_id"]
                
                # Get template
                get_response = await client.get(f"/api/v1/templates/{template_id}", headers=self.tenant_headers)
                
                assert get_response.status_code == status.HTTP_200_OK
                data = get_response.json()
                
                assert data["template_id"] == template_id
                assert data["name"] == template_data["name"]
                assert data["scope"] == "GLOBAL"
                assert data["status"] == "ACTIVE"

    @pytest.mark.asyncio
    async def test_list_templates_endpoint(self, admin_user, db_session):
        """Test template listing endpoint with filtering."""
        app.dependency_overrides[get_current_user] = lambda: admin_user  
        app.dependency_overrides[get_db] = lambda: db_session
        
        async with LifespanManager(app):
            async with AsyncClient(app=app, base_url="http://test") as client:
                # Create test templates
                global_template_data = {
                    "name": f"Global List Test {uuid4().hex[:8]}",
                    "description": "Global template for list test",
                    "flow_definition": self.generate_test_flow_definition()
                }
                
                tenant_template_data = {
                    "name": f"Tenant List Test {uuid4().hex[:8]}",
                    "description": "Tenant template for list test", 
                    "flow_definition": self.generate_test_flow_definition()
                }
                
                # Create templates
                global_response = await client.post("/api/v1/templates/", json=global_template_data, headers=self.tenant_headers)
                tenant_response = await client.post("/api/v1/templates/", json=tenant_template_data, headers=self.tenant_headers)
                
                assert global_response.status_code == status.HTTP_201_CREATED
                assert tenant_response.status_code == status.HTTP_201_CREATED
                
                # Test list all templates
                list_response = await client.get("/api/v1/templates/", headers=self.tenant_headers)
                assert list_response.status_code == status.HTTP_200_OK
                templates = list_response.json()
                assert len(templates) >= 2
                
                template_names = [t["name"] for t in templates]
                assert global_template_data["name"] in template_names
                assert tenant_template_data["name"] in template_names

    @pytest.mark.asyncio
    async def test_update_template_endpoint(self, admin_user, db_session):
        """Test template update endpoint."""
        app.dependency_overrides[get_current_user] = lambda: admin_user
        app.dependency_overrides[get_db] = lambda: db_session
        
        async with LifespanManager(app):
            async with AsyncClient(app=app, base_url="http://test") as client:
                # Create template
                create_data = {
                    "name": f"Update Test Template {uuid4().hex[:8]}",
                    "description": "Original description",
                    "flow_definition": self.generate_test_flow_definition()
                }
                
                create_response = await client.post("/api/v1/templates/", json=create_data, headers=self.tenant_headers)
                template_id = create_response.json()["template_id"]
                
                # Update template
                update_data = {
                    "flow_definition": self.generate_test_flow_definition()
                }
                
                update_response = await client.put(f"/api/v1/templates/{template_id}", json=update_data, headers=self.tenant_headers)
                
                assert update_response.status_code == status.HTTP_200_OK
                data = update_response.json()
                
                assert data["template_id"] == template_id
                assert data["current_version"] == 2  # Should be version 2 after update
                assert "updated_at" in data
                
                # ========================================
                # Validate Registry-First Architecture After Update
                # ========================================
                
                # 1. Verify template exists in DATABASE with updated version
                from src.services.template_service import TemplateService
                from uuid import UUID
                
                template_service = TemplateService(db_session)
                db_template = await template_service.get_template(UUID(template_id))
                
                assert db_template is not None, "Template not found in database"
                assert db_template.current_version == 2, "Database template version should be 2"
                
                # 2. Verify template exists in NiFi REGISTRY with both versions
                from src.nifi.clients.registry_client import NiFiRegistryClient
                from src.core.config import settings
                
                async with NiFiRegistryClient(
                    settings.NIFI_REGISTRY_URL,
                    settings.NIFI_REGISTRY_AUTH_TOKEN
                ) as registry_client:
                    # Verify flow exists in Registry
                    registry_flow = await registry_client.get_flow(db_template.bucket_id, template_id)
                    assert registry_flow is not None, "Flow not found in NiFi Registry"
                    assert registry_flow["identifier"] == template_id
                    
                    # Verify both flow versions exist in Registry
                    flow_versions = await registry_client.list_flow_versions(db_template.bucket_id, template_id)
                    assert len(flow_versions) == 2, f"Expected 2 flow versions, got {len(flow_versions)}"
                    
                    # Verify versions are numbered correctly
                    version_numbers = [v["version"] for v in flow_versions]
                    assert sorted(version_numbers) == [1, 2], f"Expected versions [1, 2], got {sorted(version_numbers)}"
                    
                    # Verify latest version has updated flow definition
                    latest_version = max(flow_versions, key=lambda v: v["version"])
                    assert latest_version["version"] == 2, "Latest version should be 2"
                    
                    # Verify flow definition can be retrieved for latest version
                    flow_definition = await registry_client.get_flow_version(
                        db_template.bucket_id, template_id, latest_version["version"]
                    )
                    assert flow_definition is not None, "Flow definition not retrievable from Registry"
                    
                    # Validate flow definition structure matches what we sent
                    flow_contents = flow_definition.get("flowContents", {})
                    assert "processors" in flow_contents
                    assert len(flow_contents["processors"]) == 1  # Our test flow has 1 processor
                
                # 3. Verify Registry-Database ID consistency
                assert str(db_template.template_id) == registry_flow["identifier"]
                
                print(f"✅ Registry-First Validation Complete After Update:")
                print(f"   📊 Template ID: {template_id}")
                print(f"   🗂️  Bucket ID: {db_template.bucket_id}")
                print(f"   🏛️  Database: ✅ Template version 2")
                print(f"   🔗 Registry: ✅ Flow versions 1 & 2")
                print(f"   🔄 Sync: ✅ IDs consistent across systems")

    @pytest.mark.asyncio
    async def test_delete_template_endpoint(self, admin_user, db_session):
        """Test template deletion endpoint."""
        app.dependency_overrides[get_current_user] = lambda: admin_user
        app.dependency_overrides[get_db] = lambda: db_session
        
        async with LifespanManager(app):
            async with AsyncClient(app=app, base_url="http://test") as client:
                # Create template
                create_data = {
                    "name": f"Delete Test Template {uuid4().hex[:8]}",
                    "description": "Template for delete test",
                    "flow_definition": self.generate_test_flow_definition()
                }
                
                create_response = await client.post("/api/v1/templates/", json=create_data, headers=self.tenant_headers)
                template_id = create_response.json()["template_id"]
                
                # Delete template
                delete_response = await client.delete(f"/api/v1/templates/{template_id}", headers=self.tenant_headers)
                
                assert delete_response.status_code == status.HTTP_204_NO_CONTENT

    @pytest.mark.asyncio
    async def test_seed_templates_endpoint(self, admin_user, db_session):
        """Test built-in template seeding endpoint."""
        app.dependency_overrides[get_current_user] = lambda: admin_user
        app.dependency_overrides[get_db] = lambda: db_session
        
        async with LifespanManager(app):
            async with AsyncClient(app=app, base_url="http://test") as client:
                response = await client.post("/api/v1/templates/seed", headers=self.tenant_headers)
                
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                
                # Verify response structure
                assert "seeded" in data
                assert "skipped" in data
                assert "errors" in data
                assert isinstance(data["seeded"], list)
                assert isinstance(data["skipped"], list)
                assert isinstance(data["errors"], list)

    @pytest.mark.asyncio
    async def test_authorization_enforcement(self, regular_user, admin_user, db_session):
        """Test authorization enforcement on template endpoints."""
        async with LifespanManager(app):
            async with AsyncClient(app=app, base_url="http://test") as client:
                # Test regular user cannot create templates
                app.dependency_overrides[get_current_user] = lambda: regular_user
                app.dependency_overrides[get_db] = lambda: db_session
                
                create_data = {
                    "name": f"Should Fail Template {uuid4().hex[:8]}",
                    "description": "This should fail",
                    "flow_definition": self.generate_test_flow_definition()
                }
                
                create_response = await client.post("/api/v1/templates/", json=create_data, headers=self.tenant_headers)
                assert create_response.status_code == status.HTTP_403_FORBIDDEN
                
                # Test regular user cannot seed templates
                seed_response = await client.post("/api/v1/templates/seed", headers=self.tenant_headers)
                assert seed_response.status_code == status.HTTP_403_FORBIDDEN
                
                # Test admin can create templates
                app.dependency_overrides[get_current_user] = lambda: admin_user
                
                admin_create_response = await client.post("/api/v1/templates/", json=create_data, headers=self.tenant_headers)
                assert admin_create_response.status_code == status.HTTP_201_CREATED

    @pytest.mark.asyncio
    async def test_tenant_isolation(self, admin_user, tenant_b_user, db_session):
        """Test tenant isolation for templates."""
        async with LifespanManager(app):
            async with AsyncClient(app=app, base_url="http://test") as client:
                # Create template as tenant-a user (using regular user to create tenant template)
                app.dependency_overrides[get_current_user] = lambda: User(
                    sub="tenant-a-user",
                    preferred_username="tenant-a-user",
                    groups=["tenant-a"],
                    realm_access=RealmAccess(roles=["workflow:write", "workflow:read"])
                )
                app.dependency_overrides[get_db] = lambda: db_session
                
                tenant_a_template = {
                    "name": f"Tenant A Template {uuid4().hex[:8]}",
                    "description": "Template for tenant A",
                    "flow_definition": self.generate_test_flow_definition()
                }
                
                create_response = await client.post("/api/v1/templates/", json=tenant_a_template, headers=self.tenant_headers)
                assert create_response.status_code == status.HTTP_201_CREATED
                template_data = create_response.json()
                
                # Switch to tenant-b user
                app.dependency_overrides[get_current_user] = lambda: tenant_b_user
                
                # Tenant B should not see tenant A's template in list
                list_response = await client.get("/api/v1/templates/", headers=self.tenant_b_headers)
                templates = list_response.json()
                
                tenant_template_names = [t["name"] for t in templates if t.get("scope") == "TENANT"]
                assert tenant_a_template["name"] not in tenant_template_names
                
                # Tenant B should not be able to access tenant A's template directly
                template_id = template_data["template_id"]
                get_response = await client.get(f"/api/v1/templates/{template_id}", headers=self.tenant_b_headers)
                # Should either return 404 or 403 depending on implementation
                assert get_response.status_code in [status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN]

    @pytest.mark.asyncio
    async def test_request_validation(self, admin_user, db_session):
        """Test request validation for template endpoints."""
        app.dependency_overrides[get_current_user] = lambda: admin_user
        app.dependency_overrides[get_db] = lambda: db_session
        
        async with LifespanManager(app):
            async with AsyncClient(app=app, base_url="http://test") as client:
                # Test missing required fields
                invalid_data = {
                    "name": "Missing Flow Definition"
                    # Missing flow_definition, description, etc.
                }
                
                response = await client.post("/api/v1/templates/", json=invalid_data, headers=self.tenant_headers)
                assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
                
                # Test invalid UUID for get/update/delete
                invalid_uuid_response = await client.get("/api/v1/templates/invalid-uuid", headers=self.tenant_headers)
                assert invalid_uuid_response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_error_handling(self, admin_user, db_session):
        """Test error handling for template endpoints."""
        app.dependency_overrides[get_current_user] = lambda: admin_user
        app.dependency_overrides[get_db] = lambda: db_session
        
        async with LifespanManager(app):
            async with AsyncClient(app=app, base_url="http://test") as client:
                # Test getting non-existent template
                response = await client.get("/api/v1/templates/00000000-0000-0000-0000-000000000000", headers=self.tenant_headers)
                assert response.status_code == status.HTTP_404_NOT_FOUND
                
                # Test updating non-existent template
                update_data = {
                    "flow_definition": self.generate_test_flow_definition()
                }
                update_response = await client.put(
                    "/api/v1/templates/00000000-0000-0000-0000-000000000000", 
                    json=update_data,
                    headers=self.tenant_headers
                )
                assert update_response.status_code == status.HTTP_404_NOT_FOUND
                
                # Test deleting non-existent template
                delete_response = await client.delete(
                    "/api/v1/templates/00000000-0000-0000-0000-000000000000",
                    headers=self.tenant_headers
                )
                assert delete_response.status_code == status.HTTP_404_NOT_FOUND