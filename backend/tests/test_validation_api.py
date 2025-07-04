import pytest
from httpx import AsyncClient

from .test_edi_parser import VALID_EDI_STRING

pytestmark = pytest.mark.asyncio

async def test_validate_endpoint_success(async_client: AsyncClient):
    request_data = {
        "edi_data": VALID_EDI_STRING,
        "implementation_guide": "837.5010.X222.A1"
    }
    response = await async_client.post("/api/v1/validate", json=request_data)
    assert response.status_code == 200

async def test_validate_endpoint_parsing_error(async_client: AsyncClient):
    request_data = {
        "edi_data": "this is not valid edi~",
        "implementation_guide": "837.5010.X222.A1"
    }
    response = await async_client.post("/api/v1/validate", json=request_data)
    assert response.status_code == 400