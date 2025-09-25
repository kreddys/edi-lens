"""Unit coverage for :mod:`src.services.registry_bucket_management`."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.services.registry_bucket_management import RegistryBucketManagement


@pytest.fixture
def bucket_management_service(mock_registry_client) -> RegistryBucketManagement:
    """Return the bucket management service under test."""

    return RegistryBucketManagement(mock_registry_client)


@pytest.mark.asyncio
async def test_create_bucket_success(bucket_management_service: RegistryBucketManagement, mock_registry_client) -> None:
    """Creating a bucket should return identifiers from the Registry response."""

    mock_registry_client.buckets.create_bucket = AsyncMock(
        return_value={
            "identifier": "bucket-123",
            "name": "test-bucket",
            "createdTimestamp": 1234567890,
        }
    )

    result = await bucket_management_service.create_bucket(
        name="test-bucket",
        description="Test bucket",
    )

    assert result["success"] is True
    assert result["bucket_id"] == "bucket-123"
    assert result["bucket_name"] == "test-bucket"


@pytest.mark.asyncio
async def test_get_or_create_bucket_existing(bucket_management_service: RegistryBucketManagement) -> None:
    """If the bucket already exists it should be returned instead of recreated."""

    bucket_management_service.list_buckets = AsyncMock(
        return_value=[{"bucket_id": "bucket-123", "bucket_name": "existing-bucket"}]
    )

    result = await bucket_management_service.get_or_create_bucket("existing-bucket")

    assert result["bucket_id"] == "bucket-123"
    assert result["bucket_name"] == "existing-bucket"


@pytest.mark.asyncio
async def test_get_or_create_bucket_new(bucket_management_service: RegistryBucketManagement) -> None:
    """A missing bucket should be created using the service helper."""

    bucket_management_service.list_buckets = AsyncMock(return_value=[])
    bucket_management_service.create_bucket = AsyncMock(
        return_value={
            "success": True,
            "bucket_id": "bucket-456",
            "bucket_name": "new-bucket",
        }
    )

    result = await bucket_management_service.get_or_create_bucket("new-bucket")

    assert result["bucket_id"] == "bucket-456"
    assert result["bucket_name"] == "new-bucket"
