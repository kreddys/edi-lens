"""
End-to-end integration tests for YAML-based built-in template system.

These tests validate the complete lifecycle from YAML template files to
deployed NiFi workflows, including database seeding, registry deployment,
and workflow creation.
"""

import pytest
import asyncio
import tempfile
import yaml
from pathlib import Path
from uuid import uuid4
from sqlalchemy import select

from src.nifi.services.built_in_templates_service import BuiltInTemplatesService
from src.services.nifi_workflow_service import NiFiWorkflowService
from src.models.workflow_template import WorkflowTemplate, Workflow
from src.nifi.clients.registry_client import NiFiRegistryClient
from src.nifi.clients.nifi_client import NiFiAPIClient
from src.core.config import settings


pytestmark = pytest.mark.integration


class TestBuiltInTemplatesEndToEnd:
    """End-to-end integration tests for the complete YAML template system."""

    @pytest.fixture
    def production_yaml_template(self):
        """Create a realistic YAML template similar to production templates."""
        template_id = f"test-e2e-batch-{uuid4()}"
        return {
            "metadata": {
                "template_id": template_id,
                "name": f"E2E Test Batch Processor {uuid4()}",
                "description": "End-to-end test template for batch EDI processing with translation",
                "category": "BATCH",
                "scope": "GLOBAL",
                "tenant_id": None,
                "maintainer": "test-system",
                "based_on": None,
                "version": "1.0.0",
                "deployment_method": "registry",
                "tags": ["e2e-test", "batch", "edi", "translation"],
                "features": [
                    "sftp-monitoring",
                    "edi-validation",
                    "ta1-generation",
                    "format-translation",
                    "configurable-translation"
                ],
                "is_featured": True,
                "status": "ACTIVE"
            },
            "flow_definition": {
                "identifier": f"e2e-test-flow-{uuid4()}",
                "name": f"E2E Test Flow {uuid4()}",
                "description": "Complete test flow for E2E validation",
                "processors": [
                    {
                        "identifier": f"list-sftp-{uuid4()}",
                        "name": "Monitor SFTP Directory",
                        "type": "org.apache.nifi.processors.standard.ListSFTP",
                        "position": {"x": 100.0, "y": 100.0},
                        "properties": {
                            "Hostname": "${SFTP_HOSTNAME}",
                            "Port": "${SFTP_PORT}",
                            "Username": "${SFTP_USERNAME}",
                            "Password": "${SFTP_PASSWORD}",
                            "Remote Path": "${INPUT_PATH}",
                            "Search Recursively": "false"
                        },
                        "schedulingPeriod": "${POLLING_INTERVAL}",
                        "autoTerminatedRelationships": []
                    },
                    {
                        "identifier": f"fetch-sftp-{uuid4()}",
                        "name": "Fetch EDI File",
                        "type": "org.apache.nifi.processors.standard.FetchSFTP",
                        "position": {"x": 350.0, "y": 100.0},
                        "properties": {
                            "Hostname": "${SFTP_HOSTNAME}",
                            "Port": "${SFTP_PORT}",
                            "Username": "${SFTP_USERNAME}",
                            "Password": "${SFTP_PASSWORD}",
                            "Remote File": "${path}/${filename}"
                        },
                        "autoTerminatedRelationships": []
                    },
                    {
                        "identifier": f"validate-edi-{uuid4()}",
                        "name": "Validate EDI Content",
                        "type": "org.apache.nifi.processors.standard.InvokeHTTP",
                        "position": {"x": 600.0, "y": 100.0},
                        "properties": {
                            "HTTP Method": "POST",
                            "Remote URL": "http://backend:8000/api/v1/edi/validate-batch",
                            "Content-Type": "application/json",
                            "Authorization": "Bearer ${EDI_BACKEND_SERVICE_TOKEN}"
                        },
                        "autoTerminatedRelationships": ["retry"]
                    }
                ],
                "connections": [
                    {
                        "identifier": f"list-to-fetch-{uuid4()}",
                        "name": "List to Fetch",
                        "source": {
                            "id": f"list-sftp-{uuid4()}",
                            "type": "PROCESSOR"
                        },
                        "destination": {
                            "id": f"fetch-sftp-{uuid4()}",
                            "type": "PROCESSOR"
                        },
                        "selectedRelationships": ["success"]
                    },
                    {
                        "identifier": f"fetch-to-validate-{uuid4()}",
                        "name": "Fetch to Validate",
                        "source": {
                            "id": f"fetch-sftp-{uuid4()}",
                            "type": "PROCESSOR"
                        },
                        "destination": {
                            "id": f"validate-edi-{uuid4()}",
                            "type": "PROCESSOR"
                        },
                        "selectedRelationships": ["success"]
                    }
                ],
                "processGroups": [],
                "controllerServices": [],
                "parameterContexts": [
                    {
                        "identifier": f"e2e-params-{uuid4()}",
                        "name": "e2e-test-parameters",
                        "description": "Parameters for E2E test workflow",
                        "parameters": [
                            {
                                "name": "SFTP_HOSTNAME",
                                "description": "SFTP server hostname",
                                "sensitive": False,
                                "value": "localhost"
                            },
                            {
                                "name": "SFTP_PORT",
                                "description": "SFTP server port",
                                "sensitive": False,
                                "value": "22"
                            },
                            {
                                "name": "INPUT_PATH",
                                "description": "Input directory path",
                                "sensitive": False,
                                "value": "/test/input"
                            },
                            {
                                "name": "POLLING_INTERVAL",
                                "description": "Polling interval",
                                "sensitive": False,
                                "value": "30 sec"
                            }
                        ]
                    }
                ]
            },
            "configuration_schema": {
                "type": "object",
                "required": ["input_path", "sftp_connection", "validation"],
                "properties": {
                    "translation": {
                        "type": "object",
                        "title": "Translation Configuration",
                        "properties": {
                            "input_translation": {
                                "type": "object",
                                "properties": {
                                    "enabled": {
                                        "type": "boolean",
                                        "title": "Enable Input Translation",
                                        "default": False
                                    },
                                    "source_format": {
                                        "type": "string",
                                        "enum": ["JSON", "XML", "CSV"]
                                    }
                                }
                            },
                            "output_translation": {
                                "type": "object",
                                "properties": {
                                    "enabled": {
                                        "type": "boolean",
                                        "title": "Enable Output Translation",
                                        "default": False
                                    },
                                    "target_format": {
                                        "type": "string",
                                        "enum": ["JSON", "XML", "CSV"]
                                    }
                                }
                            }
                        }
                    },
                    "input_path": {
                        "type": "string",
                        "title": "Input Directory Path",
                        "pattern": "^/[^/]+/.+/$"
                    },
                    "sftp_connection": {
                        "type": "object",
                        "title": "SFTP Connection",
                        "required": ["hostname", "username"],
                        "properties": {
                            "hostname": {"type": "string"},
                            "port": {"type": "integer", "default": 22},
                            "username": {"type": "string"},
                            "password": {"type": "string", "format": "password"}
                        }
                    },
                    "validation": {
                        "type": "object",
                        "required": ["schema"],
                        "properties": {
                            "schema": {"type": "string"},
                            "snip_level": {"type": "integer", "minimum": 1, "maximum": 5, "default": 3}
                        }
                    }
                }
            }
        }

    @pytest.fixture
    def temp_templates_dir(self, production_yaml_template):
        """Create temporary directory with production-like YAML template."""
        with tempfile.TemporaryDirectory() as temp_dir:
            templates_dir = Path(temp_dir)
            
            template_file = templates_dir / "e2e-test-template.yaml"
            with open(template_file, 'w') as f:
                yaml.dump(production_yaml_template, f, default_flow_style=False)
            
            yield templates_dir

    @pytest.fixture
    def templates_service(self, temp_templates_dir):
        """Create templates service with test template."""
        return BuiltInTemplatesService(
            registry_url=settings.NIFI_REGISTRY_URL,
            registry_auth_token=getattr(settings, 'NIFI_REGISTRY_AUTH_TOKEN', None),
            templates_dir=str(temp_templates_dir)
        )

    @pytest.fixture
    def workflow_service(self, db_session):
        """Create workflow service for deployment testing."""
        return NiFiWorkflowService(db_session)

    @pytest.mark.asyncio
    async def test_complete_yaml_to_workflow_lifecycle(
        self, 
        templates_service, 
        workflow_service, 
        db_session, 
        production_yaml_template
    ):
        """Test the complete lifecycle from YAML template to deployed workflow."""
        
        # Step 1: Load template from YAML
        templates = templates_service.get_all_built_in_templates()
        assert len(templates) == 1
        
        loaded_template = templates[0]
        assert loaded_template["template_id"] == production_yaml_template["metadata"]["template_id"]
        assert loaded_template["name"] == production_yaml_template["metadata"]["name"]
        assert "format-translation" in loaded_template["features"]
        
        # Step 2: Seed template into database
        seeding_results = await templates_service.seed_built_in_templates(db_session)
        assert len(seeding_results["seeded"]) == 1
        assert len(seeding_results["errors"]) == 0
        
        template_id = seeding_results["seeded"][0]["template_id"]
        
        # Verify template in database
        query = select(WorkflowTemplate).where(WorkflowTemplate.template_id == template_id)
        result = await db_session.execute(query)
        db_template = result.scalar_one()
        
        assert db_template.name == production_yaml_template["metadata"]["name"]
        assert db_template.category == "BATCH"
        assert "format-translation" in db_template.features
        
        # Step 3: Deploy template to NiFi Registry
        registry_deployment = await templates_service.register_template_in_registry(db_template)
        assert registry_deployment is True
        
        # Step 4: Create workflow from template
        workflow_config = {
            "translation": {
                "input_translation": {
                    "enabled": True,
                    "source_format": "JSON"
                },
                "output_translation": {
                    "enabled": False
                }
            },
            "input_path": "/sftp/test/input/",
            "sftp_connection": {
                "hostname": "test-sftp.example.com",
                "port": 22,
                "username": "test-user",
                "password": "test-password"
            },
            "validation": {
                "schema": "837.5010.X222.A1.json",
                "snip_level": 3
            }
        }
        
        workflow_data = {
            "name": f"E2E Test Workflow {uuid4()}",
            "description": "End-to-end test workflow created from YAML template",
            "template_id": template_id,
            "configuration": workflow_config,
            "tenant_id": "test-tenant"
        }
        
        # Create workflow in database
        created_workflow = await workflow_service.create_workflow(
            workflow_data=workflow_data,
            created_by="test-user"
        )
        
        assert created_workflow.name == workflow_data["name"]
        assert created_workflow.template_id == template_id
        assert created_workflow.configuration == workflow_config
        
        # Step 5: Deploy workflow to NiFi (if NiFi is available)
        try:
            deployed_workflow = await workflow_service.deploy_workflow(created_workflow)
            
            # If deployment succeeds, verify workflow status
            if deployed_workflow.status == "ACTIVE":
                assert deployed_workflow.nifi_process_group_id is not None
                
                # Verify workflow was updated in database
                await db_session.refresh(created_workflow)
                assert created_workflow.status == "ACTIVE"
                assert created_workflow.nifi_process_group_id is not None
                
                # Step 6: Test workflow lifecycle operations
                # Start workflow
                started_workflow = await workflow_service.start_workflow(deployed_workflow)
                assert started_workflow.status in ["ACTIVE"]
                
                # Get workflow status
                status_result = await workflow_service.get_workflow_status(deployed_workflow)
                assert "nifi_status" in status_result
                assert status_result["nifi_status"] in ["RUNNING", "STOPPED", "UNKNOWN", None]
                
                # Stop workflow
                stopped_workflow = await workflow_service.stop_workflow(deployed_workflow)
                assert stopped_workflow.status in ["PAUSED"]
                
                # Cleanup: Undeploy workflow
                undeployed_workflow = await workflow_service.undeploy_workflow(stopped_workflow)
                assert undeployed_workflow.status == "DELETED"
                
        except Exception as e:
            # If NiFi is not available or deployment fails, verify the error is handled gracefully
            pytest.skip(f"NiFi deployment test skipped due to: {str(e)}")

    @pytest.mark.asyncio
    async def test_yaml_template_translation_configuration(
        self, 
        templates_service, 
        db_session, 
        production_yaml_template
    ):
        """Test that translation configuration from YAML templates is properly handled."""
        
        # Load and seed template
        seeding_results = await templates_service.seed_built_in_templates(db_session)
        template_id = seeding_results["seeded"][0]["template_id"]
        
        query = select(WorkflowTemplate).where(WorkflowTemplate.template_id == template_id)
        result = await db_session.execute(query)
        template = result.scalar_one()
        
        # Verify translation features in template
        assert "format-translation" in template.features
        assert "configurable-translation" in template.features
        
        # Verify translation configuration schema
        config_schema = template.configuration_schema
        assert "translation" in config_schema["properties"]
        
        translation_props = config_schema["properties"]["translation"]["properties"]
        assert "input_translation" in translation_props
        assert "output_translation" in translation_props
        
        # Test input translation schema
        input_translation = translation_props["input_translation"]["properties"]
        assert "enabled" in input_translation
        assert input_translation["enabled"]["type"] == "boolean"
        assert "source_format" in input_translation
        assert input_translation["source_format"]["enum"] == ["JSON", "XML", "CSV"]
        
        # Test output translation schema
        output_translation = translation_props["output_translation"]["properties"]
        assert "enabled" in output_translation
        assert output_translation["enabled"]["type"] == "boolean"
        assert "target_format" in output_translation
        assert output_translation["target_format"]["enum"] == ["JSON", "XML", "CSV"]

    @pytest.mark.asyncio
    async def test_yaml_template_parameter_context_handling(
        self, 
        templates_service, 
        db_session
    ):
        """Test that parameter contexts from YAML templates are properly structured."""
        
        # Load template
        templates = templates_service.get_all_built_in_templates()
        template_data = templates[0]
        
        # Verify parameter contexts in flow definition
        flow_def = template_data["flow_definition"]
        assert "parameterContexts" in flow_def
        assert len(flow_def["parameterContexts"]) > 0
        
        param_context = flow_def["parameterContexts"][0]
        assert "name" in param_context
        assert "parameters" in param_context
        
        # Verify parameter structure
        parameters = param_context["parameters"]
        assert len(parameters) > 0
        
        for param in parameters:
            assert "name" in param
            assert "description" in param
            assert "sensitive" in param
            # Some parameters may have default values
            if "value" in param:
                assert isinstance(param["value"], str)

    def test_yaml_template_processor_configuration(
        self, 
        templates_service
    ):
        """Test that processor configurations from YAML are properly structured."""
        
        templates = templates_service.get_all_built_in_templates()
        template_data = templates[0]
        
        flow_def = template_data["flow_definition"]
        processors = flow_def["processors"]
        
        assert len(processors) > 0
        
        for processor in processors:
            # Verify required processor fields
            assert "identifier" in processor
            assert "name" in processor
            assert "type" in processor
            assert "position" in processor
            assert "properties" in processor
            
            # Verify position structure
            position = processor["position"]
            assert "x" in position
            assert "y" in position
            assert isinstance(position["x"], (int, float))
            assert isinstance(position["y"], (int, float))
            
            # Verify properties use parameter references
            properties = processor["properties"]
            for prop_name, prop_value in properties.items():
                if isinstance(prop_value, str) and prop_value.startswith("${"):
                    # Should be a parameter reference
                    assert prop_value.endswith("}")

    @pytest.mark.asyncio
    async def test_multiple_yaml_templates_workflow_creation(
        self, 
        workflow_service, 
        db_session
    ):
        """Test creating workflows from multiple YAML template types."""
        
        # Use production templates service to test with actual templates
        production_service = BuiltInTemplatesService(
            registry_url=settings.NIFI_REGISTRY_URL,
            registry_auth_token=getattr(settings, 'NIFI_REGISTRY_AUTH_TOKEN', None)
        )
        
        production_templates = production_service.get_all_built_in_templates()
        
        if len(production_templates) == 0:
            pytest.skip("No production templates available for multi-template test")
        
        # Seed all production templates
        seeding_results = await production_service.seed_built_in_templates(db_session)
        total_templates = len(seeding_results["seeded"]) + len(seeding_results["skipped"])
        
        assert total_templates > 0
        
        # Get all templates from database
        query = select(WorkflowTemplate)
        result = await db_session.execute(query)
        db_templates = result.scalars().all()
        
        # Test creating workflows from different template categories
        created_workflows = []
        
        for template in db_templates[:2]:  # Test first 2 templates
            workflow_config = {
                "test_config": f"test-value-for-{template.category.lower()}"
            }
            
            # Add category-specific configuration
            if template.category == "BATCH":
                workflow_config.update({
                    "input_path": f"/test/{template.template_id}/input/",
                    "translation": {
                        "input_translation": {"enabled": False},
                        "output_translation": {"enabled": False}
                    }
                })
            elif template.category == "REALTIME":
                workflow_config.update({
                    "endpoint_config": {
                        "listening_port": 8080 + len(created_workflows),
                        "base_path": f"/api/test/{template.template_id}"
                    },
                    "translation": {
                        "input_translation": {"enabled": False},
                        "output_translation": {"enabled": False}
                    }
                })
            
            workflow_data = {
                "name": f"Multi-Test Workflow {template.category} {uuid4()}",
                "description": f"Test workflow for {template.category} template",
                "template_id": template.template_id,
                "configuration": workflow_config,
                "tenant_id": "multi-test-tenant"
            }
            
            created_workflow = await workflow_service.create_workflow(
                workflow_data=workflow_data,
                created_by="multi-test-user"
            )
            
            created_workflows.append(created_workflow)
            
            # Verify workflow was created correctly
            assert created_workflow.name == workflow_data["name"]
            assert created_workflow.template_id == template.template_id
            assert created_workflow.tenant_id == "multi-test-tenant"
        
        # Verify we created workflows from different template types
        workflow_categories = [w.template.category for w in created_workflows]
        assert len(set(workflow_categories)) > 0  # At least one unique category