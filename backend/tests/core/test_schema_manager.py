import pytest
from pathlib import Path
import json

from src.core.schema_manager import SchemaManager
from src.edi_schemas.edi_guide import ImplementationGuideSchema

# Create a temporary directory structure for tests
@pytest.fixture
def temp_schema_dir(tmp_path: Path) -> Path:
    schema_content = {
        "transactionName": "Test 837P",
        "segmentDefinitions": {
            "GS": {
                "name": "Functional Group Header",
                "usage": "R", "pos": "100", "max_use": 1,
                "elements": [],
                "elementsByXid": {
                    "GS08": {
                        "xid": "GS08", "data_ele": 480, "name": "Version", "usage": "R", "seq": "08",
                        "valid_codes": { "code": ["005010X222A1"] }
                    }
                }
            },
            "ST": { "name": "Transaction Set Header", "usage": "R", "pos": "050", "max_use": 1, "elements": [], "elementsByXid": {} }
        },
        "structure": [
            { "type": "segment", "xid": "ST", "pos": "050", "usage": "R", "max_use": 1, "name": "Transaction Set Header" }
        ]
    }
    schema_file = tmp_path / "test.837p.json"
    schema_file.write_text(json.dumps(schema_content))
    return tmp_path

def test_schema_manager_is_singleton():
    """Verify that the SchemaManager follows the singleton pattern."""
    manager1 = SchemaManager()
    manager2 = SchemaManager()
    assert manager1 is manager2

def test_load_schemas_successfully(temp_schema_dir: Path):
    """Test that a valid schema file is loaded and parsed correctly."""
    manager = SchemaManager()
    # Reset for isolated test
    manager._schemas = {}
    
    manager.load_schemas(temp_schema_dir)
    
    # The key should be the GS08 version
    schema = manager.get_schema("005010X222A1")
    
    assert schema is not None
    assert isinstance(schema, ImplementationGuideSchema)
    assert schema.transactionName == "Test 837P"
    assert "ST" in schema.segmentDefinitions
    assert len(schema.structure) == 1

def test_get_schema_returns_none_for_unknown_version(temp_schema_dir: Path):
    """Test that requesting a non-existent version returns None."""
    manager = SchemaManager()
    manager._schemas = {} # Reset
    manager.load_schemas(temp_schema_dir)
    
    assert manager.get_schema("unknown-version") is None

def test_load_schemas_handles_empty_directory(tmp_path: Path):
    """Test that the manager handles an empty or non-existent directory gracefully."""
    manager = SchemaManager()
    manager._schemas = {} # Reset
    
    manager.load_schemas(tmp_path)
    assert manager.get_schema("005010X222A1") is None

def test_load_schemas_handles_invalid_json(tmp_path: Path):
    """Test that the manager logs an error but doesn't crash on invalid JSON."""
    invalid_file = tmp_path / "invalid.json"
    invalid_file.write_text("{'not_json': True,}") # Invalid JSON with trailing comma

    manager = SchemaManager()
    manager._schemas = {} # Reset
    manager.load_schemas(tmp_path)
    
    # Should still be empty as the only file failed to load
    assert len(manager._schemas) == 0