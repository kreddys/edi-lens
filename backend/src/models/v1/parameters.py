"""Parameter update models."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class ParameterUpdate(BaseModel):
    """Request model for updating a single parameter."""
    
    name: str = Field(..., description="Parameter name")
    value: str = Field(..., description="Parameter value")
    description: Optional[str] = Field(None, description="Parameter description")
    sensitive: bool = Field(False, description="Whether parameter is sensitive")


class ParameterUpdateRequest(BaseModel):
    """Request model for updating multiple parameters."""
    
    parameters: List[ParameterUpdate] = Field(..., description="List of parameter updates")


class ParameterUpdateResponse(BaseModel):
    """Response model for parameter update operations."""
    
    success: bool = Field(..., description="Whether the update was successful")
    updated_parameters: List[str] = Field(..., description="Names of updated parameters")
    parameter_context_id: str = Field(..., description="ID of the updated parameter context")
    revision: int = Field(..., description="New revision number")
    errors: Optional[List[str]] = Field(None, description="List of errors if any occurred")
    message: str = Field(..., description="Human-readable result message")