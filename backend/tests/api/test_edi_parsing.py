# FILE: backend/tests/api/test_edi_parsing.py

import pytest
from fastapi import status
from unittest.mock import patch, AsyncMock

from src.api.schemas import EdiParsingRequest

@pytest.mark.integration
class TestEdiParsing:
    """Test suite for the EDI parsing endpoint."""

    @pytest.fixture
    def parsing_request(self, valid_837p_edi_string):
        """Sample EDI parsing request."""
        return EdiParsingRequest(
            edi_content=valid_837p_edi_string,
            tenant_id="tenant-a",
            schema_name="837.5010.X222.A1.json",
        )

    @pytest.mark.asyncio
    async def test_successful_parsing(self, async_client, parsing_request):
        """Test successful EDI parsing."""
        response = await async_client.post(
            "/api/v1/edi/parse",
            json=parsing_request.model_dump(),
            headers={"Authorization": "Bearer test-token"},
        )

        assert response.status_code == status.HTTP_200_OK
        parsed_data = response.json()
        assert isinstance(parsed_data, list)
        assert len(parsed_data) > 0
        assert parsed_data[0]["id"] == "ISA"

    @pytest.mark.asyncio
    async def test_parsing_with_invalid_edi(self, async_client, parsing_request):
        """Test parsing with invalid EDI content."""
        parsing_request.edi_content = "INVALID EDI"
        response = await async_client.post(
            "/api/v1/edi/parse",
            json=parsing_request.model_dump(),
            headers={"Authorization": "Bearer test-token"},
        )

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @pytest.mark.asyncio
    async def test_parsing_with_missing_schema(self, async_client, parsing_request):
        """Test parsing with a missing schema."""
        parsing_request.schema_name = "non_existent_schema.json"
        response = await async_client.post(
            "/api/v1/edi/parse",
            json=parsing_request.model_dump(),
            headers={"Authorization": "Bearer test-token"},
        )

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
