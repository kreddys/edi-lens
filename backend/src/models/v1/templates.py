"""RESTful API models for templates."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import datetime

from pydantic import BaseModel, Field

from .flows import FlowDefinition


class TemplateBase(BaseModel):
    """Base template model."""
    name: str = Field(..., description="Template name")
    description: str = Field("", description="Template description")
    category: str = Field("general", description="Template category")
    tags: List[str] = Field(default_factory=list, description="Template tags")


class TemplateCreate(TemplateBase):
    """Model for creating a new template."""
    definition: FlowDefinition = Field(..., description="Template flow definition")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Template parameters with defaults")


class TemplateUpdate(BaseModel):
    """Model for updating an existing template."""
    name: Optional[str] = Field(None, description="Template name")
    description: Optional[str] = Field(None, description="Template description")
    category: Optional[str] = Field(None, description="Template category")
    tags: Optional[List[str]] = Field(None, description="Template tags")
    definition: Optional[FlowDefinition] = Field(None, description="Template flow definition")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Template parameters")


class TemplateResponse(TemplateBase):
    """Model for template response."""
    id: str = Field(..., description="Template ID")
    definition: Optional[FlowDefinition] = None  # Optional for list responses
    parameters: Dict[str, Any] = Field(..., description="Template parameters with defaults")
    processor_count: int = Field(0, description="Number of processors in template")
    connection_count: int = Field(0, description="Number of connections in template")
    parameter_count: int = Field(0, description="Number of parameters in template")
    usage_count: int = Field(0, description="Number of times template has been used")
    created_at: Optional[str] = Field(None, description="Creation timestamp")
    updated_at: Optional[str] = Field(None, description="Last update timestamp")


class TemplateListResponse(BaseModel):
    """Model for template list response."""
    templates: List[TemplateResponse] = Field(..., description="List of templates")
    total: int = Field(..., description="Total number of templates")
    categories: List[str] = Field(default_factory=list, description="Available categories")
    tags: List[str] = Field(default_factory=list, description="Available tags")


class TemplateValidationRequest(BaseModel):
    """Model for template validation requests."""
    definition: FlowDefinition = Field(..., description="Template definition to validate")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Parameters to validate")
    strict: bool = Field(False, description="Whether to perform strict validation")


class TemplateValidationResponse(BaseModel):
    """Model for template validation response."""
    valid: bool = Field(..., description="Whether the template is valid")
    errors: List[str] = Field(default_factory=list, description="Validation errors")
    warnings: List[str] = Field(default_factory=list, description="Validation warnings")
    summary: Dict[str, Any] = Field(default_factory=dict, description="Validation summary")