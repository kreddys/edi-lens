import pytest
from httpx import AsyncClient

# Re-use the valid EDI string from the other test file
from .test_edi_parser import VALID_EDI_STRING

# Mark all tests in this file as async
pytestmark = pytest.mark.asyncio

async def test_validate_endpoint_success(async_client: AsyncClient):
    """
    Tests the /validate endpoint with a valid EDI string.
    """
    request_data = {
        "edi_data": VALID_EDI_STRING,
        "implementation_guide": "837.5010.X222.A1"
    }
    
    response = await async_client.post("/api/v1/validate", json=request_data)
    
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] == "Parsed Successfully"
    assert len(data["parsed_segments"]) == 5
    assert data["parsed_segments"][0]["id"] == "ISA"

async def test_validate_endpoint_parsing_error(async_client: AsyncClient):
    """
    Tests that the /validate endpoint returns a 400 error for invalid EDI.
    """
    request_data = {
        "edi_data": "this is not valid edi~",
        "implementation_guide": "837.5010.X222.A1"
    }
    
    response = await async_client.post("/api/v1/validate", json=request_data)
    
    assert response.status_code == 400
    
    data = response.json()
    assert "detail" in data
    assert data["detail"] == "No valid segments found after parsing."