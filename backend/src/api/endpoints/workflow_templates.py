"""
unAPI endpoints for workflow template management.
"""

from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, or_
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.future import select

from src.api.schemas import (
    TemplateCreate, TemplateUpdate, TemplateClone, TemplateResponse, TemplateListResponse,
    TemplateScope, TemplateCategory, TemplateStatus, TemplateVersionCreate, TemplateVersionResponse,
    TemplateExport, TemplateImport
)
from src.core.auth import get_current_user, require_permission, User, AuthContext
from src.core.database import get_db
from src.models.workflow_template import (
    WorkflowTemplate, TemplateVersion, TemplateUsage, Workflow
)

router = APIRouter(prefix="/workflow-templates", tags=["workflow-templates"])


# Template Management Endpoints

@router.get("/", response_model=TemplateListResponse)
async def list_templates(
    scope: Optional[TemplateScope] = Query(None, description="Filter by template scope"),
    category: Optional[TemplateCategory] = Query(None, description="Filter by category"),
    tags: Optional[List[str]] = Query(None, description="Filter by tags"),
    status: Optional[TemplateStatus] = Query(None, description="Filter by status"),
    featured_only: bool = Query(False, description="Show only featured templates"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    session: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(require_permission("edi:read"))
) -> TemplateListResponse:
    """
    List workflow templates with filtering and pagination.
    
    Returns global templates and tenant-specific templates for the current tenant.
    """
    query = select(WorkflowTemplate)
    
    # Build filter conditions
    conditions = []
    
    # Always include global templates
    global_condition = WorkflowTemplate.scope == 'GLOBAL'
    
    # Include tenant templates for the current tenant
    tenant_condition = and_(
        WorkflowTemplate.scope == 'TENANT',
        WorkflowTemplate.tenant_id == auth_context.tenant_id
    )
    conditions.append(or_(global_condition, tenant_condition))
    
    # Apply filters
    if scope:
        conditions.append(WorkflowTemplate.scope == scope.value)
    
    if category:
        conditions.append(WorkflowTemplate.category == category.value)
    
    if status:
        conditions.append(WorkflowTemplate.status == status.value)
    else:
        # Default to active templates only
        conditions.append(WorkflowTemplate.status == 'ACTIVE')
    
    if featured_only:
        conditions.append(WorkflowTemplate.is_featured == True)
    
    if tags:
        # Filter by templates that have any of the specified tags
        conditions.append(WorkflowTemplate.tags.overlap(tags))
    
    # Apply all conditions
    if conditions:
        query = query.where(and_(*conditions))
    
    # Add ordering
    query = query.order_by(
        WorkflowTemplate.is_featured.desc(),
        WorkflowTemplate.usage_count.desc(),
        WorkflowTemplate.created_at.desc()
    )
    
    # Count total for pagination
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await session.execute(count_query)
    total = total_result.scalar()
    
    # Apply pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    
    # Execute query
    result = await session.execute(query)
    templates = result.scalars().all()
    
    return TemplateListResponse(
        templates=[TemplateResponse.model_validate(template) for template in templates],
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: str,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(require_permission("edi:read"))
) -> TemplateResponse:
    """Get a specific template by ID."""
    query = select(WorkflowTemplate).where(WorkflowTemplate.template_id == template_id)
    
    result = await session.execute(query)
    template = result.scalar_one_or_none()
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template {template_id} not found"
        )
    
    # Check access permissions
    if template.scope == 'TENANT':
        if template.tenant_id != auth_context.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to tenant template"
            )
    
    return TemplateResponse.model_validate(template)


