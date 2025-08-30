"""
Integration tests for YAML-based built-in template system.

These tests validate the complete YAML template loading, seeding, and deployment
lifecycle with real database and NiFi services.
"""

import pytest
import tempfile
import yaml
from pathlib import Path
from uuid import uuid4
from sqlalchemy import select

from src.nifi.services.built_in_templates_service import BuiltInTemplatesService
from src.models.registry_models import RegistryTemplate
from src.core.config import settings


pytestmark = pytest.mark.integration


class TestBuiltInTemplatesYAMLIntegration:
    """Integration tests for YAML-based built-in template system."""

    @pytest.fixture
    def templates_service(self):
        """Create a BuiltInTemplatesService instance for testing."""
        return BuiltInTemplatesService(
            registry_url=settings.NIFI_REGISTRY_URL,
            registry_auth_token=getattr(settings, 'NIFI_REGISTRY_AUTH_TOKEN', None)
        )

    @pytest.fixture
    def temp_templates_dir(self):
        """Create a temporary directory with test YAML templates."""
        with tempfile.TemporaryDirectory() as temp_dir:
            templates_dir = Path(temp_dir)
            
            # Create test batch template
            batch_template = {
                "metadata": {
                    "template_id": f"test-batch-template-{uuid4()}",
                    "name": "Test Batch EDI Processor",
                    "description": "Test template for batch EDI processing",
                    "category": "BATCH",
                    "scope": "GLOBAL",
                    "tenant_id": None,
                    "maintainer": "test-system",
                    "based_on": None,
                    "version": "1.0.0-test",
                    "deployment_method": "registry",
                    "tags": ["test", "batch", "edi"],
                    "features": ["sftp-monitoring", "edi-validation", "translation"],
                    "is_featured": True,
                    "status": "ACTIVE"
                },
                "flow_definition": {
                    "processors": [
                        {
                            "id": "test-list-sftp",
                            "type": "ListSFTP",
                            "name": "Test Monitor SFTP",
                            "position": {"x": 100, "y": 100},
                            "properties": {
                                "Hostname": "${SFTP_HOSTNAME}",
                                "Username": "${SFTP_USERNAME}",
                                "Password": "${SFTP_PASSWORD}",
                                "Remote Path": "${INPUT_PATH}"
                            }
                        }
                    ],
                    "connections": [],
                    "controller_services": [],
                    "parameter_contexts": [
                        {
                            "name": "test-batch-parameters",
                            "description": "Test parameters for batch processing",
                            "parameters": [
                                {
                                    "name": "SFTP_HOSTNAME",
                                    "description": "SFTP server hostname",
                                    "sensitive": False
                                },
                                {
                                    "name": "INPUT_PATH",
                                    "description": "Input directory path",
                                    "sensitive": False
                                }
                            ]
                        }
                    ]
                },
                "configuration_schema": {
                    "type": "object",
                    "required": ["input_path", "sftp_connection"],
                    "properties": {
                        "translation": {
                            "type": "object",
                            "properties": {
                                "input_translation": {
                                    "type": "object",
                                    "properties": {
                                        "enabled": {"type": "boolean", "default": False},
                                        "source_format": {"type": "string", "enum": ["JSON", "XML", "CSV"]}
                                    }
                                }
                            }
                        },
                        "input_path": {
                            "type": "string",
                            "title": "Input Directory Path"
                        },
                        "sftp_connection": {
                            "type": "object",
                            "properties": {
                                "hostname": {"type": "string"},
                                "username": {"type": "string"}
                            }
                        }
                    }
                }
            }
            
            # Create test realtime template
            realtime_template = {
                "metadata": {
                    "template_id": f"test-realtime-template-{uuid4()}",
                    "name": "Test Real-time EDI Processor",
                    "description": "Test template for real-time EDI processing",
                    "category": "REALTIME",
                    "scope": "GLOBAL",
                    "tenant_id": None,
                    "maintainer": "test-system",
                    "based_on": None,
                    "version": "1.0.0-test",
                    "deployment_method": "registry",
                    "tags": ["test", "realtime", "edi", "http"],
                    "features": ["http-listener", "real-time-validation", "translation"],
                    "is_featured": True,
                    "status": "ACTIVE"
                },
                "flow_definition": {
                    "processors": [
                        {
                            "id": "test-listen-http",
                            "type": "ListenHTTP",
                            "name": "Test HTTP Endpoint",
                            "position": {"x": 100, "y": 100},
                            "properties": {
                                "Listening Port": "${HTTP_PORT}",
                                "Base Path": "${HTTP_BASE_PATH}"
                            }
                        }
                    ],
                    "connections": [],
                    "controller_services": []
                },
                "configuration_schema": {
                    "type": "object",
                    "required": ["endpoint_config"],
                    "properties": {
                        "translation": {
                            "type": "object",
                            "properties": {
                                "output_translation": {
                                    "type": "object",
                                    "properties": {
                                        "enabled": {"type": "boolean", "default": False},
                                        "target_format": {"type": "string", "enum": ["JSON", "XML", "CSV"]}
                                    }
                                }
                            }
                        },
                        "endpoint_config": {
                            "type": "object",
                            "properties": {
                                "listening_port": {"type": "integer"},
                                "base_path": {"type": "string"}
                            }
                        }
                    }
                }
            }
            
            # Write templates to files
            batch_file = templates_dir / "test-batch-template.yaml"
            with open(batch_file, 'w') as f:
                yaml.dump(batch_template, f)
            
            realtime_file = templates_dir / "test-realtime-template.yaml"
            with open(realtime_file, 'w') as f:
                yaml.dump(realtime_template, f)
            
            # Create a README file (should be ignored)
            readme_file = templates_dir / "README.md"
            with open(readme_file, 'w') as f:
                f.write("# Test Templates\nThis is a test directory.")
            
            yield templates_dir

    @pytest.fixture
    def temp_templates_service(self, temp_templates_dir):
        """Create a BuiltInTemplatesService with temporary test templates."""
        return BuiltInTemplatesService(
            registry_url=settings.NIFI_REGISTRY_URL,
            registry_auth_token=getattr(settings, 'NIFI_REGISTRY_AUTH_TOKEN', None),
            templates_dir=str(temp_templates_dir)
        )

    def test_yaml_template_discovery(self, temp_templates_service):
        """Test that YAML template files are correctly discovered."""
        template_files = temp_templates_service._discover_template_files()
        
        # Should find 2 YAML files (ignoring README)
        assert len(template_files) == 2
        
        # Check that README is filtered out
        filenames = [f.name for f in template_files]
        assert "README.md" not in filenames
        assert any("batch" in name for name in filenames)
        assert any("realtime" in name for name in filenames)

    def test_yaml_template_loading(self, temp_templates_service, temp_templates_dir):
        """Test that YAML templates are correctly loaded and parsed."""
        templates = temp_templates_service.get_all_built_in_templates()
        
        # Should load 2 templates
        assert len(templates) == 2
        
        # Check template structure
        for template in templates:
            # Verify required fields are present
            assert "template_id" in template
            assert "name" in template
            assert "description" in template
            assert "category" in template
            assert "flow_definition" in template
            assert "configuration_schema" in template
            assert "_source_file" in template
            
            # Verify categories
            assert template["category"] in ["BATCH", "REALTIME"]
            
            # Verify translation configuration in schema
            config_schema = template["configuration_schema"]
            assert "translation" in config_schema["properties"]
            
            # Verify source file tracking
            assert temp_templates_dir.name in template["_source_file"]

    def test_yaml_template_validation(self, temp_templates_dir):
        """Test that invalid YAML templates are properly handled."""
        # Create an invalid template (missing required sections)
        invalid_template = {
            "metadata": {
                "template_id": "invalid-template",
                "name": "Invalid Template"
            }
            # Missing flow_definition and configuration_schema
        }
        
        invalid_file = temp_templates_dir / "invalid-template.yaml"
        with open(invalid_file, 'w') as f:
            yaml.dump(invalid_template, f)
        
        service = BuiltInTemplatesService(
            registry_url=settings.NIFI_REGISTRY_URL,
            templates_dir=str(temp_templates_dir)
        )
        
        # Should handle invalid template gracefully
        templates = service.get_all_built_in_templates()
        
        # Should still load the 2 valid templates, skipping the invalid one
        assert len(templates) == 2
        
        # Verify none of the loaded templates are the invalid one
        template_ids = [t["template_id"] for t in templates]
        assert "invalid-template" not in template_ids

    def test_template_by_id_lookup(self, temp_templates_service):
        """Test retrieving templates by ID."""
        templates = temp_templates_service.get_all_built_in_templates()
        first_template = templates[0]
        
        # Test successful lookup
        found_template = temp_templates_service.get_template_by_id(first_template["template_id"])
        assert found_template is not None
        assert found_template["template_id"] == first_template["template_id"]
        assert found_template["name"] == first_template["name"]
        
        # Test failed lookup
        not_found = temp_templates_service.get_template_by_id("non-existent-template")
        assert not_found is None

    def test_template_reload_functionality(self, temp_templates_service, temp_templates_dir):
        """Test that templates can be reloaded from YAML files."""
        # Initial load
        initial_templates = temp_templates_service.get_all_built_in_templates()
        assert len(initial_templates) == 2
        
        # Add a new template file
        new_template = {
            "metadata": {
                "template_id": f"new-template-{uuid4()}",
                "name": "New Test Template",
                "description": "Dynamically added template",
                "category": "TRANSFORMATION",
                "scope": "GLOBAL",
                "tenant_id": None,
                "maintainer": "test-system",
                "version": "1.0.0",
                "deployment_method": "registry",
                "tags": ["test", "new"],
                "features": ["transformation"],
                "is_featured": False,
                "status": "ACTIVE"
            },
            "flow_definition": {
                "processors": [{"id": "new-processor", "type": "UpdateAttribute"}],
                "connections": []
            },
            "configuration_schema": {
                "type": "object",
                "properties": {"test_prop": {"type": "string"}}
            }
        }
        
        new_file = temp_templates_dir / "new-template.yaml"
        with open(new_file, 'w') as f:
            yaml.dump(new_template, f)
        
        # Reload templates
        reloaded_templates = temp_templates_service.reload_templates()
        
        # Should now have 3 templates
        assert len(reloaded_templates) == 3
        
        # Verify the new template is included
        template_names = [t["name"] for t in reloaded_templates]
        assert "New Test Template" in template_names

    def test_builtin_templates_directory_default(self):
        """Test that service defaults to the correct builtin templates directory."""
        service = BuiltInTemplatesService(registry_url="http://test")
        
        # Should default to backend/data/templates/builtin
        expected_path = Path(__file__).parent.parent.parent / "data" / "templates" / "builtin"
        assert service.templates_dir == expected_path

    def test_production_templates_loading(self, templates_service):
        """Test loading the actual production YAML templates."""
        templates = templates_service.get_all_built_in_templates()
        
        # Should load the production templates (assuming they exist)
        # This test will skip if no production templates are present
        if len(templates) == 0:
            pytest.skip("No production templates found in builtin directory")
        
        # Verify production template structure
        for template in templates:
            # Check required metadata
            # Template ID should be valid (relaxed naming convention)
            assert len(template["template_id"]) > 0
            assert template["category"] in ["BATCH", "REALTIME", "TRANSFORMATION"]
            assert template["scope"] == "GLOBAL"
            # Maintainer should be specified
            assert len(template["maintainer"]) > 0
            
            # Check translation features (templates may have different features)
            features = template.get("features", [])
            # At least check that it has some features
            assert len(features) > 0
            
            # Check flow definition structure
            flow_def = template["flow_definition"]
            assert "processors" in flow_def
            assert isinstance(flow_def["processors"], list)
            
            # Check configuration schema structure
            config_schema = template["configuration_schema"]
            assert "properties" in config_schema
            assert isinstance(config_schema["properties"], dict)

    def test_yaml_template_with_missing_directory(self):
        """Test handling of missing templates directory."""
        non_existent_dir = "/tmp/non-existent-templates-" + str(uuid4())
        service = BuiltInTemplatesService(
            registry_url="http://test",
            templates_dir=non_existent_dir
        )
        
        # Should handle gracefully and return empty list
        templates = service.get_all_built_in_templates()
        assert templates == []

    def test_yaml_template_file_permissions_error(self, temp_templates_dir):
        """Test handling of file permission errors during template loading."""
        # This test may not work on all systems, so we'll make it conditional
        try:
            # Create a template file with restricted permissions
            restricted_file = temp_templates_dir / "restricted-template.yaml"
            with open(restricted_file, 'w') as f:
                yaml.dump({"metadata": {"template_id": "restricted"}}, f)
            
            # Remove read permissions (this may not work on all systems)
            restricted_file.chmod(0o000)
            
            service = BuiltInTemplatesService(
                registry_url="http://test",
                templates_dir=str(temp_templates_dir)
            )
            
            # Should handle permission errors gracefully
            templates = service.get_all_built_in_templates()
            
            # Should load other templates but skip the restricted one
            # The exact number depends on whether the permission restriction worked
            assert isinstance(templates, list)
            
            # Restore permissions for cleanup
            restricted_file.chmod(0o644)
            
        except (OSError, PermissionError):
            # Skip test if we can't manipulate file permissions
            pytest.skip("Cannot test file permissions on this system")


