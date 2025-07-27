# FILE: backend/tests/core/test_schema_manager.py
import pytest
from pathlib import Path
import json

from src.core.schema_manager import SchemaManager
from src.edi_schemas.edi_guide import ImplementationGuideSchema

pytestmark = pytest.mark.unit

@pytest.fixture
def temp_schema_dir(tmp_path: Path) -> Path:
    # --- THIS IS THE FIX: Use a valid mock schema content ---
    schema_content = {
        "transactionName": "Test 837P",
        "version": "005010X222A1",
        "description": "A valid mock schema for testing.",
        "segmentDefinitions": {
            "ST": { "id": "ST", "name": "Transaction Set Header", "description": "", "usage": "R", "max_use": 1, "elements": [] }
        },
        "structure": [
            {
                "type": "loop",
                "xid": "ST_LOOP",
                "name": "Transaction Set",
                "usage": "R",
                "repeat": 1,
                "children": [
                    {
                        "type": "segment",
                        "xid": "ST",
                        "name": "Transaction Set Header",
                        "usage": "R",
                        "max_use": 1,
                        "segmentDefinitionId": "ST"
                    }
                ]
            }
        ]
    }
    schema_file = tmp_path / "test.837p.json"
    schema_file.write_text(json.dumps(schema_content))
    return tmp_path

# The rest of the tests in this file can remain unchanged.
def test_schema_manager_is_singleton():
    """Verify that the SchemaManager follows the singleton pattern."""
    manager1 = SchemaManager()
    manager2 = SchemaManager()
    assert manager1 is manager2

def test_load_schemas_successfully(temp_schema_dir: Path):
    """Test that a valid schema file is loaded and parsed correctly."""
    manager = SchemaManager()
    manager._schemas = {}
    manager._schemas_by_filename = {} # Also reset this for isolation
    
    manager.load_schemas(temp_schema_dir)
    
    schema = manager.get_schema("005010X222A1")
    
    assert schema is not None
    assert isinstance(schema, ImplementationGuideSchema)
    assert schema.transactionName == "Test 837P"
    assert "ST" in schema.segmentDefinitions

def test_get_schema_returns_none_for_unknown_version(temp_schema_dir: Path):
    """Test that requesting a non-existent version returns None."""
    manager = SchemaManager()
    manager._schemas = {}
    manager._schemas_by_filename = {}
    manager.load_schemas(temp_schema_dir)
    
    assert manager.get_schema("unknown-version") is None

def test_load_schemas_handles_empty_directory(tmp_path: Path):
    """Test that the manager handles an empty or non-existent directory gracefully."""
    manager = SchemaManager()
    manager._schemas = {}
    manager._schemas_by_filename = {}
    
    manager.load_schemas(tmp_path)
    assert manager.get_schema("005010X222A1") is None

def test_load_schemas_handles_invalid_json(tmp_path: Path):
    """Test that the manager logs an error but doesn't crash on invalid JSON."""
    invalid_file = tmp_path / "invalid.json"
    invalid_file.write_text("{'not_json': True,}")

    manager = SchemaManager()
    manager._schemas = {}
    manager._schemas_by_filename = {}
    manager.load_schemas(tmp_path)
    
    assert len(manager._schemas) == 0