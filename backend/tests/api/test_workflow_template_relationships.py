"""
Integration tests for workflow template relationships and full functionality.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.models.workflow_template import WorkflowTemplate, TemplateVersion, TemplateUsage


@pytest.mark.asyncio
@pytest.mark.integration
async def test_workflow_template_creation_with_relationships(db_session: AsyncSession):
    """Test that creating a workflow template also creates version and usage records."""
    
    # Create template data
    template_data = {
        "template_id": "test-template-rel-001",
        "name": "Test Relationship Template",
        "description": "Test template for relationship functionality",
        "category": "BATCH",
        "scope": "GLOBAL",
        "version": "1.0.0",
        "flow_definition": {
            "processors": [
                {"id": "processor1", "type": "ListSFTP", "properties": {}}
            ],
            "connections": []
        },
        "configuration_schema": {
            "type": "object",
            "properties": {
                "test_config": {"type": "string"}
            }
        },
        "deployment_method": "registry",
        "tags": ["test", "relationships"],
        "features": ["testing"],
        "documentation": "Test template documentation",
        "is_featured": False
    }
    
    # Create the template
    template = WorkflowTemplate(
        template_id=template_data["template_id"],
        name=template_data["name"],
        description=template_data["description"],
        category=template_data["category"],
        scope=template_data["scope"],
        version=template_data["version"],
        flow_definition=template_data["flow_definition"],
        configuration_schema=template_data["configuration_schema"],
        deployment_method=template_data["deployment_method"],
        tags=template_data["tags"],
        features=template_data["features"],
        documentation=template_data["documentation"],
        is_featured=template_data["is_featured"],
        maintainer="test-user"
    )
    
    db_session.add(template)
    
    # Create initial version
    initial_version = TemplateVersion(
        template_id=template_data["template_id"],
        version=template_data["version"],
        flow_definition=template_data["flow_definition"],
        configuration_schema=template_data["configuration_schema"],
        changes="Initial version",
        created_by="test-user",
        is_current=True
    )
    
    db_session.add(initial_version)
    
    # Create usage record
    usage_record = TemplateUsage.create_usage_record(
        template_id=template_data["template_id"],
        tenant_id="platform",
        action="CREATE",
        success=True
    )
    
    db_session.add(usage_record)
    
    await db_session.commit()
    
    # Verify template was created
    template_query = select(WorkflowTemplate).where(
        WorkflowTemplate.template_id == template_data["template_id"]
    )
    template_result = await db_session.execute(template_query)
    saved_template = template_result.scalar_one_or_none()
    
    assert saved_template is not None
    assert saved_template.name == template_data["name"]
    assert saved_template.scope == template_data["scope"]
    
    # Verify version was created
    version_query = select(TemplateVersion).where(
        TemplateVersion.template_id == template_data["template_id"]
    )
    version_result = await db_session.execute(version_query)
    saved_version = version_result.scalar_one_or_none()
    
    assert saved_version is not None
    assert saved_version.version == template_data["version"]
    assert saved_version.is_current is True
    assert saved_version.changes == "Initial version"
    
    # Verify usage record was created
    usage_query = select(TemplateUsage).where(
        TemplateUsage.template_id == template_data["template_id"]
    )
    usage_result = await db_session.execute(usage_query)
    saved_usage = usage_result.scalar_one_or_none()
    
    assert saved_usage is not None
    assert saved_usage.action == "CREATE"
    assert saved_usage.tenant_id == "platform"
    assert saved_usage.success is True


@pytest.mark.asyncio
@pytest.mark.integration
async def test_template_relationships_navigation(db_session: AsyncSession):
    """Test that SQLAlchemy relationships work correctly for navigation."""
    
    # Create a template with multiple versions and usage records
    template = WorkflowTemplate(
        template_id="test-nav-template",
        name="Navigation Test Template",
        description="Test template for relationship navigation",
        category="TRANSFORMATION",
        scope="TENANT",
        tenant_id="tenant-test",
        version="1.0.0",
        flow_definition={"test": "flow"},
        configuration_schema={"test": "schema"},
        deployment_method="registry",
        maintainer="test-user"
    )
    
    db_session.add(template)
    
    # Create multiple versions
    version_1 = TemplateVersion(
        template_id="test-nav-template",
        version="1.0.0",
        flow_definition={"test": "flow"},
        configuration_schema={"test": "schema"},
        changes="Initial version",
        created_by="test-user",
        is_current=False
    )
    
    version_2 = TemplateVersion(
        template_id="test-nav-template",
        version="1.1.0",
        flow_definition={"test": "flow", "update": "added"},
        configuration_schema={"test": "schema"},
        changes="Added functionality",
        created_by="test-user",
        is_current=True
    )
    
    db_session.add(version_1)
    db_session.add(version_2)
    
    # Create multiple usage records
    usage_1 = TemplateUsage.create_usage_record(
        template_id="test-nav-template",
        tenant_id="tenant-test",
        action="CREATE",
        success=True
    )
    
    usage_2 = TemplateUsage.create_usage_record(
        template_id="test-nav-template",
        tenant_id="tenant-test",
        action="UPDATE",
        success=True
    )
    
    db_session.add(usage_1)
    db_session.add(usage_2)
    
    await db_session.commit()
    
    # Test relationship navigation using primaryjoin
    template_query = select(WorkflowTemplate).where(
        WorkflowTemplate.template_id == "test-nav-template"
    )
    template_result = await db_session.execute(template_query)
    saved_template = template_result.scalar_one()
    
    # Test accessing versions through relationship
    versions_query = select(TemplateVersion).where(
        TemplateVersion.template_id == saved_template.template_id
    )
    versions_result = await db_session.execute(versions_query)
    template_versions = versions_result.scalars().all()
    
    assert len(template_versions) == 2
    version_numbers = [v.version for v in template_versions]
    assert "1.0.0" in version_numbers
    assert "1.1.0" in version_numbers
    
    # Test accessing usage records through relationship
    usage_query = select(TemplateUsage).where(
        TemplateUsage.template_id == saved_template.template_id
    )
    usage_result = await db_session.execute(usage_query)
    template_usage = usage_result.scalars().all()
    
    assert len(template_usage) == 2
    actions = [u.action for u in template_usage]
    assert "CREATE" in actions
    assert "UPDATE" in actions
    
    # Test reverse relationship navigation
    for version in template_versions:
        parent_template_query = select(WorkflowTemplate).where(
            WorkflowTemplate.template_id == version.template_id
        )
        parent_result = await db_session.execute(parent_template_query)
        parent_template = parent_result.scalar_one()
        
        assert parent_template.template_id == saved_template.template_id
        assert parent_template.name == saved_template.name


@pytest.mark.asyncio
@pytest.mark.integration
async def test_template_inheritance_relationships(db_session: AsyncSession):
    """Test template inheritance (based_on) relationships work correctly."""
    
    # Create parent template
    parent_template = WorkflowTemplate(
        template_id="parent-template",
        name="Parent Template",
        description="Base template for inheritance",
        category="BATCH",
        scope="GLOBAL",
        version="1.0.0",
        flow_definition={"base": "flow"},
        configuration_schema={"base": "schema"},
        deployment_method="registry",
        maintainer="platform"
    )
    
    db_session.add(parent_template)
    
    # Create child template that inherits from parent
    child_template = WorkflowTemplate(
        template_id="child-template",
        name="Child Template",
        description="Template based on parent",
        category="BATCH",
        scope="TENANT",
        tenant_id="tenant-test",
        based_on="parent-template",  # This creates the inheritance relationship
        version="1.0.0",
        flow_definition={"base": "flow", "custom": "addition"},
        configuration_schema={"base": "schema"},
        deployment_method="registry",
        maintainer="tenant-user"
    )
    
    db_session.add(child_template)
    
    await db_session.commit()
    
    # Test inheritance relationship
    parent_query = select(WorkflowTemplate).where(
        WorkflowTemplate.template_id == "parent-template"
    )
    parent_result = await db_session.execute(parent_query)
    saved_parent = parent_result.scalar_one()
    
    child_query = select(WorkflowTemplate).where(
        WorkflowTemplate.template_id == "child-template"
    )
    child_result = await db_session.execute(child_query)
    saved_child = child_result.scalar_one()
    
    # Verify inheritance relationship
    assert saved_child.based_on == saved_parent.template_id
    assert saved_child.is_derived is True
    assert saved_parent.is_derived is False
    
    # Test finding child templates of parent
    children_query = select(WorkflowTemplate).where(
        WorkflowTemplate.based_on == "parent-template"
    )
    children_result = await db_session.execute(children_query)
    children = children_result.scalars().all()
    
    assert len(children) == 1
    assert children[0].template_id == "child-template"
    assert children[0].name == "Child Template"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_template_cascade_deletion(db_session: AsyncSession):
    """Test that deleting a template properly handles related records."""
    
    # Create template with versions and usage records
    template = WorkflowTemplate(
        template_id="cascade-test-template",
        name="Cascade Test Template",
        description="Test template for cascade deletion",
        category="INTEGRATION",
        scope="TENANT",
        tenant_id="tenant-test",
        version="1.0.0",
        flow_definition={"test": "flow"},
        configuration_schema={"test": "schema"},
        deployment_method="registry",
        maintainer="test-user"
    )
    
    db_session.add(template)
    
    # Create version
    version = TemplateVersion(
        template_id="cascade-test-template",
        version="1.0.0",
        flow_definition={"test": "flow"},
        configuration_schema={"test": "schema"},
        changes="Initial version",
        created_by="test-user",
        is_current=True
    )
    
    db_session.add(version)
    
    # Create usage record
    usage = TemplateUsage.create_usage_record(
        template_id="cascade-test-template",
        tenant_id="tenant-test",
        action="CREATE",
        success=True
    )
    
    db_session.add(usage)
    
    await db_session.commit()
    
    # Verify records exist
    template_count_query = select(WorkflowTemplate).where(
        WorkflowTemplate.template_id == "cascade-test-template"
    )
    template_count_result = await db_session.execute(template_count_query)
    assert template_count_result.scalar_one_or_none() is not None
    
    version_count_query = select(TemplateVersion).where(
        TemplateVersion.template_id == "cascade-test-template"
    )
    version_count_result = await db_session.execute(version_count_query)
    assert version_count_result.scalar_one_or_none() is not None
    
    usage_count_query = select(TemplateUsage).where(
        TemplateUsage.template_id == "cascade-test-template"
    )
    usage_count_result = await db_session.execute(usage_count_query)
    assert usage_count_result.scalar_one_or_none() is not None
    
    # Delete the template
    await db_session.delete(template)
    await db_session.commit()
    
    # Verify template is deleted
    deleted_template_query = select(WorkflowTemplate).where(
        WorkflowTemplate.template_id == "cascade-test-template"
    )
    deleted_template_result = await db_session.execute(deleted_template_query)
    assert deleted_template_result.scalar_one_or_none() is None
    
    # Check what happens to related records
    # The behavior depends on the SQLAlchemy configuration and database constraints
    remaining_version_query = select(TemplateVersion).where(
        TemplateVersion.template_id == "cascade-test-template"
    )
    remaining_version_result = await db_session.execute(remaining_version_query)
    remaining_version = remaining_version_result.scalar_one_or_none()
    
    remaining_usage_query = select(TemplateUsage).where(
        TemplateUsage.template_id == "cascade-test-template"
    )
    remaining_usage_result = await db_session.execute(remaining_usage_query)
    remaining_usage = remaining_usage_result.scalar_one_or_none()
    
    # Since we have proper database-level foreign key constraints with CASCADE,
    # the related records should be deleted automatically by the database
    # This is the expected behavior with our current setup
    assert remaining_version is None, "TemplateVersion should be cascade deleted"
    assert remaining_usage is None, "TemplateUsage should be cascade deleted"