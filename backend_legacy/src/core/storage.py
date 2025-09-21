# FILE: backend/src/core/storage.py
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
import logging
from src.core.config import settings

logger = logging.getLogger(__name__)

class ObjectStorageClient:
    def __init__(self):
        # --- THIS IS THE FIX ---
        # The boto3 client is configured to use our generic settings variables.
        # It doesn't care what the variables are called in our app, only what
        # parameter names it receives here (aws_access_key_id, etc.).
        self.s3_client = boto3.client(
            "s3",
            endpoint_url=settings.STORAGE_ENDPOINT_URL,
            aws_access_key_id=settings.STORAGE_ACCESS_KEY,
            aws_secret_access_key=settings.STORAGE_SECRET_KEY,
            region_name=settings.STORAGE_REGION,
            config=Config(signature_version="s3v4"),
        )
        self.bucket_name = settings.STORAGE_BUCKET
        # --- END OF FIX ---
        logger.info(f"ObjectStorageClient initialized for bucket '{self.bucket_name}' at endpoint '{settings.STORAGE_ENDPOINT_URL}'.")

    def upload(self, data: bytes, key: str):
        try:
            self.s3_client.put_object(Bucket=self.bucket_name, Key=key, Body=data)
            logger.info(f"Successfully uploaded object to s3://{self.bucket_name}/{key}")
        except ClientError as e:
            logger.error(f"Failed to upload to {key}: {e}")
            raise

    def download(self, key: str) -> bytes | None: # Return None on NoSuchKey
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
            logger.info(f"Successfully downloaded object from s3://{self.bucket_name}/{key}")
            return response["Body"].read()
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                logger.warning(f"Object not found at {key}")
                return None
            logger.error(f"Failed to download from {key}: {e}")
            raise

    def list_objects(self, prefix: str) -> list[str]:
        try:
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=self.bucket_name, Prefix=prefix)
            object_keys = []
            for page in pages:
                if "Contents" in page:
                    for obj in page["Contents"]:
                        object_keys.append(obj["Key"])
            return object_keys
        except ClientError as e:
            logger.error(f"Failed to list objects with prefix {prefix}: {e}")
            return []

# Singleton instance
storage_client = ObjectStorageClient()