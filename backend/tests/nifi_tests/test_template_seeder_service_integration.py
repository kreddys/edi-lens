"""
Integration tests for Template Seeder Service with real NiFi instances.

These tests validate template seeding, initialization, and error recovery
scenarios against actual NiFi and database services.
"""

import pytest
import asyncio
import tempfile
import yaml
from pathlib import Path
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import text

from src.nifi.services.template_seeder_service import TemplateSeederService
from src.models.workflow_template import WorkflowTemplate, TemplateVersion
from src.core.config import settings


pytestmark = pytest.mark.integration


@pytest.fixture
def seeder_service(db_session: AsyncSession) -> TemplateSeederService:
    """Create template seeder service instance."""
    return TemplateSeederService(
        registry_url=settings.NIFI_REGISTRY_URL
    )


@pytest.fixture
def temp_template_directory():
    """Create temporary directory with test YAML templates."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create multiple test templates
        templates = [
            {
                "template_id": f"seeder-test-template-1-{uuid4()}",
                "name": "Seeder Test Template 1",
                "description": "First test template for seeder integration",
                "category": "BATCH",
                "scope": "GLOBAL",
                "tenant_id": None,
                "flow_definition": {},
                "configuration_schema": {},
            },
            {
                "template_id": f"seeder-test-template-2-{uuid4()}",
                "name": "Seeder Test Template 2",
                "description": "Second test template for seeder integration",
                "category": "REALTIME",
                "scope": "TENANT",
                "tenant_id": "tenant-seeder-test",
                "flow_definition": {},
                "configuration_schema": {},
            }
        ]
        
        # Write templates to YAML files
        for i, template in enumerate(templates):
            template_file = temp_path / f"template_{i+1}.yaml"
            with open(template_file, 'w') as f:
                yaml.dump(template, f)
        
        yield temp_path, templates


class TestTemplateSeederServiceIntegration:
    """Integration tests for Template Seeder Service with real services."""

    @pytest.mark.asyncio
    async def test_template_seeding_from_directory(self, seeder_service: TemplateSeederService, temp_template_directory, db_session: AsyncSession):
        """Test seeding templates from a directory of YAML files."""
        temp_path, expected_templates = temp_template_directory
        
        try:
            # Seed templates from directory
            seeding_result = await seeder_service.seed_templates_from_directory(
                session=db_session,
                templates_directory=str(temp_path),
            )
            
            # Verify seeding result structure
            assert isinstance(seeding_result, dict)
            assert "seeded" in seeding_result
            assert "skipped" in seeding_result
            assert "errors" in seeding_result
            assert "total_processed" in seeding_result
            
            # Verify successful seeding
            seeded_templates = seeding_result["seeded"]
            assert len(seeded_templates) == 2  # Two valid templates
            
            # Verify templates were created in database
            for expected_template in expected_templates:
                template_id = expected_template["template_id"]
                
                template_query = select(WorkflowTemplate).where(
                    WorkflowTemplate.template_id == template_id
                )
                result = await db_session.execute(template_query)
                saved_template = result.scalar_one_or_none()
                
                assert saved_template is not None
                assert saved_template.name == expected_template["name"]

        finally:
            # Cleanup
            for template in expected_templates:
                await db_session.execute(text(f"DELETE FROM template_versions WHERE template_id = '{template["template_id"]}'"))
                await db_session.execute(text(f"DELETE FROM workflow_templates WHERE template_id = '{template["template_id"]}'"))
            await db_session.commit()