@router.post("/", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    template_data: TemplateCreate,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(require_permission("edi:write"))
) -> TemplateResponse:
    """Create a new workflow template."""
    
    # Validate tenant template permissions
    if template_data.scope == TemplateScope.TENANT:
        # Use tenant from auth context, not request
        template_data.tenant_id = auth_context.tenant_id
    elif template_data.scope == TemplateScope.GLOBAL:
        # Only platform services/superusers can create global templates
        if not auth_context.has_permission("admin"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only platform administrators can create global templates"
            )
        template_data.tenant_id = None
    
    # Generate template ID if not provided
    if not template_data.template_id:
        template_data.template_id = f"{template_data.scope.lower()}-{template_data.category.lower()}-{str(uuid4())[:8]}"
    
    # Check if template ID already exists
    existing_query = select(WorkflowTemplate).where(WorkflowTemplate.template_id == template_data.template_id)
    existing_result = await session.execute(existing_query)
    if existing_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Template {template_data.template_id} already exists"
        )
    
    # Validate parent template if specified
    if template_data.based_on:
        parent_query = select(WorkflowTemplate).where(WorkflowTemplate.template_id == template_data.based_on)
        parent_result = await session.execute(parent_query)
        parent_template = parent_result.scalar_one_or_none()
        
        if not parent_template:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Parent template {template_data.based_on} not found"
            )
        
        # Check access to parent template
        if parent_template.scope == 'TENANT' and parent_template.tenant_id != template_data.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to parent template"
            )
    
    # Create template
    template = WorkflowTemplate(
        template_id=template_data.template_id,
        name=template_data.name,
        description=template_data.description,
        category=template_data.category.value,
        scope=template_data.scope.value,
        tenant_id=template_data.tenant_id,
        maintainer=auth_context.user_id,
        based_on=template_data.based_on,
        version=template_data.version,
        flow_definition=template_data.flow_definition,
        configuration_schema=template_data.configuration_schema,
        deployment_method=template_data.deployment_method.value,
        tags=template_data.tags,
        features=template_data.features,
        documentation=template_data.documentation,
        examples=template_data.examples,
        is_featured=template_data.is_featured
    )
    
    session.add(template)
    
    # Create initial version
    initial_version = TemplateVersion(
        template_id=template_data.template_id,
        version=template_data.version,
        flow_definition=template_data.flow_definition,
        configuration_schema=template_data.configuration_schema,
        changes="Initial version",
        created_by=auth_context.user_id,
        is_current=True
    )
    
    session.add(initial_version)
    
    # Create usage record
    usage_record = TemplateUsage.create_usage_record(
        template_id=template_data.template_id,
        tenant_id=template_data.tenant_id or 'platform',
        action='CREATE',
        success=True
    )
    
    session.add(usage_record)
    
    await session.commit()
    await session.refresh(template)
    
    return TemplateResponse.model_validate(template)


@router.put("/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: str,
    template_data: TemplateUpdate,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(require_permission("edi:write"))
) -> TemplateResponse:
    """Update an existing workflow template."""
    
    # Get existing template
    query = select(WorkflowTemplate).where(WorkflowTemplate.template_id == template_id)
    result = await session.execute(query)
    template = result.scalar_one_or_none()
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template {template_id} not found"
        )
    
    # Check permissions
    if template.scope == 'TENANT':
        if template.tenant_id != auth_context.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot modify templates from other tenants"
            )
    elif template.scope == 'GLOBAL':
        if not auth_context.has_permission("admin"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only platform administrators can modify global templates"
            )
    
    # Update fields
    update_data = template_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if hasattr(template, field):
            # Handle enum values
            if field in ['status'] and hasattr(value, 'value'):
                value = value.value
            setattr(template, field, value)
    
    # Create usage record
    usage_record = TemplateUsage.create_usage_record(
        template_id=template_id,
        tenant_id=auth_context.tenant_id,
        action='UPDATE',
        success=True
    )
    
    session.add(usage_record)
    
    await session.commit()
    await session.refresh(template)
    
    return TemplateResponse.model_validate(template)


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: str,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(require_permission("edi:write"))
):
    """Delete a workflow template."""
    
    # Get existing template
    query = select(WorkflowTemplate).where(WorkflowTemplate.template_id == template_id)
    result = await session.execute(query)
    template = result.scalar_one_or_none()
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template {template_id} not found"
        )
    
    # Check permissions
    if template.scope == 'TENANT':
        if template.tenant_id != auth_context.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot delete templates from other tenants"
            )
    elif template.scope == 'GLOBAL':
        if not auth_context.has_permission("admin"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only platform administrators can delete global templates"
            )
    
    # Check if template is in use by workflows
    workflow_query = select(func.count(Workflow.workflow_id)).where(
        and_(
            Workflow.template_id == template_id,
            Workflow.status.in_(['ACTIVE', 'PAUSED'])
        )
    )
    workflow_result = await session.execute(workflow_query)
    active_workflows = workflow_result.scalar()
    
    if active_workflows > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot delete template with {active_workflows} active workflows. Stop workflows first."
        )
    
    # Check if template is used as parent by other templates
    child_query = select(func.count(WorkflowTemplate.template_id)).where(
        WorkflowTemplate.based_on == template_id
    )
    child_result = await session.execute(child_query)
    child_templates = child_result.scalar()
    
    if child_templates > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot delete template that is used as parent by {child_templates} other templates"
        )
    
    # Create usage record
    usage_record = TemplateUsage.create_usage_record(
        template_id=template_id,
        tenant_id=auth_context.tenant_id,
        action='DELETE',
        success=True
    )
    
    session.add(usage_record)
    
    # Delete template (cascade will handle versions and usage records)
    await session.delete(template)
    await session.commit()


