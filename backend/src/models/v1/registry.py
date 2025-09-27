"""RESTful API models for registry."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class BucketBase(BaseModel):
    """Base bucket model."""
    name: str = Field(..., description="Bucket name")
    description: str = Field("", description="Bucket description")
    allow_public_read: bool = Field(False, description="Whether to allow public read access")


class BucketCreate(BucketBase):
    """Model for creating a new bucket."""
    pass


class BucketUpdate(BaseModel):
    """Model for updating an existing bucket."""
    name: Optional[str] = Field(None, description="Bucket name")
    description: Optional[str] = Field(None, description="Bucket description")
    allow_public_read: Optional[bool] = Field(None, description="Whether to allow public read access")


class BucketResponse(BucketBase):
    """Model for bucket response."""
    id: str = Field(..., description="Bucket ID")
    created_at: Optional[str] = Field(None, description="Creation timestamp")
    updated_at: Optional[str] = Field(None, description="Last update timestamp")
    flow_count: int = Field(0, description="Number of flows in bucket")
    permissions: Dict[str, bool] = Field(default_factory=dict, description="Bucket permissions")
    revision: Dict[str, Any] = Field(default_factory=dict, description="Bucket revision info")

    @field_validator('created_at', 'updated_at', mode='before')
    @classmethod
    def convert_timestamp(cls, v):
        """Convert timestamp to string if needed."""
        if v is None:
            return v
        if isinstance(v, int):
            # Convert Unix timestamp (milliseconds) to ISO string
            return datetime.fromtimestamp(v / 1000).isoformat()
        return str(v)


class RegistryFlowBase(BaseModel):
    """Base registry flow model."""
    name: str = Field(..., description="Flow name")
    description: str = Field("", description="Flow description")
    bucket_id: str = Field(..., description="Bucket ID")


class RegistryFlowResponse(RegistryFlowBase):
    """Model for registry flow response."""
    id: str = Field(..., description="Flow ID")
    version_count: int = Field(0, description="Number of versions")
    latest_version: Optional[int] = Field(None, description="Latest version number")
    created_at: Optional[str] = Field(None, description="Creation timestamp")
    updated_at: Optional[str] = Field(None, description="Last update timestamp")
    permissions: Dict[str, bool] = Field(default_factory=dict, description="Flow permissions")

    @field_validator('created_at', 'updated_at', mode='before')
    @classmethod
    def convert_timestamp(cls, v):
        """Convert timestamp to string if needed."""
        if v is None:
            return v
        if isinstance(v, int):
            # Convert Unix timestamp (milliseconds) to ISO string
            return datetime.fromtimestamp(v / 1000).isoformat()
        return str(v)


class RegistryFlowVersion(BaseModel):
    """Model for registry flow version."""
    version: int = Field(..., description="Version number")
    flow_id: str = Field(..., description="Flow ID")
    bucket_id: str = Field(..., description="Bucket ID")
    comments: str = Field("", description="Version comments")
    author: Optional[str] = Field(None, description="Version author")
    created_at: str = Field(..., description="Version creation timestamp")
    snapshot_metadata: Dict[str, Any] = Field(default_factory=dict, description="Snapshot metadata")
    flow_contents: Dict[str, Any] = Field(default_factory=dict, description="Flow contents")

    @field_validator('created_at', mode='before')
    @classmethod
    def validate_created_at(cls, v):
        """Convert Unix timestamp to string if needed."""
        if isinstance(v, int):
            return datetime.fromtimestamp(v / 1000).isoformat() + "Z"
        return v


class RegistryFlowVersionListResponse(BaseModel):
    """Model for registry flow version list response."""
    versions: List[RegistryFlowVersion] = Field(..., description="List of flow versions")
    flow_id: str = Field(..., description="Flow ID")
    bucket_id: str = Field(..., description="Bucket ID")
    total: int = Field(..., description="Total number of versions")


class RegistryFlowListResponse(BaseModel):
    """Model for registry flow list response."""
    flows: List[RegistryFlowResponse] = Field(..., description="List of flows")
    total: int = Field(..., description="Total number of flows")