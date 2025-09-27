"""API routes for flow template management."""

from __future__ import annotations

from typing import Dict, List, Any, Optional

from fastapi import APIRouter, HTTPException, Path, Query
from starlette.status import HTTP_200_OK, HTTP_404_NOT_FOUND

from fastapi import Depends

from src.api.dependencies import get_flow_template_service
from src.services.flow_template_service import FlowTemplateService
from src.core.logging import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/api/flows/templates", tags=["templates"])


@router.get("/", response_model=List[Dict[str, Any]], status_code=HTTP_200_OK)
async def list_templates(
    template_service: FlowTemplateService = Depends(get_flow_template_service),
) -> List[Dict[str, Any]]:
    """
    List all available flow templates with metadata.
    
    Returns:
        List of template metadata including name, description, component counts
    """
    try:
        templates = await template_service.list_templates()
        log.debug("Found %d templates", len(templates))
        return templates
    except Exception as exc:
        log.error("Failed to list templates: %s", exc)
        raise HTTPException(
            status_code=500,
            detail={
                "error_type": "TEMPLATE_LIST_FAILED",
                "user_message": "Failed to retrieve template list",
                "action_required": "Please try again or contact support",
            },
        ) from exc


@router.get("/{template_name}", response_model=Dict[str, Any], status_code=HTTP_200_OK)
async def get_template(
    template_name: str = Path(..., description="Template name (without .json extension)"),
    validate: bool = Query(False, description="Whether to validate the template structure"),
    template_service: FlowTemplateService = Depends(get_flow_template_service),
) -> Dict[str, Any]:
    """
    Get a specific flow template by name.
    
    Args:
        template_name: Name of the template file (without .json extension)
        validate: Whether to validate the template structure
        
    Returns:
        Complete template definition ready for use in flow designer
    """
    try:
        template_data = await template_service.get_template(template_name)
        
        if not template_data:
            raise HTTPException(
                status_code=HTTP_404_NOT_FOUND,
                detail={
                    "error_type": "TEMPLATE_NOT_FOUND",
                    "user_message": f"Template '{template_name}' not found",
                    "action_required": "Check the template name and try again",
                },
            )

        response = {
            "template_name": template_name,
            "template_data": template_data,
        }

        # Optional validation
        if validate:
            validation_result = await template_service.validate_template(template_data)
            response["validation"] = validation_result

        log.debug("Retrieved template: %s", template_name)
        return response

    except HTTPException:
        raise
    except Exception as exc:
        log.error("Failed to get template %s: %s", template_name, exc)
        raise HTTPException(
            status_code=500,
            detail={
                "error_type": "TEMPLATE_GET_FAILED",
                "user_message": f"Failed to retrieve template '{template_name}'",
                "action_required": "Please try again or contact support",
            },
        ) from exc


@router.post("/{template_name}/validate", response_model=Dict[str, Any], status_code=HTTP_200_OK)
async def validate_template(
    template_name: str = Path(..., description="Template name to validate"),
    template_service: FlowTemplateService = Depends(get_flow_template_service),
) -> Dict[str, Any]:
    """
    Validate a specific template structure.
    
    Args:
        template_name: Name of the template to validate
        
    Returns:
        Validation results with errors, warnings, and statistics
    """
    try:
        template_data = await template_service.get_template(template_name)
        
        if not template_data:
            raise HTTPException(
                status_code=HTTP_404_NOT_FOUND,
                detail={
                    "error_type": "TEMPLATE_NOT_FOUND",
                    "user_message": f"Template '{template_name}' not found",
                    "action_required": "Check the template name and try again",
                },
            )

        validation_result = await template_service.validate_template(template_data)
        
        log.debug("Validated template %s: %s", template_name, 
                 "valid" if validation_result["valid"] else "invalid")
        
        return {
            "template_name": template_name,
            "validation": validation_result,
        }

    except HTTPException:
        raise
    except Exception as exc:
        log.error("Failed to validate template %s: %s", template_name, exc)
        raise HTTPException(
            status_code=500,
            detail={
                "error_type": "TEMPLATE_VALIDATION_FAILED",
                "user_message": f"Failed to validate template '{template_name}'",
                "action_required": "Please try again or contact support",
            },
        ) from exc