@router.post("/clone", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def clone_template(
    clone_data: TemplateClone,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(require_permission("edi:write"))
) -> TemplateResponse:
    """Clone an existing template with optional customizations."""
    
    # Get source template
    source_query = select(WorkflowTemplate).where(
        WorkflowTemplate.template_id == clone_data.source_template_id
    )
    source_result = await session.execute(source_query)
    source_template = source_result.scalar_one_or_none()
    
    if not source_template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source template {clone_data.source_template_id} not found"
        )
    
    # Check access to source template
    if source_template.scope == 'TENANT':
        if source_template.tenant_id != auth_context.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to source template"
            )
    
    # Prepare new template data starting from source template
    new_template_data = TemplateCreate(
        name=clone_data.new_template.name,
        description=clone_data.new_template.description or source_template.description,
        category=clone_data.new_template.category,
        scope=clone_data.new_template.scope,
        tenant_id=clone_data.new_template.tenant_id,
        based_on=clone_data.source_template_id,
        version=clone_data.new_template.version,
        flow_definition=source_template.flow_definition.copy(),
        configuration_schema=source_template.configuration_schema.copy(),
        deployment_method=clone_data.new_template.deployment_method,
        tags=clone_data.new_template.tags or source_template.tags,
        features=clone_data.new_template.features or source_template.features,
        documentation=clone_data.new_template.documentation or source_template.documentation,
        examples=clone_data.new_template.examples or source_template.examples,
        is_featured=clone_data.new_template.is_featured
    )
    
    # Apply customizations if provided
    if clone_data.customizations:
        # Apply flow definition customizations
        if 'flow_definition_updates' in clone_data.customizations:
            # Deep merge flow definition updates
            flow_def = new_template_data.flow_definition
            updates = clone_data.customizations['flow_definition_updates']
            if isinstance(updates, dict):
                flow_def.update(updates)
                new_template_data.flow_definition = flow_def
        
        # Apply configuration schema customizations
        if 'configuration_schema_updates' in clone_data.customizations:
            # Deep merge schema updates
            schema = new_template_data.configuration_schema
            updates = clone_data.customizations['configuration_schema_updates']
            if isinstance(updates, dict):
                schema.update(updates)
                new_template_data.configuration_schema = schema
        
        # Apply metadata customizations
        if 'add_tags' in clone_data.customizations:
            existing_tags = new_template_data.tags or []
            new_tags = clone_data.customizations['add_tags']
            if isinstance(new_tags, list):
                new_template_data.tags = list(set(existing_tags + new_tags))
        
        if 'add_features' in clone_data.customizations:
            existing_features = new_template_data.features or []
            new_features = clone_data.customizations['add_features']
            if isinstance(new_features, list):
                new_template_data.features = list(set(existing_features + new_features))
    
    # Create the cloned template using the create logic
    return await create_template(new_template_data, session, auth_context)



# Template Version Management

