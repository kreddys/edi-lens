"""
Unit tests for SchemaManager.
"""

import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src.core.schema_manager import SchemaManager, schema_manager
from src.core.models.edi_schema_models import ImplementationGuideSchema


pytestmark = pytest.mark.unit


class TestSchemaManager:
    """Unit tests for SchemaManager functionality."""

    def setup_method(self):
        """Reset singleton state before each test."""
        # Reset singleton instance
        if SchemaManager._instance:
            SchemaManager._instance._base_schemas = {}
            SchemaManager._instance._specialized_schemas_cache = {}

    @pytest.fixture
    def sample_schema_data(self):
        """Create sample schema data for testing."""
        return {
            "name": "837P_5010_X222A1",
            "version": "5010",
            "description": "Professional Healthcare Claim Implementation Guide",
            "transaction_type": "837P",
            "loops": [
                {
                    "id": "2000A",
                    "name": "Billing Provider Hierarchical Level",
                    "usage": "Required",
                    "max_use": 1,
                    "segments": [
                        {
                            "id": "HL",
                            "name": "Hierarchical Level",
                            "usage": "Required",
                            "max_use": 1,
                            "elements": [
                                {
                                    "id": "HL01",
                                    "name": "Hierarchical ID Number",
                                    "usage": "Required",
                                    "data_type": "AN",
                                    "min_length": 1,
                                    "max_length": 12
                                }
                            ]
                        }
                    ]
                }
            ],
            "metadata": {
                "created_by": "system",
                "created_at": "2024-01-01T00:00:00Z",
                "version_info": "Initial version"
            }
        }

    @pytest.fixture
    def temp_schema_dir(self, sample_schema_data):
        """Create temporary directory with test schema files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            schema_dir = Path(temp_dir)
            
            # Create valid schema file
            schema_file = schema_dir / "837P_5010_X222A1.json"
            with open(schema_file, 'w') as f:
                json.dump(sample_schema_data, f)
            
            # Create invalid schema file
            invalid_file = schema_dir / "invalid_schema.json"
            with open(invalid_file, 'w') as f:
                f.write("invalid json content")
            
            # Create another valid schema
            other_schema_data = sample_schema_data.copy()
            other_schema_data["name"] = "835_5010_X221A1"
            other_schema_data["transaction_type"] = "835"
            other_file = schema_dir / "835_5010_X221A1.json"
            with open(other_file, 'w') as f:
                json.dump(other_schema_data, f)
            
            yield schema_dir

    def test_schema_manager_singleton(self):
        """Test that SchemaManager is a singleton."""
        manager1 = SchemaManager()
        manager2 = SchemaManager()
        
        assert manager1 is manager2
        assert manager1 is schema_manager

    def test_load_base_schemas_success(self, temp_schema_dir):
        """Test successful loading of base schemas from directory."""
        manager = SchemaManager()
        
        manager.load_base_schemas(temp_schema_dir)
        
        # Should load 2 valid schemas (ignoring invalid one)
        assert len(manager._base_schemas) == 2
        assert "837P_5010_X222A1.json" in manager._base_schemas
        assert "835_5010_X221A1.json" in manager._base_schemas
        
        # Verify schema content
        schema = manager._base_schemas["837P_5010_X222A1.json"]
        assert isinstance(schema, ImplementationGuideSchema)
        assert schema.name == "837P_5010_X222A1"
        assert schema.transaction_type == "837P"

    def test_load_base_schemas_directory_not_found(self):
        """Test loading schemas from non-existent directory."""
        manager = SchemaManager()
        
        non_existent_dir = Path("/non/existent/directory")
        manager.load_base_schemas(non_existent_dir)
        
        # Should not raise error, but no schemas loaded
        assert len(manager._base_schemas) == 0

    def test_load_base_schemas_invalid_json(self, temp_schema_dir):
        """Test loading schemas with invalid JSON files."""
        manager = SchemaManager()
        
        # This should load valid schemas and skip invalid ones
        manager.load_base_schemas(temp_schema_dir)
        
        # Should still load valid schemas despite invalid one
        assert len(manager._base_schemas) == 2
        assert "invalid_schema.json" not in manager._base_schemas

    def test_get_schema_base_schema_found(self, temp_schema_dir):
        """Test getting schema when base schema exists."""
        manager = SchemaManager()
        manager.load_base_schemas(temp_schema_dir)
        
        schema = manager.get_schema("837P_5010_X222A1.json", "tenant-test")
        
        assert schema is not None
        assert isinstance(schema, ImplementationGuideSchema)
        assert schema.name == "837P_5010_X222A1"

    def test_get_schema_specialized_from_cache(self, temp_schema_dir, sample_schema_data):
        """Test getting specialized schema from in-memory cache."""
        manager = SchemaManager()
        
        # Pre-populate cache
        cache_key = "tenant-test/custom_schema.json"
        specialized_schema = ImplementationGuideSchema.model_validate(sample_schema_data)
        manager._specialized_schemas_cache[cache_key] = specialized_schema
        
        schema = manager.get_schema("custom_schema.json", "tenant-test")
        
        assert schema is not None
        assert schema is specialized_schema

    @patch('src.core.schema_manager.storage_client')
    def test_get_schema_download_from_storage_success(self, mock_storage_client, sample_schema_data):
        """Test downloading schema from object storage."""
        manager = SchemaManager()
        
        # Mock successful storage download
        schema_json = json.dumps(sample_schema_data)
        mock_storage_client.download.return_value = schema_json.encode('utf-8')
        
        schema = manager.get_schema("custom_schema.json", "tenant-test")
        
        assert schema is not None
        assert isinstance(schema, ImplementationGuideSchema)
        assert schema.name == sample_schema_data["name"]
        
        # Verify storage was called correctly
        mock_storage_client.download.assert_called_once_with("tenant-test/schemas/custom_schema.json")
        
        # Verify schema was cached
        cache_key = "tenant-test/custom_schema.json"
        assert cache_key in manager._specialized_schemas_cache

    @patch('src.core.schema_manager.storage_client')
    def test_get_schema_download_from_storage_not_found(self, mock_storage_client, temp_schema_dir):
        """Test schema download when not found in storage but base schema exists."""
        manager = SchemaManager()
        manager.load_base_schemas(temp_schema_dir)
        
        # Mock storage not found
        mock_storage_client.download.return_value = None
        
        schema = manager.get_schema("837P_5010_X222A1.json", "tenant-test")
        
        # Should fall back to base schema
        assert schema is not None
        assert isinstance(schema, ImplementationGuideSchema)
        assert schema.name == "837P_5010_X222A1"

    @patch('src.core.schema_manager.storage_client')
    def test_get_schema_download_from_storage_completely_not_found(self, mock_storage_client):
        """Test schema download when not found anywhere."""
        manager = SchemaManager()
        
        # Mock storage not found
        mock_storage_client.download.return_value = None
        
        schema = manager.get_schema("non_existent.json", "tenant-test")
        
        assert schema is None

    @patch('src.core.schema_manager.storage_client')
    def test_get_schema_download_invalid_json(self, mock_storage_client):
        """Test schema download with invalid JSON from storage."""
        manager = SchemaManager()
        
        # Mock storage returning invalid JSON
        mock_storage_client.download.return_value = b"invalid json content"
        
        schema = manager.get_schema("invalid.json", "tenant-test")
        
        assert schema is None

    @patch('src.core.schema_manager.storage_client')
    def test_get_schema_download_invalid_schema_format(self, mock_storage_client):
        """Test schema download with JSON that doesn't match schema format."""
        manager = SchemaManager()
        
        # Mock storage returning valid JSON but invalid schema
        invalid_schema = {"invalid": "schema", "format": "wrong"}
        mock_storage_client.download.return_value = json.dumps(invalid_schema).encode('utf-8')
        
        schema = manager.get_schema("invalid_format.json", "tenant-test")
        
        assert schema is None

    @patch('src.core.config.settings')
    def test_get_schema_lazy_load_base_schemas(self, mock_settings, temp_schema_dir):
        """Test lazy loading of base schemas when not already loaded."""
        manager = SchemaManager()
        
        # Ensure base schemas are not loaded
        manager._base_schemas = {}
        
        # Mock settings
        mock_settings.EDI_SCHEMA_DIRECTORY = str(temp_schema_dir)
        
        with patch.object(manager, 'load_base_schemas') as mock_load:
            schema = manager.get_schema("837P_5010_X222A1.json", "tenant-test")
            
            # Should attempt to load base schemas
            mock_load.assert_called_once_with(temp_schema_dir)

    def test_list_base_schemas(self, temp_schema_dir):
        """Test listing available base schemas."""
        manager = SchemaManager()
        manager.load_base_schemas(temp_schema_dir)
        
        schema_list = manager.list_base_schemas()
        
        assert isinstance(schema_list, list)
        assert len(schema_list) == 2
        assert "837P_5010_X222A1.json" in schema_list
        assert "835_5010_X221A1.json" in schema_list

    def test_list_base_schemas_empty(self):
        """Test listing base schemas when none are loaded."""
        manager = SchemaManager()
        
        schema_list = manager.list_base_schemas()
        
        assert isinstance(schema_list, list)
        assert len(schema_list) == 0


