import pytest_asyncio
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from src.main import app

@pytest_asyncio.fixture(scope="function")
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Provide a clean test client for each test function."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client