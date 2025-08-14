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
    async def test_list_schemas_combines_base_and_specialized(self, async_client: AsyncClient, mock_user_context):
        # This test remains the same but now benefits from the autouse fixture
        tenant_id = "tenant-a"
        specialized_schema_name = "test_specialized.json"
        s3_key = f"{tenant_id}/schemas/{specialized_schema_name}"
        storage_client.upload(b'{"transactionName": "Specialized", "version": "v1", "description": "d1", "structure": []}', key=s3_key)
        
        with patch('src.core.auth.get_current_user', return_value=mock_user_context):
            headers = {"X-Tenant-ID": tenant_id}
            response = await async_client.get("/api/v1/schemas", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert "837.5010.X222.A1.json" in data["base_schemas"]
        assert specialized_schema_name in data["specialized_schemas"]