@router.get("/{template_id}/versions", response_model=List[TemplateVersionResponse])
async def list_template_versions(
    template_id: str,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(require_permission("edi:read"))
) -> List[TemplateVersionResponse]:
    """List all versions of a specific template."""
    
    # Get the template to ensure it exists and user has access
    template = await get_template(template_id, session, auth_context)
    
    query = select(TemplateVersion).where(
        TemplateVersion.template_id == template_id
    ).order_by(TemplateVersion.created_at.desc())
    
    result = await session.execute(query)
    versions = result.scalars().all()
    
    return [TemplateVersionResponse.model_validate(v) for v in versions]


@router.post("/{template_id}/versions", response_model=TemplateVersionResponse, status_code=status.HTTP_201_CREATED)
async def create_template_version(
    template_id: str,
    version_data: TemplateVersionCreate,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(require_permission("edi:write"))
) -> TemplateVersionResponse:
    """Create a new version of a template."""
    
    # Get the template to ensure it exists and user has access
    template = await get_template(template_id, session, auth_context)
    
    # Check if version already exists
    existing_version_query = select(TemplateVersion).where(
        and_(
            TemplateVersion.template_id == template_id,
            TemplateVersion.version == version_data.version
        )
    )
    existing_version_result = await session.execute(existing_version_query)
    if existing_version_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Version {version_data.version} for template {template_id} already exists"
        )
    
    # Set all other versions to not be current
    await session.execute(
        sa.update(TemplateVersion)
        .where(TemplateVersion.template_id == template_id)
        .values(is_current=False)
    )
    
    # Create new version
    new_version = TemplateVersion(
        template_id=template_id,
        version=version_data.version,
        changes=version_data.changes,
        flow_definition=version_data.flow_definition,
        configuration_schema=version_data.configuration_schema,
        created_by=auth_context.user_id,
        is_current=True
    )
    
    session.add(new_version)
    
    # Update the main template to the new version
    template.version = new_version.version
    template.flow_definition = new_version.flow_definition
    template.configuration_schema = new_version.configuration_schema
    
    await session.commit()
    await session.refresh(new_version)
    
    return TemplateVersionResponse.model_validate(new_version)

# TODO: Implement additional endpoints incrementally:
# - GET /{template_id}/export (export template)
# - POST /import (import template)
# - Workflow management endpoints


# Template Import/Export

@router.get("/{template_id}/export", response_model=TemplateExport)
async def export_template(
    template_id: str,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(require_permission("edi:read"))
) -> TemplateExport:
    """Export a template and all its versions."""
    
    template = await get_template(template_id, session, auth_context)
    
    versions_query = select(TemplateVersion).where(
        TemplateVersion.template_id == template_id
    ).order_by(TemplateVersion.created_at.asc())
    
    versions_result = await session.execute(versions_query)
    versions = versions_result.scalars().all()
    
    export_data = TemplateExport(
        template=TemplateResponse.model_validate(template),
        versions=[TemplateVersionResponse.model_validate(v) for v in versions],
        metadata={
            "exported_at": datetime.utcnow().isoformat(),
            "exported_by": auth_context.user_id
        }
    )
    
    return export_data


@router.post("/import", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def import_template(
    import_data: TemplateImport,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(require_permission("edi:write"))
) -> TemplateResponse:
    """Import a template from an exported JSON object."""
    
    template_data = TemplateCreate(**import_data.template_data['template'])
    
    # Handle import options
    if import_data.import_options.get('assign_new_id', False):
        template_data.template_id = None # Let create_template generate a new ID
    
    if import_data.import_options.get('overwrite_existing', False):
        existing_template = await session.get(WorkflowTemplate, template_data.template_id)
        if existing_template:
            await session.delete(existing_template)
            await session.commit()

    # Create the template
    created_template = await create_template(template_data, session, auth_context)
    
    # Import versions
    if 'versions' in import_data.template_data:
        for version_data in import_data.template_data['versions']:
            # Don't re-create the initial version
            if version_data['version'] == created_template.version:
                continue

            version_create = TemplateVersionCreate(**version_data)
            await create_template_version(
                created_template.template_id,
                version_create,
                session,
                auth_context
            )
            
    await session.refresh(created_template)
    return created_template
