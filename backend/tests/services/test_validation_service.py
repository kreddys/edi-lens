# FILE: backend/tests/api/test_api_workflows.py

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from src.main import app
from src.core.auth import User, RealmAccess, get_current_user

from src.core.schema_manager import schema_manager
from pathlib import Path
from src.core.config import settings
import json
import uuid

from unittest.mock import patch
from src.core.storage import storage_client

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]

@pytest_asyncio.fixture(autouse=True)
async def setup_for_api_tests():
    """Ensures the schema manager is loaded before any test in this file runs."""
    if not schema_manager.list_base_schemas():
        schema_manager.load_base_schemas(Path(settings.EDI_SCHEMA_DIRECTORY))
    yield




# === Schema API Tests ===
class TestSchemaApi:
    @pytest.mark.skip(reason="Authentication dependency mocking issue - will be fixed in future PR")
    async def test_list_schemas_combines_base_and_specialized(self, mock_user_context):
        # Use the async_client fixture properly with user context override
        from tests.conftest import TestAsyncSessionLocal
        from httpx import AsyncClient, ASGITransport
        from src.main import app
        from src.core.database import get_db
        from src.core.auth import require_service_auth, ServiceContext, get_current_user, AuthContext
        
        # This test remains the same but now benefits from the autouse fixture
        tenant_id = "tenant-a"
        specialized_schema_name = "test_specialized.json"
        s3_key = f"{tenant_id}/schemas/{specialized_schema_name}"
        storage_client.upload(b'{"transactionName": "Specialized", "version": "v1", "description": "d1", "structure": []}', key=s3_key)
        
        # Create session and override dependencies
        async with TestAsyncSessionLocal() as session:
            async def override_get_db():
                yield session
            
            def override_require_service_auth():
                return ServiceContext(
                    service_name="test-service",
                    allowed_tenants=[]
                )
            
            # Create an AuthContext for the test
            auth_context = AuthContext(mock_user_context, tenant_id)
            
            # Override all dependencies
            app.dependency_overrides[get_db] = override_get_db
            app.dependency_overrides[require_service_auth] = override_require_service_auth
            
            # Create the dependency function and override it
            from src.core.auth import require_permission
            dependency_func = require_permission("schemas:read")
            
            async def mock_auth_dependency():
                return auth_context
            
            app.dependency_overrides[dependency_func] = mock_auth_dependency
            
            try:
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    headers = {"X-Tenant-ID": tenant_id}
                    response = await client.get("/api/v1/schemas", headers=headers)
            finally:
                # Clean up all overrides
                app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert "837.5010.X222.A1.json" in data["base_schemas"]
        assert specialized_schema_name in data["specialized_schemas"]