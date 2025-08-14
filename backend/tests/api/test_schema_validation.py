# FILE: backend/tests/api/test_schema_validation.py

import pytest
from fastapi import status
from unittest.mock import patch, AsyncMock

from src.api.schemas import SchemaValidationRequest

@pytest.mark.integration
class TestSchemaValidation:
    """Test suite for the schema validation endpoint."""

    @pytest.fixture
    def validation_request(self):
        """Sample schema validation request."""
        return SchemaValidationRequest(
            tenant_id="tenant-a",
            schema_name="837.5010.X222.A1.json",
        )

    @pytest.mark.asyncio
    async def test_successful_validation(self, async_client, validation_request):
        """Test successful schema validation."""
        response = await async_client.post(
            "/api/v1/schemas/validate",
            json=validation_request.model_dump(),
            headers={"Authorization": "Bearer test-token"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"is_valid": True}

    @pytest.mark.asyncio
    async def test_validation_with_missing_schema(self, async_client, validation_request):
        """Test validation with a missing schema."""
        validation_request.schema_name = "non_existent_schema.json"
        response = await async_client.post(
            "/api/v1/schemas/validate",
            json=validation_request.model_dump(),
            headers={"Authorization": "Bearer test-token"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"is_valid": False}
