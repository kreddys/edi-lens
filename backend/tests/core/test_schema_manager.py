import pytest
from pathlib import Path
import json

from src.core.schema_manager import SchemaManager
from src.edi_schemas.edi_guide import ImplementationGuideSchema

pytestmark = [pytest.mark.unit]

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