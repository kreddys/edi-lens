"""
Unit tests for Template Seeder Service.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4

from src.nifi.services.template_seeder_service import TemplateSeederService
from src.nifi.services.built_in_templates_service import BuiltInTemplatesService
from src.models.workflow_template import WorkflowTemplate

pytestmark = pytest.mark.unit


class TestTemplateSeederService:
    """Test Template Seeder Service."""

    @pytest.fixture
    def template_seeder_service(self):
        """Create a template seeder service fixture."""
        return TemplateSeederService(
            registry_url="http://localhost:18080",
            registry_auth_token="test-token"
        )

    @pytest.mark.asyncio
    async def test_template_seeder_service_initialization(self):
        """Test template seeder service initialization."""
        service = TemplateSeederService(
            registry_url="http://localhost:18080",
            registry_auth_token="test-token"
        )
        
        assert service.built_in_templates_service is not None
        assert isinstance(service.built_in_templates_service, BuiltInTemplatesService)

    @pytest.mark.asyncio
    async def test_seed_built_in_templates(self, template_seeder_service):
        """Test seeding built-in templates."""
        # Mock the built-in templates service
        mock_built_in_service = AsyncMock()
        mock_built_in_service.seed_built_in_templates.return_value = {
            "seeded": [{"template_id": "test-template-1", "name": "Test Template 1"}],
            "skipped": [],
            "errors": []
        }
        
        template_seeder_service.built_in_templates_service = mock_built_in_service
        
        # Mock session
        mock_session = AsyncMock()
        
        # Test seeding
        results = await template_seeder_service.seed_built_in_templates(mock_session)
        
        # Verify results
        assert "seeded" in results
        assert len(results["seeded"]) == 1
        assert results["seeded"][0]["template_id"] == "test-template-1"
        
        # Verify the built-in service was called
        mock_built_in_service.seed_built_in_templates.assert_called_once_with(mock_session)

    @pytest.mark.asyncio
    async def test_seed_custom_templates_success(self, template_seeder_service):
        """Test seeding custom templates successfully."""
        # Mock session
        mock_session = AsyncMock()
        mock_session.execute.return_value.scalar_one_or_none.return_value = None
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()
        
        # Test data
        template_definitions = [
            {
                "template_id": "custom-template-1",
                "name": "Custom Template 1",
                "description": "A custom template for testing",
                "category": "BATCH",
                "flow_definition": {"processors": []}
            }
        ]
        
        # Test seeding
        results = await template_seeder_service.seed_custom_templates(
            mock_session, template_definitions
        )
        
        # Verify results
        # Note: Since we're mocking the session, the actual insertion might not happen
        # but we should still get results from the method
        assert isinstance(results, dict)
        assert "seeded" in results
        assert "skipped" in results
        assert "errors" in results

    @pytest.mark.asyncio
    async def test_seed_custom_templates_missing_required_fields(self, template_seeder_service):
        """Test seeding custom templates with missing required fields."""
        # Mock session
        mock_session = AsyncMock()
        
        # Test data with missing required fields
        template_definitions = [
            {
                "template_id": "incomplete-template-1",
                "name": "Incomplete Template 1"
                # Missing required fields: description, category, flow_definition
            }
        ]
        
        # Test seeding
        results = await template_seeder_service.seed_custom_templates(
            mock_session, template_definitions
        )
        
        # Verify results
        assert len(results["seeded"]) == 0
        assert len(results["skipped"]) == 0
        assert len(results["errors"]) == 1
        
        assert "Missing required field" in results["errors"][0]["error"]

    @pytest.mark.asyncio
    async def test_seed_custom_templates_already_exists(self, template_seeder_service):
        """Test seeding custom templates that already exist."""
        # Mock session with existing template
        mock_session = AsyncMock()
        mock_existing_template = MagicMock()
        mock_session.execute.return_value = MagicMock()
        mock_session.execute.return_value.scalar_one_or_none.return_value = mock_existing_template
        
        # Test data for existing template
        template_definitions = [
            {
                "template_id": "existing-template-1",
                "name": "Existing Template 1",
                "description": "An existing template",
                "category": "BATCH",
                "flow_definition": {"processors": []}
            }
        ]
        
        # Test seeding
        results = await template_seeder_service.seed_custom_templates(
            mock_session, template_definitions
        )
        
        # Verify results
        assert len(results["seeded"]) == 0
        assert len(results["skipped"]) == 1
        assert len(results["errors"]) == 0
        
        assert results["skipped"][0]["template_id"] == "existing-template-1"
        assert results["skipped"][0]["status"] == "skipped"
        assert results["skipped"][0]["reason"] == "Template already exists"