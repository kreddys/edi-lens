"""Template management operations."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from starlette.status import HTTP_200_OK

from src.api.dependencies import get_flow_template_service
from src.core.logging import get_logger
from src.models.v1.templates import (
    TemplateResponse,
    TemplateListResponse,
    TemplateValidationRequest,
    TemplateValidationResponse
)
from src.services.flow_template_service import FlowTemplateService

log = get_logger(__name__)

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("/", response_model=TemplateListResponse, status_code=HTTP_200_OK)
async def list_templates(
    category: Optional[str] = Query(None, description="Filter by category"),
    tag: Optional[str] = Query(None, description="Filter by tag"),
    search: Optional[str] = Query(None, description="Search in name and description"),
    template_service: FlowTemplateService = Depends(get_flow_template_service),
) -> TemplateListResponse:
    """List all available templates with filtering options."""
    try:
        log.debug("Listing templates: category=%s, tag=%s, search=%s", category, tag, search)
        
        # Get templates from service
        templates_data = await template_service.list_templates()
        
        # Convert to new response format
        templates = []
        all_categories = set()
        all_tags = set()
        
        for template_data in templates_data:
            # Extract data from current format
            template_id = template_data.get("id", "")
            name = template_data.get("name", "")
            description = template_data.get("description", "")
            processor_count = template_data.get("processor_count", 0)
            connection_count = template_data.get("connection_count", 0) 
            parameter_count = template_data.get("parameter_count", 0)
            
            # For now, set default values for new fields
            template_category = "general"  # Default category
            template_tags = []  # Default empty tags
            usage_count = 0  # Not tracked yet
            
            all_categories.add(template_category)
            for tag in template_tags:
                all_tags.add(tag)
            
            # Apply filters
            if category and template_category != category:
                continue
            if tag and tag not in template_tags:
                continue
            if search and search.lower() not in name.lower() and search.lower() not in description.lower():
                continue
            
            # Create template response (without definition for list performance)
            template_response = TemplateResponse(
                id=template_id,
                name=name,
                description=description,
                category=template_category,
                tags=template_tags,
                definition=None,  # Optional for list responses
                parameters={},    # Not included in list for performance
                processor_count=processor_count,
                connection_count=connection_count,
                parameter_count=parameter_count,
                usage_count=usage_count
            )
            templates.append(template_response)
        
        return TemplateListResponse(
            templates=templates,
            total=len(templates),
            categories=sorted(all_categories),
            tags=sorted(all_tags)
        )
        
    except Exception as exc:
        log.exception("Failed to list templates")
        raise HTTPException(
            status_code=500,
            detail={
                "error_type": "TEMPLATE_LIST_FAILED",
                "message": "Failed to retrieve templates",
                "details": str(exc)
            }
        ) from exc


@router.get("/{template_id}", response_model=TemplateResponse, status_code=HTTP_200_OK)
async def get_template(
    template_id: str = Path(..., description="Template ID"),
    include_definition: bool = Query(True, description="Include full template definition"),
    template_service: FlowTemplateService = Depends(get_flow_template_service),
) -> TemplateResponse:
    """Get a specific template by ID."""
    try:
        log.debug("Getting template: %s (include_definition=%s)", template_id, include_definition)
        
        # Get template from service
        template_data = await template_service.get_template(template_id)
        
        if not template_data:
            raise HTTPException(
                status_code=404,
                detail={
                    "error_type": "TEMPLATE_NOT_FOUND",
                    "message": f"Template {template_id} not found"
                }
            )
        
        # Extract template metadata directly from template_data
        name = template_data.get("name", template_id)
        description = template_data.get("description", "")
        processors = template_data.get("processors", [])
        connections = template_data.get("connections", [])
        parameters = template_data.get("parameters", {})
        
        # For now, set default values for new fields
        template_category = "general"
        template_tags = []
        usage_count = 0
        
        # Create flow definition if requested
        definition = None
        if include_definition:
            from src.models.v1.flows import FlowDefinition
            definition = FlowDefinition(
                name=name,
                description=description,
                processors=processors,
                connections=connections,
                process_groups=[]
            )
        
        return TemplateResponse(
            id=template_id,
            name=name,
            description=description,
            category=template_category,
            tags=template_tags,
            definition=definition,
            parameters=parameters,
            processor_count=len(processors),
            connection_count=len(connections), 
            parameter_count=len(parameters),
            usage_count=usage_count
        )
        
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("Failed to get template %s", template_id)
        raise HTTPException(
            status_code=500,
            detail={
                "error_type": "TEMPLATE_GET_FAILED",
                "message": "Failed to retrieve template",
                "details": str(exc)
            }
        ) from exc


@router.post("/{template_id}/validate", response_model=TemplateValidationResponse, status_code=HTTP_200_OK)
async def validate_template(
    validation_data: TemplateValidationRequest,
    template_id: str = Path(..., description="Template ID"),
    template_service: FlowTemplateService = Depends(get_flow_template_service),
) -> TemplateValidationResponse:
    """Validate a template definition."""
    try:
        log.debug("Validating template: %s (strict=%s)", template_id, validation_data.strict)
        
        # For now, perform basic validation
        errors = []
        warnings = []
        
        definition = validation_data.definition
        
        # Basic validation checks
        if not definition.name:
            errors.append("Template name is required")
        
        if not definition.processors:
            warnings.append("Template has no processors")
        
        if not definition.connections and len(definition.processors) > 1:
            warnings.append("Template has multiple processors but no connections")
        
        # Validate processor configurations
        for i, processor in enumerate(definition.processors):
            if not processor.get("type"):
                errors.append(f"Processor {i+1} is missing type")
            if not processor.get("identifier"):
                errors.append(f"Processor {i+1} is missing identifier")
        
        # Validate connections
        processor_ids = {p.get("identifier") for p in definition.processors if p.get("identifier")}
        for i, connection in enumerate(definition.connections):
            source_id = connection.get("source", {}).get("id")
            dest_id = connection.get("destination", {}).get("id")
            
            if source_id not in processor_ids:
                errors.append(f"Connection {i+1} references unknown source processor: {source_id}")
            if dest_id not in processor_ids:
                errors.append(f"Connection {i+1} references unknown destination processor: {dest_id}")
        
        # Additional strict validation
        if validation_data.strict:
            if not definition.description:
                errors.append("Template description is required in strict mode")
            
            # Check for required processor properties
            for i, processor in enumerate(definition.processors):
                if not processor.get("properties"):
                    warnings.append(f"Processor {i+1} has no properties configured")
        
        summary = {
            "total_processors": len(definition.processors),
            "total_connections": len(definition.connections),
            "validation_mode": "strict" if validation_data.strict else "basic",
            "error_count": len(errors),
            "warning_count": len(warnings)
        }
        
        return TemplateValidationResponse(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            summary=summary
        )
        
    except Exception as exc:
        log.exception("Failed to validate template %s", template_id)
        raise HTTPException(
            status_code=500,
            detail={
                "error_type": "TEMPLATE_VALIDATION_FAILED",
                "message": "Failed to validate template",
                "details": str(exc)
            }
        ) from exc