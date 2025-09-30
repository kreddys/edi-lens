import pytest
import json
from pathlib import Path
from schema_manager import SchemaManager

@pytest.fixture
def schema_dir(tmp_path: Path) -> Path:
    """Create a temporary directory with base and tenant-specific schemas."""
    # Base schema
    base_schema_content = {
        "transactionName": "837p",
        "version": "1.0",
        "description": "Base 837p Schema",
        "structure": []
    }
    (tmp_path / "base_schema.json").write_text(json.dumps(base_schema_content))

    # Tenant-specific schema
    tenant_dir = tmp_path / "tenant-specific" / "tenant-a"
    tenant_dir.mkdir(parents=True)
    tenant_schema_content = {
        "transactionName": "837p",
        "version": "1.1",
        "description": "Tenant A 837p Schema",
        "structure": []
    }
    (tenant_dir / "tenant_schema.json").write_text(json.dumps(tenant_schema_content))

    # Malformed schema
    (tmp_path / "malformed.json").write_text("{'invalid_json':}")

    return tmp_path

def test_schema_manager_init_and_load_base_schemas(schema_dir: Path):
    manager = SchemaManager(str(schema_dir))
    assert "base_schema.json" in manager._base_schemas
    assert "malformed.json" not in manager._base_schemas # Should fail to load

def test_get_schema_base(schema_dir: Path):
    manager = SchemaManager(str(schema_dir))
    schema = manager.get_schema("base_schema.json", "tenant-a")
    assert schema is not None
    assert schema.description == "Base 837p Schema"

def test_get_schema_tenant_specific(schema_dir: Path):
    manager = SchemaManager(str(schema_dir))
    schema = manager.get_schema("tenant_schema.json", "tenant-a")
    assert schema is not None
    assert schema.description == "Tenant A 837p Schema"

def test_get_schema_tenant_fallback_to_base(schema_dir: Path):
    manager = SchemaManager(str(schema_dir))
    schema = manager.get_schema("base_schema.json", "tenant-b")
    assert schema is not None
    assert schema.description == "Base 837p Schema"

def test_get_schema_not_found(schema_dir: Path):
    manager = SchemaManager(str(schema_dir))
    schema = manager.get_schema("non_existent_schema.json", "tenant-a")
    assert schema is None

def test_get_schema_caching(schema_dir: Path):
    manager = SchemaManager(str(schema_dir))

    # First call should load from file
    schema1 = manager.get_schema("tenant_schema.json", "tenant-a")
    assert "tenant-a/tenant_schema.json" in manager._tenant_schemas_cache

    # To prove it's cached, let's delete the file and get it again
    (schema_dir / "tenant-specific" / "tenant-a" / "tenant_schema.json").unlink()

    schema2 = manager.get_schema("tenant_schema.json", "tenant-a")
    assert schema2 is not None
    assert schema1 == schema2

def test_list_base_schemas(schema_dir: Path):
    manager = SchemaManager(str(schema_dir))
    base_schemas = manager.list_base_schemas()
    assert "base_schema.json" in base_schemas
    assert "malformed.json" not in base_schemas

def test_reload_schemas(schema_dir: Path):
    manager = SchemaManager(str(schema_dir))
    assert "new_schema.json" not in manager.list_base_schemas()

    # Add a new schema file
    new_schema_content = {
        "transactionName": "270",
        "version": "1.0",
        "description": "New 270 Schema",
        "structure": []
    }
    (schema_dir / "new_schema.json").write_text(json.dumps(new_schema_content))

    manager.reload_schemas()

    assert "new_schema.json" in manager.list_base_schemas()
    new_schema = manager.get_schema("new_schema.json", "any-tenant")
    assert new_schema is not None
    assert new_schema.description == "New 270 Schema"

def test_schema_manager_with_non_existent_path():
    manager = SchemaManager("/non/existent/path")
    assert not manager._base_schemas
    assert manager.get_schema("any.json", "any-tenant") is None
