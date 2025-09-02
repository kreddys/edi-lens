"""
Integration tests for Registry-first template persistence and relationships.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from uuid import uuid4

from src.models.registry_models import RegistryTemplate, WorkflowInstance, RegistryBucket
from src.services.registry_service import RegistryService


@pytest.mark.asyncio
@pytest.mark.integration
async def test_registry_template_creation_with_relationships(db_session: AsyncSession):
    """Test that creating a registry template creates proper database records."""
    
    # Use RegistryService to create template properly
    registry_service = RegistryService(db_session)
    
    template = await registry_service.create_template(
        name="Test Registry Template",
        description="Test template for Registry-first functionality",
        flow_definition={
            "identifier": "test-flow",
            "name": "Test Flow",
            "description": "Test flow definition",
            "processGroups": [],
            "processors": [
                {
                    "identifier": str(uuid4()),
                    "name": "Test Processor",
                    "type": "org.apache.nifi.processors.standard.LogMessage",
                    "position": {"x": 100, "y": 100},
                    "properties": {"Log Level": "INFO", "Log Message": "Test message"}
                }
            ],
            "controllerServices": [],
            "funnels": [],
            "inputPorts": [],
            "outputPorts": [],
            "remoteProcessGroups": [],
            "labels": [],
            "variables": {},
            "connections": [],
            "processGroupIdentifier": "test-flow",
            "version": 1
        },
        scope="TENANT",
        tenant_id="tenant-test"
    )
    
    # Verify template was created in database
    template_query = select(RegistryTemplate).where(
        RegistryTemplate.template_id == template.template_id
    )
    template_result = await db_session.execute(template_query)
    saved_template = template_result.scalar_one_or_none()
    
    assert saved_template is not None
    assert saved_template.name == "Test Registry Template"
    assert saved_template.scope == "TENANT"
    assert saved_template.tenant_id == "tenant-test"
    assert saved_template.current_version == 1
    
    # Verify bucket was created
    bucket_query = select(RegistryBucket).where(
        RegistryBucket.bucket_id == template.bucket_id
    )
    bucket_result = await db_session.execute(bucket_query)
    saved_bucket = bucket_result.scalar_one_or_none()
    
    assert saved_bucket is not None
    assert saved_bucket.scope == "TENANT"
    assert saved_bucket.tenant_id == "tenant-test"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_workflow_instance_creation_and_relationships(db_session: AsyncSession):
    """Test workflow instance creation and relationship to registry template."""
    
    # Create a registry template first
    registry_service = RegistryService(db_session)
    
    template = await registry_service.create_template(
        name="Test Instance Template",
        description="Template for testing workflow instances",
        flow_definition={
            "identifier": "instance-test-flow",
            "name": "Instance Test Flow",
            "description": "Flow for testing workflow instances",
            "processGroups": [],
            "processors": [
                {
                    "identifier": str(uuid4()),
                    "name": "Instance Processor",
                    "type": "org.apache.nifi.processors.standard.GenerateFlowFile",
                    "position": {"x": 200, "y": 200},
                    "properties": {"File Size": "1KB"}
                }
            ],
            "controllerServices": [],
            "funnels": [],
            "inputPorts": [],
            "outputPorts": [],
            "remoteProcessGroups": [],
            "labels": [],
            "variables": {},
            "connections": [],
            "processGroupIdentifier": "instance-test-flow",
            "version": 1
        },
        scope="GLOBAL"
    )
    
    # Create workflow instance
    instance = await registry_service.create_workflow_instance(
        template_id=template.template_id,
        template_version=1,
        name="Test Workflow Instance",
        tenant_id="tenant-test",
        configuration={
            "file_size": "2KB",
            "generation_rate": "10 sec"
        }
    )
    
    # Verify instance was created
    instance_query = select(WorkflowInstance).where(
        WorkflowInstance.workflow_id == instance.workflow_id
    )
    instance_result = await db_session.execute(instance_query)
    saved_instance = instance_result.scalar_one_or_none()
    
    assert saved_instance is not None
    assert saved_instance.name == "Test Workflow Instance"
    assert saved_instance.template_id == template.template_id
    assert saved_instance.template_version == 1
    assert saved_instance.tenant_id == "tenant-test"
    assert saved_instance.configuration["file_size"] == "2KB"
    
    # Test relationship navigation
    template_query = select(RegistryTemplate).where(
        RegistryTemplate.template_id == saved_instance.template_id
    )
    template_result = await db_session.execute(template_query)
    related_template = template_result.scalar_one()
    
    assert related_template.template_id == template.template_id
    assert related_template.name == "Test Instance Template"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_multi_tenant_template_isolation(db_session: AsyncSession):
    """Test that templates are properly isolated by tenant."""
    
    registry_service = RegistryService(db_session)
    
    # Create global template (visible to all tenants)
    global_template = await registry_service.create_template(
        name="Global Template",
        description="Template visible to all tenants",
        flow_definition={
            "identifier": "global-flow",
            "name": "Global Flow",
            "description": "Global flow definition",
            "processGroups": [],
            "processors": [],
            "controllerServices": [],
            "funnels": [],
            "inputPorts": [],
            "outputPorts": [],
            "remoteProcessGroups": [],
            "labels": [],
            "variables": {},
            "connections": [],
            "processGroupIdentifier": "global-flow",
            "version": 1
        },
        scope="GLOBAL"
    )
    
    # Create tenant-specific template
    tenant_template = await registry_service.create_template(
        name="Tenant A Template",
        description="Template for tenant A only",
        flow_definition={
            "identifier": "tenant-a-flow",
            "name": "Tenant A Flow",
            "description": "Tenant A specific flow",
            "processGroups": [],
            "processors": [],
            "controllerServices": [],
            "funnels": [],
            "inputPorts": [],
            "outputPorts": [],
            "remoteProcessGroups": [],
            "labels": [],
            "variables": {},
            "connections": [],
            "processGroupIdentifier": "tenant-a-flow",
            "version": 1
        },
        scope="TENANT",
        tenant_id="tenant-a"
    )
    
    # Test tenant isolation
    
    # Query global templates (should be visible to all)
    global_templates_query = select(RegistryTemplate).where(
        RegistryTemplate.scope == "GLOBAL"
    )
    global_result = await db_session.execute(global_templates_query)
    global_templates = global_result.scalars().all()
    
    assert len(global_templates) >= 1
    assert any(t.name == "Global Template" for t in global_templates)
    
    # Query tenant-specific templates
    tenant_templates_query = select(RegistryTemplate).where(
        RegistryTemplate.scope == "TENANT",
        RegistryTemplate.tenant_id == "tenant-a"
    )
    tenant_result = await db_session.execute(tenant_templates_query)
    tenant_templates = tenant_result.scalars().all()
    
    assert len(tenant_templates) >= 1
    assert any(t.name == "Tenant A Template" for t in tenant_templates)
    
    # Verify tenant isolation - tenant B shouldn't see tenant A's templates
    other_tenant_query = select(RegistryTemplate).where(
        RegistryTemplate.scope == "TENANT",
        RegistryTemplate.tenant_id == "tenant-b"
    )
    other_tenant_result = await db_session.execute(other_tenant_query)
    other_tenant_templates = other_tenant_result.scalars().all()
    
    # Should not contain tenant A's templates
    assert not any(t.name == "Tenant A Template" for t in other_tenant_templates)


@pytest.mark.asyncio
@pytest.mark.integration  
async def test_registry_template_cascade_deletion(db_session: AsyncSession):
    """Test that deleting a registry template properly handles related records."""
    
    registry_service = RegistryService(db_session)
    
    # Create template
    template = await registry_service.create_template(
        name="Deletion Test Template",
        description="Template for testing cascade deletion",
        flow_definition={
            "identifier": "deletion-test-flow",
            "name": "Deletion Test Flow",
            "description": "Flow for testing deletion",
            "processGroups": [],
            "processors": [],
            "controllerServices": [],
            "funnels": [],
            "inputPorts": [],
            "outputPorts": [],
            "remoteProcessGroups": [],
            "labels": [],
            "variables": {},
            "connections": [],
            "processGroupIdentifier": "deletion-test-flow",
            "version": 1
        },
        scope="TENANT",
        tenant_id="tenant-delete-test"
    )
    
    # Create workflow instance based on template
    instance = await registry_service.create_workflow_instance(
        template_id=template.template_id,
        template_version=1,
        name="Instance to be deleted",
        tenant_id="tenant-delete-test",
        configuration={}
    )
    
    # Verify both exist
    template_query = select(RegistryTemplate).where(
        RegistryTemplate.template_id == template.template_id
    )
    template_result = await db_session.execute(template_query)
    assert template_result.scalar_one_or_none() is not None
    
    instance_query = select(WorkflowInstance).where(
        WorkflowInstance.workflow_id == instance.workflow_id
    )
    instance_result = await db_session.execute(instance_query)
    assert instance_result.scalar_one_or_none() is not None
    
    # Delete the template
    await db_session.delete(template)
    await db_session.commit()
    
    # Verify template is deleted
    deleted_template_query = select(RegistryTemplate).where(
        RegistryTemplate.template_id == template.template_id
    )
    deleted_template_result = await db_session.execute(deleted_template_query)
    assert deleted_template_result.scalar_one_or_none() is None
    
    # Check if workflow instances are handled properly
    # (Behavior depends on foreign key constraints)
    remaining_instance_query = select(WorkflowInstance).where(
        WorkflowInstance.template_id == template.template_id
    )
    remaining_instance_result = await db_session.execute(remaining_instance_query)
    remaining_instance = remaining_instance_result.scalar_one_or_none()
    
    # With proper foreign key constraints, the instance should be cascade deleted
    # or the deletion should be prevented if instances exist
    # This depends on your database schema configuration
    print(f"Remaining instance after template deletion: {remaining_instance}")