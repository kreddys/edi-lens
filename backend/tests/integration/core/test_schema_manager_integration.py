"""
Integration tests for SchemaManager with storage system.
"""

import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch

from src.core.schema_manager import SchemaManager
from src.core.models.edi_schema_models import ImplementationGuideSchema


pytestmark = pytest.mark.integration


class TestSchemaManagerIntegration:
    """Integration tests for SchemaManager with real storage interactions."""

    def setup_method(self):
        """Reset singleton state before each test."""
        # Reset singleton instance
        if SchemaManager._instance:
            SchemaManager._instance._base_schemas = {}
            SchemaManager._instance._specialized_schemas_cache = {}

    @pytest.fixture
    def realistic_schema_data(self):
        """Create realistic EDI schema data for integration testing."""
        return {
            "transactionName": "Professional Healthcare Claim Implementation Guide",
            "version": "005010X222A1",
            "description": "Professional Healthcare Claim Implementation Guide",
            "rules": [],
            "contextualDefinitions": {},
            "segmentDefinitions": {
                "HL": {
                    "id": "HL",
                    "name": "Hierarchical Level",
                    "description": "Hierarchical Level",
                    "usage": "R",
                    "max_use": 99999,
                    "elements": [
                        {
                            "xid": "HL01",
                            "data_ele": "HL01",
                            "name": "Hierarchical ID Number",
                            "usage": "R",
                            "seq": 1,
                            "dataType": "AN",
                            "minLength": 1,
                            "maxLength": 12
                        }
                    ]
                }
            },
            "structure": [
                {
                    "type": "loop",
                    "xid": "2000A",
                    "name": "Billing Provider Hierarchical Level",
                    "usage": "R",
                    "repeat": 1,
                    "children": [
                        {
                            "type": "segment",
                            "xid": "HL",
                            "name": "Hierarchical Level",
                            "usage": "R",
                            "max_use": 1,
                            "baseDefinitionId": "HL"
                        }
                    ]
                }
            ]
        }

    def test_load_base_schemas_from_filesystem(self, realistic_schema_data):
        """Test loading base schemas from filesystem."""
        manager = SchemaManager()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            schema_dir = Path(temp_dir)
            
            # Create schema files
            schema_file = schema_dir / "837P_5010_X222A1.json"
            with open(schema_file, 'w') as f:
                json.dump(realistic_schema_data, f)
            
            # Create another schema
            other_schema_data = realistic_schema_data.copy()
            other_schema_data["transactionName"] = "835 Healthcare Claim Payment and Remittance Advice Implementation Guide"
            other_file = schema_dir / "835_5010_X221A1.json"
            with open(other_file, 'w') as f:
                json.dump(other_schema_data, f)
            
            # Load schemas
            manager.load_base_schemas(schema_dir)
            
            # Verify schemas were loaded
            assert len(manager._base_schemas) == 2
            assert "837P_5010_X222A1.json" in manager._base_schemas
            assert "835_5010_X221A1.json" in manager._base_schemas
            
            # Verify schema content
            schema = manager._base_schemas["837P_5010_X222A1.json"]
            assert isinstance(schema, ImplementationGuideSchema)
            assert schema.transactionName == "Professional Healthcare Claim Implementation Guide"
            assert len(schema.structure) == 1

    @patch('src.core.schema_manager.storage_client')
    def test_get_schema_with_storage_fallback(self, mock_storage_client, realistic_schema_data):
        """Test schema retrieval with storage system integration."""
        manager = SchemaManager()
        
        # Setup base schemas first
        with tempfile.TemporaryDirectory() as temp_dir:
            schema_dir = Path(temp_dir)
            base_schema_file = schema_dir / "base_schema.json"
            with open(base_schema_file, 'w') as f:
                json.dump(realistic_schema_data, f)
            manager.load_base_schemas(schema_dir)
        
        # Test 1: Get base schema (should not hit storage)
        schema = manager.get_schema("base_schema.json", "tenant-test")
        assert schema is not None
        assert schema.transactionName == "Professional Healthcare Claim Implementation Guide"
        mock_storage_client.download.assert_not_called()
        
        # Test 2: Get specialized schema from storage
        specialized_schema_data = realistic_schema_data.copy()
        specialized_schema_data["transactionName"] = "Custom 837P TenantA Implementation Guide"
        
        mock_storage_client.download.return_value = json.dumps(specialized_schema_data).encode('utf-8')
        
        specialized_schema = manager.get_schema("custom_schema.json", "tenant-a")
        assert specialized_schema is not None
        assert specialized_schema.transactionName == "Custom 837P TenantA Implementation Guide"
        mock_storage_client.download.assert_called_once_with("tenant-a/schemas/custom_schema.json")
        
        # Test 3: Second call should use cache
        mock_storage_client.reset_mock()
        cached_schema = manager.get_schema("custom_schema.json", "tenant-a")
        assert cached_schema is specialized_schema  # Same object
        mock_storage_client.download.assert_not_called()

    @patch('src.core.schema_manager.storage_client')
    def test_storage_error_handling(self, mock_storage_client, realistic_schema_data):
        """Test proper error handling with storage system failures."""
        manager = SchemaManager()
        
        # Test 1: Storage returns None (not found)
        mock_storage_client.download.return_value = None
        schema = manager.get_schema("non_existent.json", "tenant-test")
        assert schema is None
        
        # Test 2: Storage returns invalid JSON
        mock_storage_client.download.return_value = b"invalid json"
        schema = manager.get_schema("invalid.json", "tenant-test")
        assert schema is None
        
        # Test 3: Storage returns valid JSON but invalid schema
        invalid_schema = {"invalid": "schema"}
        mock_storage_client.download.return_value = json.dumps(invalid_schema).encode('utf-8')
        schema = manager.get_schema("invalid_format.json", "tenant-test")
        assert schema is None

    def test_schema_caching_behavior(self, realistic_schema_data):
        """Test schema caching behavior across multiple requests."""
        manager = SchemaManager()
        
        # Load base schemas
        with tempfile.TemporaryDirectory() as temp_dir:
            schema_dir = Path(temp_dir)
            schema_file = schema_dir / "test_schema.json"
            with open(schema_file, 'w') as f:
                json.dump(realistic_schema_data, f)
            manager.load_base_schemas(schema_dir)
        
        # Multiple requests for the same base schema should return the same object
        schema1 = manager.get_schema("test_schema.json", "tenant-1")
        schema2 = manager.get_schema("test_schema.json", "tenant-2")
        schema3 = manager.get_schema("test_schema.json", "tenant-1")
        
        assert schema1 is schema2  # Same base schema object
        assert schema1 is schema3  # Same base schema object
        assert schema1.transactionName == "Professional Healthcare Claim Implementation Guide"

    def test_list_base_schemas_functionality(self, realistic_schema_data):
        """Test listing available base schemas."""
        manager = SchemaManager()
        
        # Initially empty
        assert len(manager.list_base_schemas()) == 0
        
        # Load schemas
        with tempfile.TemporaryDirectory() as temp_dir:
            schema_dir = Path(temp_dir)
            
            # Create multiple schema files
            for i in range(3):
                schema_data = realistic_schema_data.copy()
                schema_data["transactionName"] = f"Schema {i} Implementation Guide"
                schema_file = schema_dir / f"schema_{i}.json"
                with open(schema_file, 'w') as f:
                    json.dump(schema_data, f)
            
            manager.load_base_schemas(schema_dir)
        
        # Verify listing
        schemas = manager.list_base_schemas()
        assert len(schemas) == 3
        assert "schema_0.json" in schemas
        assert "schema_1.json" in schemas
        assert "schema_2.json" in schemas

    @patch('src.core.schema_manager.storage_client')
    def test_tenant_schema_isolation(self, mock_storage_client, realistic_schema_data):
        """Test that tenant-specific schemas are properly isolated."""
        manager = SchemaManager()
        
        # Setup different tenant schemas
        tenant_a_schema = realistic_schema_data.copy()
        tenant_a_schema["transactionName"] = "TenantA Custom Schema Implementation Guide"
        
        tenant_b_schema = realistic_schema_data.copy()
        tenant_b_schema["transactionName"] = "TenantB Custom Schema Implementation Guide"
        
        def mock_download(key):
            if "tenant-a" in key:
                return json.dumps(tenant_a_schema).encode('utf-8')
            elif "tenant-b" in key:
                return json.dumps(tenant_b_schema).encode('utf-8')
            return None
        
        mock_storage_client.download.side_effect = mock_download
        
        # Get schemas for different tenants
        schema_a = manager.get_schema("custom.json", "tenant-a")
        schema_b = manager.get_schema("custom.json", "tenant-b")
        
        assert schema_a is not None
        assert schema_b is not None
        assert schema_a.transactionName == "TenantA Custom Schema Implementation Guide"
        assert schema_b.transactionName == "TenantB Custom Schema Implementation Guide"
        assert schema_a is not schema_b  # Different objects
        
        # Verify correct storage keys were called
        expected_calls = [
            "tenant-a/schemas/custom.json",
            "tenant-b/schemas/custom.json"
        ]
        actual_calls = [call[0][0] for call in mock_storage_client.download.call_args_list]
        assert set(actual_calls) == set(expected_calls)