import pytest
from unittest.mock import MagicMock, patch
from botocore.exceptions import ClientError
from src.core.storage import ObjectStorageClient, storage_client

pytestmark = pytest.mark.unit

@pytest.fixture
def mock_s3_client():
    """Fixture for a mocked S3 client."""
    with patch('boto3.client') as mock:
        yield mock

@pytest.fixture
def unit_storage_client(mock_s3_client):
    """Fixture to create a new ObjectStorageClient for each test."""
    return ObjectStorageClient()

def test_upload_success(unit_storage_client: ObjectStorageClient):
    """Test successful upload."""
    unit_storage_client.upload(b"test_data", "test_key")
    unit_storage_client.s3_client.put_object.assert_called_once_with(
        Bucket=unit_storage_client.bucket_name, Key="test_key", Body=b"test_data"
    )

def test_upload_client_error(unit_storage_client: ObjectStorageClient):
    """Test that ClientError is re-raised on upload failure."""
    unit_storage_client.s3_client.put_object.side_effect = ClientError({}, "put_object")
    with pytest.raises(ClientError):
        unit_storage_client.upload(b"test_data", "test_key")

def test_download_success(unit_storage_client: ObjectStorageClient):
    """Test successful download."""
    mock_response = {
        "Body": MagicMock(read=MagicMock(return_value=b"test_data"))
    }
    unit_storage_client.s3_client.get_object.return_value = mock_response
    data = unit_storage_client.download("test_key")
    assert data == b"test_data"
    unit_storage_client.s3_client.get_object.assert_called_once_with(
        Bucket=unit_storage_client.bucket_name, Key="test_key"
    )

def test_download_no_such_key(unit_storage_client: ObjectStorageClient):
    """Test that None is returned when the key is not found."""
    unit_storage_client.s3_client.get_object.side_effect = ClientError(
        {"Error": {"Code": "NoSuchKey"}}, "get_object"
    )
    data = unit_storage_client.download("test_key")
    assert data is None

def test_download_client_error(unit_storage_client: ObjectStorageClient):
    """Test that other ClientErrors are re-raised on download failure."""
    unit_storage_client.s3_client.get_object.side_effect = ClientError(
        {"Error": {"Code": "SomeOtherError"}}, "get_object"
    )
    with pytest.raises(ClientError):
        unit_storage_client.download("test_key")

def test_list_objects_success(unit_storage_client: ObjectStorageClient):
    """Test successful listing of objects."""
    mock_paginator = MagicMock()
    mock_pages = [
        {"Contents": [{"Key": "key1"}, {"Key": "key2"}]},
        {"Contents": [{"Key": "key3"}]},
    ]
    mock_paginator.paginate.return_value = mock_pages
    unit_storage_client.s3_client.get_paginator.return_value = mock_paginator

    keys = unit_storage_client.list_objects("test_prefix")
    assert keys == ["key1", "key2", "key3"]
    unit_storage_client.s3_client.get_paginator.assert_called_once_with('list_objects_v2')
    mock_paginator.paginate.assert_called_once_with(
        Bucket=unit_storage_client.bucket_name, Prefix="test_prefix"
    )

def test_list_objects_client_error(unit_storage_client: ObjectStorageClient):
    """Test that an empty list is returned on ClientError."""
    unit_storage_client.s3_client.get_paginator.side_effect = ClientError({}, "list_objects_v2")
    keys = unit_storage_client.list_objects("test_prefix")
    assert keys == []

def test_list_objects_no_contents(unit_storage_client: ObjectStorageClient):
    """Test listing objects when there are no contents."""
    mock_paginator = MagicMock()
    mock_pages = [{}]
    mock_paginator.paginate.return_value = mock_pages
    unit_storage_client.s3_client.get_paginator.return_value = mock_paginator

    keys = unit_storage_client.list_objects("test_prefix")
    assert keys == []

@patch('src.core.storage.boto3.client')
def test_storage_client_initialization(mock_boto3_client):
    """Test that the ObjectStorageClient initializes correctly."""
    ObjectStorageClient()
    mock_boto3_client.assert_called_once()

import pytest_asyncio
import uuid
from typing import AsyncGenerator


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