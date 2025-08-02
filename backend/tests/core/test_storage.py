import pytest
import pytest_asyncio
import uuid
from typing import AsyncGenerator

from src.core.storage import storage_client

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]

@pytest_asyncio.fixture(scope="function", autouse=True)
async def clean_minio_bucket():
    """Ensures the test bucket is clean before each test function."""
    # This is a simple cleanup; in a real-world scenario, you might list and delete all objects.
    # For now, we rely on unique keys per test.
    yield
    # No teardown needed for now, as each test uses unique keys.

async def test_upload_and_download():
    """Tests that a file can be uploaded and then downloaded with matching content."""
    # Arrange
    test_key = f"test-data/{uuid.uuid4()}.txt"
    test_content = b"This is a test file for MinIO."

    # Act
    storage_client.upload(data=test_content, key=test_key)
    downloaded_content = storage_client.download(key=test_key)

    # Assert
    assert downloaded_content is not None
    assert downloaded_content == test_content

async def test_download_nonexistent_key_returns_none():
    """Tests that downloading a key that doesn't exist returns None."""
    # Arrange
    test_key = f"nonexistent/{uuid.uuid4()}.txt"

    # Act
    downloaded_content = storage_client.download(key=test_key)

    # Assert
    assert downloaded_content is None

async def test_list_objects():
    """Tests listing objects with a specific prefix."""
    # Arrange
    prefix = f"listing-test/{uuid.uuid4()}"
    key1 = f"{prefix}/file1.txt"
    key2 = f"{prefix}/file2.txt"
    other_key = "other-dir/file3.txt"
    
    storage_client.upload(data=b"1", key=key1)
    storage_client.upload(data=b"2", key=key2)
    storage_client.upload(data=b"3", key=other_key)

    # Act
    listed_keys = storage_client.list_objects(prefix=prefix)

    # Assert
    assert len(listed_keys) == 2
    assert key1 in listed_keys
    assert key2 in listed_keys
    assert other_key not in listed_keys