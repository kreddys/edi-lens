"""
API endpoints for Registry-first template management.
"""

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth import require_permission, AuthContext
from src.core.database import get_db
from src.services.registry_service import RegistryService, RegistryServiceError
from src.api.schemas import (
    RegistryTemplateResponse, RegistryTemplateCreateRequest, RegistryTemplateUpdateRequest,
    WorkflowInstanceResponse, WorkflowInstanceCreateRequest, FlowDefinitionResponse
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/registry-templates", tags=["Registry Templates"])


def create_workflow_response(workflow, include_template=False) -> WorkflowInstanceResponse:
    """Helper function to create WorkflowInstanceResponse manually to avoid SQLAlchemy serialization issues."""
    template_response = None
    
    if include_template:
        # Only try to include template if explicitly requested and template relationship is loaded
        try:
            # Check if the template attribute is loaded (not a lazy proxy)
            if hasattr(workflow, 'template') and workflow.template is not None:
                # Try to access template attributes, this will fail if not properly loaded
                _ = workflow.template.name  # Test access
                
                template_response = RegistryTemplateResponse(
                    template_id=workflow.template.template_id,
                    bucket_id=workflow.template.bucket_id,
                    current_version=workflow.template.current_version,
                    name=workflow.template.name,
                    description=workflow.template.description,
                    scope=workflow.template.scope,
                    tenant_id=workflow.template.tenant_id,
                    status=workflow.template.status,
                    is_featured=workflow.template.is_featured,
                    usage_count=workflow.template.usage_count,
                    created_by=workflow.template.created_by,
                    created_at=workflow.template.created_at,
                    updated_at=workflow.template.updated_at,
                    deprecated_at=workflow.template.deprecated_at
                )
        except Exception:
            # If template access fails, skip it
            template_response = None
    
    return WorkflowInstanceResponse(
        workflow_id=workflow.workflow_id,
        name=workflow.name,
        description=workflow.description,
        tenant_id=workflow.tenant_id,
        template_id=workflow.template_id,
        template_version=workflow.template_version,
        configuration=workflow.configuration,
        nifi_process_group_id=workflow.nifi_process_group_id,
        nifi_parameter_context_id=workflow.nifi_parameter_context_id,
        nifi_registry_client_id=workflow.nifi_registry_client_id,
        version_control_info=workflow.version_control_info,
        status=workflow.status,
        created_by=workflow.created_by,
        created_at=workflow.created_at,
        updated_at=workflow.updated_at,
        deployed_at=workflow.deployed_at,
        last_started_at=workflow.last_started_at,
        last_stopped_at=workflow.last_stopped_at,
        template=template_response
    )


@router.post("/", response_model=RegistryTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    template_data: RegistryTemplateCreateRequest,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(require_permission("workflow:write"))
):
    """Create a new template in NiFi Registry."""
    try:
        registry_service = RegistryService(session)
        
        # Determine scope and tenant_id based on user permissions
        scope = "GLOBAL" if "admin" in auth_context.roles else "TENANT"
        tenant_id = None if scope == "GLOBAL" else auth_context.tenant_id
        
        if scope == "TENANT" and not tenant_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tenant ID required for tenant-scoped templates"
            )
        
        template = await registry_service.create_template(
            name=template_data.name,
            description=template_data.description,
            flow_definition=template_data.flow_definition,
            scope=scope,
            tenant_id=tenant_id,
            created_by=auth_context.user_id
        )
        
        return RegistryTemplateResponse.from_orm(template)
        
    except RegistryServiceError as e:
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
        registry_service = RegistryService(session)
        
        # Determine what templates user can see
        if "admin" in auth_context.roles:
            # Admins can see all templates
            templates = await registry_service.list_templates(scope=scope)
        else:
            # Regular users can see global templates and their tenant templates
            global_templates = await registry_service.list_templates(scope="GLOBAL")
            tenant_templates = []
            
            if auth_context.tenant_id:
                tenant_templates = await registry_service.list_templates(
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


@router.get("/instances", response_model=List[WorkflowInstanceResponse])
async def list_workflow_instances(
    template_id: Optional[str] = None,
    status: Optional[str] = None,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(require_permission("workflow:read"))
):
    """List workflow instances accessible to the current user."""
    try:
        registry_service = RegistryService(session)
        
        # Convert template_id string to UUID if provided
        template_uuid = None
        if template_id:
            try:
                template_uuid = UUID(template_id)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid template_id format"
                )
        
        # Determine tenant filter
        if "admin" in auth_context.roles:
            tenant_filter = None  # Admins see all
        else:
            tenant_filter = auth_context.tenant_id
        
        workflows = await registry_service.list_workflow_instances(
            tenant_id=tenant_filter,
            template_id=template_uuid,
            status=status
        )
        
        return [create_workflow_response(workflow, include_template=True) for workflow in workflows]
        
    except Exception as e:
        log.error(f"Error listing workflow instances: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list workflow instances"
        )