# Keep the existing fixture at the end
@pytest.fixture
def temp_schema_dir(tmp_path: Path) -> Path:
    schema_content = {
        "transactionName": "Test 837P",
        "version": "005010X222A1",
        "description": "A valid mock schema for testing.",
        "segmentDefinitions": {},
        "structure": []
    }
    schema_file = tmp_path / "test.837p.json"
    schema_file.write_text(json.dumps(schema_content))
    return tmp_path

def test_schema_manager_is_singleton():
    """Verify that the SchemaManager follows the singleton pattern."""
    manager1 = SchemaManager()
    manager2 = SchemaManager()
    assert manager1 is manager2

def test_load_base_schemas_successfully(temp_schema_dir: Path):
    """Test that a valid schema file is loaded and parsed correctly."""
    manager = SchemaManager()
    manager._base_schemas = {}
    manager._specialized_schemas_cache = {}
    
    manager.load_base_schemas(temp_schema_dir)
    
    schema = manager.get_schema("test.837p.json", tenant_id="any_tenant_id")
    
    assert schema is not None
    assert isinstance(schema, ImplementationGuideSchema)
    assert schema.transactionName == "Test 837P"

def test_get_schema_returns_none_for_unknown_version(temp_schema_dir: Path, mocker):
    """Test that requesting a non-existent version returns None."""
    manager = SchemaManager()
    manager._base_schemas = {}
    manager._specialized_schemas_cache = {}
    
    manager.load_base_schemas(temp_schema_dir)
    
    mocker.patch('src.core.storage.storage_client.download', return_value=None)
    
    assert manager.get_schema("unknown-version.json", tenant_id="any_tenant_id") is None

# --- THIS IS THE FIX ---
def test_load_schemas_handles_empty_directory(tmp_path: Path, mocker):
    """Test that the manager handles an empty directory gracefully."""
    manager = SchemaManager()
    manager._base_schemas = {}
    manager._specialized_schemas_cache = {}
    
    # Mock the storage client to prevent network calls
    mocker.patch('src.core.storage.storage_client.download', return_value=None)
    
    manager.load_base_schemas(tmp_path)
    
    # Now this call will use the mock and return instantly
    assert manager.get_schema("any.json", tenant_id="any_tenant_id") is None
    assert len(manager._base_schemas) == 0

def test_load_schemas_handles_invalid_json(tmp_path: Path):
    """Test that the manager logs an error but doesn't crash on invalid JSON."""
    invalid_file = tmp_path / "invalid.json"
    invalid_file.write_text("{'not_json': True,}")

    manager = SchemaManager()
    manager._base_schemas = {}
    manager._specialized_schemas_cache = {}
    
    manager.load_base_schemas(tmp_path)
    
    assert len(manager._base_schemas) == 0
# --- END OF FIX ---