"""
API endpoints for Registry template management.
"""

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth import require_permission, AuthContext
from src.core.database import get_db
from src.services.template_service import TemplateService, TemplateServiceError
from src.api.schemas import (
    RegistryTemplateResponse, RegistryTemplateCreateRequest, RegistryTemplateUpdateRequest
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/templates", tags=["Templates"])


@router.post("/", response_model=RegistryTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    template_data: RegistryTemplateCreateRequest,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(require_permission("workflow:write"))
):
    """Create a new template in NiFi Registry."""
    try:
        template_service = TemplateService(session)
        
        scope = "GLOBAL" if "admin" in auth_context.roles else "TENANT"
        tenant_id = None if scope == "GLOBAL" else auth_context.tenant_id
        
        if scope == "TENANT" and not tenant_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tenant ID required for tenant-scoped templates"
            )
        
        template = await template_service.create_template(
            name=template_data.name,
            description=template_data.description,
            flow_definition=template_data.flow_definition,
            scope=scope,
            tenant_id=tenant_id,
            created_by=auth_context.user_id
        )
        
        return RegistryTemplateResponse.from_orm(template)
        
    except TemplateServiceError as e:
        log.error(f"Registry service error creating template: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    except Exception as e:
        log.error(f"Unexpected error creating template: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create template"
        )


@router.get("/", response_model=List[RegistryTemplateResponse])
async def list_templates(
    scope: Optional[str] = None,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(require_permission("workflow:read"))
):
    """List templates accessible to the current user."""
    try:
        template_service = TemplateService(session)
        
        if "admin" in auth_context.roles:
            templates = await template_service.list_templates(scope=scope)
        else:
            global_templates = await template_service.list_templates(scope="GLOBAL")
            tenant_templates = []
            if auth_context.tenant_id:
                tenant_templates = await template_service.list_templates(
                    scope="TENANT", 
                    tenant_id=auth_context.tenant_id
                )
            templates = global_templates + tenant_templates
        
        return [RegistryTemplateResponse.from_orm(template) for template in templates]
        
    except Exception as e:
        log.error(f"Error listing templates: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list templates"
        )


@router.post("/seed", status_code=status.HTTP_200_OK)
async def seed_templates(
    session: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(require_permission("admin"))
):
    """Seed built-in templates into the database."""
    try:
        template_service = TemplateService(session)
        result = await template_service.seed_templates()
        return result
    except TemplateServiceError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/{template_id}", response_model=RegistryTemplateResponse)
async def get_template(
    template_id: UUID,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(require_permission("workflow:read"))
):
    """Get template by ID."""
    try:
        template_service = TemplateService(session)
        template = await template_service.get_template(template_id)
        
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Template not found"
            )
        
        if template.scope == "TENANT":
            if template.tenant_id != auth_context.tenant_id and "admin" not in auth_context.roles:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied to this template"
                )
        
        return RegistryTemplateResponse.from_orm(template)
        
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error getting template {template_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get template"
        )


@router.put("/{template_id}", response_model=RegistryTemplateResponse)
async def update_template(
    template_id: UUID,
    update_data: RegistryTemplateUpdateRequest,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(require_permission("workflow:write"))
):
    """Update template by creating a new version in Registry."""
    try:
        template_service = TemplateService(session)
        template = await template_service.get_template(template_id)
        
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Template not found"
            )
        
        if template.scope == "GLOBAL" and "admin" not in auth_context.roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can modify global templates"
            )
        
        if template.scope == "TENANT":
            if template.tenant_id != auth_context.tenant_id and "admin" not in auth_context.roles:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied to modify this template"
                )
        
        updated_template = await template_service.update_template(
            template_id=template_id,
            flow_definition=update_data.flow_definition,
            comments=update_data.comments or "Updated via EDI Lens API"
        )
        
        return RegistryTemplateResponse.from_orm(updated_template)
        
    except HTTPException:
        raise
    except TemplateServiceError as e:
        log.error(f"Registry service error updating template: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    except Exception as e:
        log.error(f"Error updating template {template_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update template"
        )


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: UUID,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(require_permission("workflow:write"))
):
    """Delete template by marking it as inactive."""
    try:
        template_service = TemplateService(session)
        template = await template_service.get_template(template_id)
        
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Template not found"
            )
        
        if template.scope == "GLOBAL" and "admin" not in auth_context.roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can delete global templates"
            )
        
        if template.scope == "TENANT":
            if template.tenant_id != auth_context.tenant_id and "admin" not in auth_context.roles:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied to delete this template"
                )
        
        success = await template_service.delete_template(template_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Template not found"
            )
        
        return None  # 204 No Content
        
    except HTTPException:
        raise
    except TemplateServiceError as e:
        log.error(f"Registry service error deleting template: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    except Exception as e:
        log.error(f"Error deleting template {template_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete template"
        )


@router.get("/{template_id}/flow-definition")
async def get_template_flow_definition(
    template_id: UUID,
    version: Optional[int] = None,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(require_permission("workflow:read"))
):
    """Get flow definition from Registry for a specific template version."""
    try:
        template_service = TemplateService(session)
        template = await template_service.get_template(template_id)
        
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Template not found"
            )
        
        if template.scope == "TENANT":
            if template.tenant_id != auth_context.tenant_id and "admin" not in auth_context.roles:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied to this template"
                )
        
        flow_definition = await template_service.get_template_flow_definition(
            template_id=template_id,
            version=version
        )
        
        return {
            "template_id": str(template_id),
            "version": version or template.current_version,
            "flow_definition": flow_definition
        }
        
    except HTTPException:
        raise
    except TemplateServiceError as e:
        log.error(f"Registry service error getting flow definition: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    except Exception as e:
        log.error(f"Error getting flow definition for template {template_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get flow definition"
        )
