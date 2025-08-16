"""
Unit tests for Built-in Templates Service.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4

from src.nifi.services.built_in_templates_service import BuiltInTemplatesService
from src.models.workflow_template import WorkflowTemplate

pytestmark = pytest.mark.unit


class TestBuiltInTemplatesService:
    """Test Built-in Templates Service."""

    @pytest.fixture
    def built_in_service(self):
        """Create a built-in templates service fixture."""
        return BuiltInTemplatesService(
            registry_url="http://localhost:18080",
            registry_auth_token="test-token"
        )

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        session = AsyncMock()
        # Set up execute method as async and return a mock result
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_result)
        session.commit = AsyncMock()
        session.add = MagicMock()
        session.refresh = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_built_in_service_initialization(self):
        """Test built-in templates service initialization."""
        service = BuiltInTemplatesService(
            registry_url="http://localhost:18080",
            registry_auth_token="test-token"
        )
        
        assert service.registry_url == "http://localhost:18080"
        assert service.registry_auth_token == "test-token"

    @pytest.mark.asyncio
    async def test_built_in_service_initialization_no_auth(self):
        """Test built-in templates service initialization without auth token."""
        service = BuiltInTemplatesService(
            registry_url="http://localhost:18080"
        )
        
        assert service.registry_url == "http://localhost:18080"
        assert service.registry_auth_token is None

    def test_get_all_built_in_templates(self, built_in_service):
        """Test getting all built-in template definitions."""
        templates = built_in_service.get_all_built_in_templates()
        
        assert isinstance(templates, list)
        assert len(templates) == 3  # SFTP, HTTP, Format Converter
        
        # Check template IDs (these are the actual IDs from the implementation)
        template_ids = [t["template_id"] for t in templates]
        assert "global-sftp-edi-processor-v1.0" in template_ids
        assert "global-http-edi-processor-v1.0" in template_ids
        assert "global-format-converter-v1.0" in template_ids
        
        # Check required fields are present
        for template in templates:
            assert "template_id" in template
            assert "name" in template
            assert "description" in template
            assert "category" in template
            assert "flow_definition" in template
            assert "configuration_schema" in template

    def test_get_sftp_edi_processor_template(self, built_in_service):
        """Test SFTP EDI processor template definition."""
        template = built_in_service._get_sftp_edi_processor_template()
        
        assert template["template_id"] == "global-sftp-edi-processor-v1.0"
        assert template["name"] == "SFTP EDI File Processor"
        assert template["category"] == "BATCH"
        assert template["scope"] == "GLOBAL"
        assert template["deployment_method"] == "registry"
        
        # Check flow definition structure
        flow_def = template["flow_definition"]
        assert "processors" in flow_def
        assert "connections" in flow_def
        assert "parameter_contexts" in flow_def
        
        # Check processors (checking actual processor types from implementation)
        processors = flow_def["processors"]
        processor_types = [p["type"] for p in processors]
        assert "ListSFTP" in processor_types
        assert "RouteOnAttribute" in processor_types
        assert "FetchSFTP" in processor_types
        
        # Check configuration schema
        config_schema = template["configuration_schema"]
        assert config_schema["type"] == "object"
        assert "required" in config_schema
        assert "properties" in config_schema
        
        # Check required properties (updated to match actual implementation)
        required_props = config_schema["required"]
        assert "input_path" in required_props
        assert "file_patterns" in required_props
        assert "validation" in required_props

    def test_get_http_edi_processor_template(self, built_in_service):
        """Test HTTP EDI processor template definition."""
        template = built_in_service._get_http_edi_processor_template()
        
        assert template["template_id"] == "global-http-edi-processor-v1.0"
        assert template["name"] == "HTTP EDI Processor"
        assert template["category"] == "REALTIME"
        assert template["scope"] == "GLOBAL"
        assert template["deployment_method"] == "registry"
        
        # Check flow definition structure
        flow_def = template["flow_definition"]
        assert "processors" in flow_def
        assert "connections" in flow_def
        assert "parameter_contexts" in flow_def
        
        # Check processors (checking actual processor types from implementation)
        processors = flow_def["processors"]
        processor_types = [p["type"] for p in processors]
        assert "ListenHTTP" in processor_types
        assert "RouteOnAttribute" in processor_types
        assert "InvokeHTTP" in processor_types
        
        # Check configuration schema
        config_schema = template["configuration_schema"]
        assert config_schema["type"] == "object"
        assert "required" in config_schema
        assert "properties" in config_schema
        
        # Check required properties (updated to match actual implementation)
        required_props = config_schema["required"]
        assert "endpoint_config" in required_props
        assert "validation" in required_props

    def test_get_format_converter_template(self, built_in_service):
        """Test format converter template definition."""
        template = built_in_service._get_format_converter_template()
        
        assert template["template_id"] == "global-format-converter-v1.0"
        assert template["name"] == "Format Converter"
        assert template["category"] == "TRANSFORMATION"
        assert template["scope"] == "GLOBAL"
        assert template["deployment_method"] == "registry"
        
        # Check flow definition structure
        flow_def = template["flow_definition"]
        assert "processors" in flow_def
        assert "connections" in flow_def
        assert "parameter_contexts" in flow_def
        
        # Check processors (checking actual processor types from implementation)
        processors = flow_def["processors"]
        processor_types = [p["type"] for p in processors]
        # The format converter uses ${INPUT_METHOD} as a dynamic type
        assert "UpdateAttribute" in processor_types
        assert "RouteOnAttribute" in processor_types
        assert "InvokeHTTP" in processor_types
        assert "EvaluateJsonPath" in processor_types
        
        # Check configuration schema
        config_schema = template["configuration_schema"]
        assert config_schema["type"] == "object"
        assert "required" in config_schema
        assert "properties" in config_schema
        
        # Check required properties (updated to match actual implementation)
        required_props = config_schema["required"]
        assert "input_config" in required_props
        assert "output_config" in required_props
        assert "conversion_config" in required_props

    @pytest.mark.asyncio
    async def test_seed_built_in_templates_success(self, built_in_service, mock_session):
        """Test successful seeding of built-in templates."""
        # Mock the _seed_template method to return success results
        from unittest.mock import patch, AsyncMock
        
        mock_seed_results = [
            {"template_id": "global-sftp-edi-processor-v1.0", "status": "seeded", "name": "SFTP EDI File Processor"},
            {"template_id": "global-http-edi-processor-v1.0", "status": "seeded", "name": "HTTP EDI Processor"},
            {"template_id": "global-format-converter-v1.0", "status": "seeded", "name": "Format Converter"}
        ]
        
        with patch.object(built_in_service, '_seed_template', side_effect=mock_seed_results) as mock_seed:
            result = await built_in_service.seed_built_in_templates(mock_session)
            
            assert len(result["seeded"]) == 3
            assert len(result["skipped"]) == 0
            assert len(result["errors"]) == 0
            
            # Verify _seed_template was called 3 times
            assert mock_seed.call_count == 3

    @pytest.mark.asyncio
    async def test_seed_built_in_templates_already_exist(self, built_in_service, mock_session):
        """Test seeding when templates already exist."""
        # Mock the _seed_template method to return skipped results
        from unittest.mock import patch
        
        mock_seed_results = [
            {"template_id": "global-sftp-edi-processor-v1.0", "status": "skipped", "reason": "Template already exists"},
            {"template_id": "global-http-edi-processor-v1.0", "status": "skipped", "reason": "Template already exists"},
            {"template_id": "global-format-converter-v1.0", "status": "skipped", "reason": "Template already exists"}
        ]
        
        with patch.object(built_in_service, '_seed_template', side_effect=mock_seed_results) as mock_seed:
            result = await built_in_service.seed_built_in_templates(mock_session)
            
            assert len(result["seeded"]) == 0
            assert len(result["skipped"]) == 3
            assert len(result["errors"]) == 0
            
            # Verify _seed_template was called 3 times
            assert mock_seed.call_count == 3

    @pytest.mark.asyncio
    async def test_seed_built_in_templates_partial_exist(self, built_in_service, mock_session):
        """Test seeding when some templates already exist."""
        # Mock the _seed_template method to return mixed results
        from unittest.mock import patch
        
        mock_seed_results = [
            {"template_id": "global-sftp-edi-processor-v1.0", "status": "skipped", "reason": "Template already exists"},
            {"template_id": "global-http-edi-processor-v1.0", "status": "seeded", "name": "HTTP EDI Processor"},
            {"template_id": "global-format-converter-v1.0", "status": "seeded", "name": "Format Converter"}
        ]
        
        with patch.object(built_in_service, '_seed_template', side_effect=mock_seed_results) as mock_seed:
            result = await built_in_service.seed_built_in_templates(mock_session)
            
            assert len(result["seeded"]) == 2  # HTTP and Format Converter
            assert len(result["skipped"]) == 1  # SFTP
            assert len(result["errors"]) == 0
            
            # Verify _seed_template was called 3 times
            assert mock_seed.call_count == 3

    @pytest.mark.asyncio
    async def test_seed_template_success(self, built_in_service, mock_session):
        """Test successful individual template seeding."""
        template_data = {
            "template_id": "test-template",
            "name": "Test Template",
            "description": "A test template",
            "category": "TEST",
            "scope": "GLOBAL",
            "tenant_id": None,
            "maintainer": "test",
            "based_on": None,
            "version": "1.0",
            "flow_definition": {"processors": []},
            "configuration_schema": {"type": "object"},
            "deployment_method": "registry",
            "tags": [],
            "features": [],
            "is_featured": False,
            "status": "ACTIVE"
        }
        
        # Template doesn't exist (handled by fixture)
        
        result = await built_in_service._seed_template(template_data, mock_session)
        
        assert result["status"] == "seeded"
        assert result["template_id"] == "test-template"
        
        # Verify template was added (we expect 2 calls: template + version)
        assert mock_session.add.call_count == 2
        mock_session.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_seed_template_already_exists(self, built_in_service, mock_session):
        """Test seeding when template already exists."""
        template_data = {
            "template_id": "test-template",
            "name": "Test Template",
            "description": "A test template",
            "category": "TEST",
            "flow_definition": {"processors": []},
            "configuration_schema": {"type": "object"}
        }
        
        # Mock that template already exists
        existing_template = MagicMock()
        existing_template.template_id = "test-template"
        mock_session.execute.return_value.scalar_one_or_none.return_value = existing_template
        
        result = await built_in_service._seed_template(template_data, mock_session)
        
        assert result["status"] == "skipped"
        assert result["template_id"] == "test-template"
        assert result["reason"] == "Template already exists"
        
        # Verify no new template was added
        mock_session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_register_template_in_registry_success(self, built_in_service):
        """Test successful template registration in NiFi Registry."""
        mock_template = MagicMock()
        mock_template.template_id = "test-template"
        mock_template.name = "Test Template"
        mock_template.description = "A test template"
        mock_template.version = "1.0"
        mock_template.flow_definition = {"processors": []}
        
        # Mock Registry client responses
        mock_buckets = [{"identifier": "bucket1", "name": "other-bucket"}]
        mock_new_bucket = {"identifier": "edi-bucket", "name": "edi-lens-templates"}
        mock_flows = []
        mock_new_flow = {"identifier": "flow1", "name": "Test Template"}
        mock_flow_version = {"version": 1}
        
        with patch('src.nifi.services.built_in_templates_service.NiFiRegistryClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None
            
            mock_client.list_buckets.return_value = mock_buckets
            mock_client.create_bucket.return_value = mock_new_bucket
            mock_client.list_flows.return_value = mock_flows
            mock_client.create_flow.return_value = mock_new_flow
            mock_client.create_flow_version.return_value = mock_flow_version
            
            result = await built_in_service.register_template_in_registry(mock_template)
            
            assert result is True
            
            # Verify the sequence of calls
            mock_client.list_buckets.assert_called_once()
            mock_client.create_bucket.assert_called_once()
            mock_client.list_flows.assert_called_once()
            mock_client.create_flow.assert_called_once()
            mock_client.create_flow_version.assert_called_once()

    @pytest.mark.asyncio
    async def test_register_template_in_registry_bucket_exists(self, built_in_service):
        """Test template registration when bucket already exists."""
        mock_template = MagicMock()
        mock_template.template_id = "test-template"
        mock_template.name = "Test Template"
        mock_template.description = "A test template"
        mock_template.version = "1.0"
        mock_template.flow_definition = {"processors": []}
        
        # Mock that bucket already exists
        mock_buckets = [{"identifier": "edi-bucket", "name": "edi-lens-templates"}]
        mock_flows = []
        mock_new_flow = {"identifier": "flow1", "name": "Test Template"}
        mock_flow_version = {"version": 1}
        
        with patch('src.nifi.services.built_in_templates_service.NiFiRegistryClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None
            
            mock_client.list_buckets.return_value = mock_buckets
            mock_client.list_flows.return_value = mock_flows
            mock_client.create_flow.return_value = mock_new_flow
            mock_client.create_flow_version.return_value = mock_flow_version
            
            result = await built_in_service.register_template_in_registry(mock_template)
            
            assert result is True
            
            # Verify bucket creation was skipped
            mock_client.list_buckets.assert_called_once()
            mock_client.create_bucket.assert_not_called()
            mock_client.create_flow.assert_called_once()

    @pytest.mark.asyncio
    async def test_register_template_in_registry_flow_exists(self, built_in_service):
        """Test template registration when flow already exists."""
        mock_template = MagicMock()
        mock_template.template_id = "test-template"
        mock_template.name = "Test Template"
        mock_template.description = "A test template"
        mock_template.version = "1.0"
        mock_template.flow_definition = {"processors": []}
        
        # Mock that bucket and flow already exist
        mock_buckets = [{"identifier": "edi-bucket", "name": "edi-lens-templates"}]
        mock_flows = [{"identifier": "flow1", "name": "Test Template"}]
        mock_flow_version = {"version": 2}
        
        with patch('src.nifi.services.built_in_templates_service.NiFiRegistryClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None
            
            mock_client.list_buckets.return_value = mock_buckets
            mock_client.list_flows.return_value = mock_flows
            mock_client.create_flow_version.return_value = mock_flow_version
            
            result = await built_in_service.register_template_in_registry(mock_template)
            
            assert result is True
            
            # Verify flow creation was skipped
            mock_client.list_buckets.assert_called_once()
            mock_client.list_flows.assert_called_once()
            mock_client.create_bucket.assert_not_called()
            mock_client.create_flow.assert_not_called()
            mock_client.create_flow_version.assert_called_once()

    @pytest.mark.asyncio
    async def test_register_template_in_registry_failure(self, built_in_service):
        """Test template registration failure."""
        mock_template = MagicMock()
        mock_template.template_id = "test-template"
        
        with patch('src.nifi.services.built_in_templates_service.NiFiRegistryClient') as mock_client_class:
            mock_client_class.side_effect = Exception("Registry connection error")
            
            result = await built_in_service.register_template_in_registry(mock_template)
            
            assert result is False

    @pytest.mark.asyncio 
    async def test_template_flow_definition_structure(self, built_in_service):
        """Test that all template flow definitions have required structure."""
        templates = built_in_service.get_all_built_in_templates()
        
        for template in templates:
            flow_def = template["flow_definition"]
            
            # Check required top-level keys
            assert "processors" in flow_def
            assert "connections" in flow_def
            assert "parameter_contexts" in flow_def
            
            # Check processors structure
            assert isinstance(flow_def["processors"], list)
            assert len(flow_def["processors"]) > 0
            
            for processor in flow_def["processors"]:
                assert "id" in processor
                assert "type" in processor
                assert "name" in processor
                assert "position" in processor
                assert "properties" in processor
            
            # Check connections structure
            assert isinstance(flow_def["connections"], list)
            
            for connection in flow_def["connections"]:
                assert "source" in connection
                assert "destination" in connection
                # Some connections use "relationship", others use "relationships"
                assert "relationship" in connection or "relationships" in connection
            
            # Check parameter contexts structure
            assert isinstance(flow_def["parameter_contexts"], list)
            
            for param_context in flow_def["parameter_contexts"]:
                assert "name" in param_context
                assert "parameters" in param_context
                assert isinstance(param_context["parameters"], list)

    @pytest.mark.asyncio
    async def test_template_configuration_schema_structure(self, built_in_service):
        """Test that all template configuration schemas are valid."""
        templates = built_in_service.get_all_built_in_templates()
        
        for template in templates:
            config_schema = template["configuration_schema"]
            
            # Check JSON Schema structure
            assert config_schema["type"] == "object"
            assert "properties" in config_schema
            assert "required" in config_schema
            
            # Check properties structure
            properties = config_schema["properties"]
            assert isinstance(properties, dict)
            assert len(properties) > 0
            
            for prop_name, prop_def in properties.items():
                assert "type" in prop_def
                assert "title" in prop_def
                # Description may be in nested properties for object types
                if prop_def["type"] != "object":
                    assert "description" in prop_def
            
            # Check required fields
            required = config_schema["required"]
            assert isinstance(required, list)
            assert len(required) > 0
            
            # Verify all required fields exist in properties
            for req_field in required:
                assert req_field in properties