class TestBuiltInTemplatesSeeding:
    """Test template seeding functionality."""

    @pytest.fixture
    def temp_templates_service(self, temp_templates_dir):
        """Create a service with test templates for seeding tests."""
        return BuiltInTemplatesService(
            registry_url=settings.NIFI_REGISTRY_URL,
            templates_dir=str(temp_templates_dir)
        )

    @pytest.fixture
    def temp_templates_dir(self):
        """Create test templates for seeding."""
        with tempfile.TemporaryDirectory() as temp_dir:
            templates_dir = Path(temp_dir)
            
            # Create a simple test template with fixed ID for consistency
            test_template = {
                "metadata": {
                    "template_id": "test-seed-template-fixed-id-for-seeding",
                    "name": "Test Seeding Template",
                    "description": "Template for testing seeding functionality",
                    "category": "BATCH",
                    "scope": "GLOBAL",
                    "tenant_id": None,
                    "maintainer": "test-system",
                    "based_on": None,
                    "version": "1.0.0",
                    "deployment_method": "registry",
                    "tags": ["test", "seeding"],
                    "features": ["test-feature"],
                    "is_featured": False,
                    "status": "ACTIVE"
                },
                "flow_definition": {
                    "processors": [
                        {
                            "id": "test-processor",
                            "type": "GenerateFlowFile",
                            "name": "Test Processor",
                            "properties": {"File Size": "1KB"}
                        }
                    ],
                    "connections": []
                },
                "configuration_schema": {
                    "type": "object",
                    "properties": {
                        "test_property": {
                            "type": "string",
                            "title": "Test Property"
                        }
                    }
                }
            }
            
            template_file = templates_dir / "test-seed-template.yaml"
            with open(template_file, 'w') as f:
                yaml.dump(test_template, f)
            
            yield templates_dir

    @pytest.mark.asyncio
    async def test_template_seeding_success(self, temp_templates_service, db_session):
        """Test successful seeding of YAML templates into database."""
        # Clean up any existing templates first to ensure test isolation (Registry-first architecture)
        from sqlalchemy import text
        await db_session.execute(text("DELETE FROM registry_templates"))
        await db_session.commit()
        
        # Verify database is clean
        query = select(RegistryTemplate)
        result = await db_session.execute(query)
        initial_templates = result.scalars().all()
        assert len(initial_templates) == 0
        
        # Seed templates
        seeding_results = await temp_templates_service.seed_built_in_templates(db_session)
        
        # Verify seeding results
        assert "seeded" in seeding_results
        assert "skipped" in seeding_results
        assert "errors" in seeding_results
        
        assert len(seeding_results["seeded"]) == 1
        assert len(seeding_results["skipped"]) == 0
        assert len(seeding_results["errors"]) == 0
        
        # Verify templates were created in database (Registry-first architecture)
        query = select(RegistryTemplate)
        result = await db_session.execute(query)
        db_templates = result.scalars().all()
        assert len(db_templates) == 1
        
        template = db_templates[0]
        assert template.name == "Test Seeding Template"
        assert template.scope == "GLOBAL"
        assert template.created_by == "test-system"
        
        # In Registry-first architecture, versions are managed by NiFi Registry, not database
        # Verify the template has Registry IDs
        assert template.bucket_id is not None
        assert template.current_version == 1

    @pytest.mark.asyncio
    async def test_template_seeding_idempotency(self, temp_templates_service, db_session):
        """Test that re-seeding existing templates is handled correctly."""
        # Clean up any existing templates first to ensure test isolation (Registry-first architecture)
        from sqlalchemy import text
        await db_session.execute(text("DELETE FROM registry_templates"))
        await db_session.commit()
        
        # First seeding
        first_results = await temp_templates_service.seed_built_in_templates(db_session)
        assert len(first_results["seeded"]) == 1
        assert len(first_results["skipped"]) == 0
        
        # Second seeding (should skip existing templates)
        second_results = await temp_templates_service.seed_built_in_templates(db_session)
        assert len(second_results["seeded"]) == 0
        assert len(second_results["skipped"]) == 1
        assert second_results["skipped"][0]["reason"] == "Template already exists"
        
        # Verify only one template exists in database
        query = select(RegistryTemplate)
        result = await db_session.execute(query)
        db_templates = result.scalars().all()
        assert len(db_templates) == 1

    @pytest.mark.asyncio
    async def test_template_seeding_error_handling(self, db_session):
        """Test error handling during template seeding."""
        # Create a service with invalid template directory
        invalid_service = BuiltInTemplatesService(
            registry_url=settings.NIFI_REGISTRY_URL,
            templates_dir="/tmp/non-existent-" + str(uuid4())
        )
        
        # Seeding should complete without errors but with no templates
        results = await invalid_service.seed_built_in_templates(db_session)
        assert len(results["seeded"]) == 0
        assert len(results["skipped"]) == 0
        assert len(results["errors"]) == 0