@router.get("/{template_id}", response_model=RegistryTemplateResponse)
async def get_template(
    template_id: UUID,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(require_permission("workflow:read"))
):
    """Get template by ID."""
    try:
        registry_service = RegistryService(session)
        template = await registry_service.get_template(template_id)
        
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Template not found"
            )
        
        # Check access permissions
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
        registry_service = RegistryService(session)
        template = await registry_service.get_template(template_id)
        
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Template not found"
            )
        
        # Check modification permissions
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
        
        updated_template = await registry_service.update_template(
            template_id=template_id,
            flow_definition=update_data.flow_definition,
            comments=update_data.comments or "Updated via EDI Lens API",
            updated_by=auth_context.user_id
        )
        
        return RegistryTemplateResponse.from_orm(updated_template)
        
    except HTTPException:
        raise
    except RegistryServiceError as e:
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


@router.get("/{template_id}/flow-definition")
async def get_template_flow_definition(
    template_id: UUID,
    version: Optional[int] = None,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(require_permission("workflow:read"))
):
    """Get flow definition from Registry for a specific template version."""
    try:
        registry_service = RegistryService(session)
        template = await registry_service.get_template(template_id)
        
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Template not found"
            )
        
        # Check access permissions
        if template.scope == "TENANT":
            if template.tenant_id != auth_context.tenant_id and "admin" not in auth_context.roles:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied to this template"
                )
        
        flow_definition = await registry_service.get_template_flow_definition(
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
    except RegistryServiceError as e:
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


# === Workflow Instance Endpoints ===

@router.post("/{template_id}/instances", response_model=WorkflowInstanceResponse, status_code=status.HTTP_201_CREATED)
async def create_workflow_instance(
    template_id: UUID,
    instance_data: WorkflowInstanceCreateRequest,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(require_permission("workflow:write"))
):
    """Create a workflow instance from a template."""
    try:
        registry_service = RegistryService(session)
        
        # Get user's tenant
        if not auth_context.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User must belong to a tenant to create workflows"
            )
        
        workflow = await registry_service.create_workflow_instance(
            template_id=template_id,
            name=instance_data.name,
            tenant_id=auth_context.tenant_id,
            configuration=instance_data.configuration,
            description=instance_data.description,
            template_version=instance_data.template_version,
            created_by=auth_context.user_id
        )
        
        return create_workflow_response(workflow, include_template=False)
        
    except RegistryServiceError as e:
        log.error(f"Registry service error creating workflow instance: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    except Exception as e:
        log.error(f"Error creating workflow instance: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create workflow instance"
        )


@router.post("/instances/{workflow_id}/deploy", response_model=WorkflowInstanceResponse)
async def deploy_workflow_instance(
    workflow_id: UUID,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(require_permission("workflow:write"))
):
    """Deploy workflow instance to NiFi."""
    try:
        registry_service = RegistryService(session)
        
        # Check workflow exists and user has access
        workflow = await registry_service.get_workflow_instance(workflow_id)
        if not workflow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workflow instance not found"
            )
        
        if workflow.tenant_id != auth_context.tenant_id and "admin" not in auth_context.roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this workflow"
            )
        
        deployed_workflow = await registry_service.deploy_workflow_instance(workflow_id)
        
        return create_workflow_response(deployed_workflow, include_template=False)
        
    except HTTPException:
        raise
    except RegistryServiceError as e:
        log.error(f"Registry service error deploying workflow: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    except Exception as e:
        log.error(f"Error deploying workflow {workflow_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to deploy workflow"
        )



@router.get("/instances/{workflow_id}", response_model=WorkflowInstanceResponse)
async def get_workflow_instance(
    workflow_id: UUID,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(require_permission("workflow:read"))
):
    """Get workflow instance by ID."""
    try:
        registry_service = RegistryService(session)
        workflow = await registry_service.get_workflow_instance(workflow_id)
        
        if not workflow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workflow instance not found"
            )
        
        # Check access permissions
        if workflow.tenant_id != auth_context.tenant_id and "admin" not in auth_context.roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this workflow"
            )
        
        return create_workflow_response(workflow, include_template=True)
        
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error getting workflow instance {workflow_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get workflow instance"
        )