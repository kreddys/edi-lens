# Ported and adapted from backend/src/core/schema_manager.py
import json
import logging
from pathlib import Path
from typing import Dict, Optional

# Note: For NiFi processors, we'll need to adapt the schema models
# For now, we'll use a simplified schema representation
from edi_schema_models import ImplementationGuideSchema

logger = logging.getLogger(__name__)

class SchemaManager:
    """
    Schema manager adapted for NiFi processors.
    Handles loading EDI schemas from the local filesystem and supports tenant-specific schemas.
    """
    
    def __init__(self, schema_base_path: str = "/opt/nifi/schemas"):
        self.schema_base_path = Path(schema_base_path)
        self._base_schemas: Dict[str, ImplementationGuideSchema] = {}
        self._tenant_schemas_cache: Dict[str, ImplementationGuideSchema] = {}
        self._load_base_schemas()
    
    def _load_base_schemas(self):
        """Load base schemas from the schema directory."""
        if not self.schema_base_path.exists():
            logger.warning(f"Schema base path does not exist: {self.schema_base_path}")
            return
            
        logger.info(f"Loading base EDI schemas from: {self.schema_base_path}")
        
        for schema_file in self.schema_base_path.glob("*.json"):
            try:
                with open(schema_file, 'r') as f:
                    schema_data = json.load(f)
                    schema = ImplementationGuideSchema.model_validate(schema_data)
                    self._base_schemas[schema_file.name] = schema
                    logger.info(f"Loaded base schema: {schema_file.name}")
            except Exception as e:
                logger.error(f"Failed to load schema {schema_file.name}: {e}")
    
    def get_schema(self, schema_name: str, tenant_id: str) -> Optional[ImplementationGuideSchema]:
        """
        Get schema for tenant. Checks tenant-specific schemas first, then falls back to base schemas.
        
        Args:
            schema_name: Name of the schema file (e.g., "270.5010.X279.A1.json")
            tenant_id: Tenant identifier
            
        Returns:
            ImplementationGuideSchema or None if not found
        """
        # Check tenant-specific schema cache
        cache_key = f"{tenant_id}/{schema_name}"
        if cache_key in self._tenant_schemas_cache:
            return self._tenant_schemas_cache[cache_key]
        
        # Try to load tenant-specific schema
        tenant_schema_path = self.schema_base_path / "tenant-specific" / tenant_id / schema_name
        if tenant_schema_path.exists():
            try:
                with open(tenant_schema_path, 'r') as f:
                    schema_data = json.load(f)
                    schema = ImplementationGuideSchema.model_validate(schema_data)
                    self._tenant_schemas_cache[cache_key] = schema
                    logger.info(f"Loaded tenant-specific schema: {tenant_id}/{schema_name}")
                    return schema
            except Exception as e:
                logger.error(f"Failed to load tenant schema {tenant_id}/{schema_name}: {e}")
        
        # Fall back to base schema
        if schema_name in self._base_schemas:
            logger.info(f"Using base schema for tenant {tenant_id}: {schema_name}")
            return self._base_schemas[schema_name]
        
        logger.error(f"Schema not found: {schema_name} for tenant {tenant_id}")
        return None
    
    def get_base_schema(self, schema_name: str) -> Optional[ImplementationGuideSchema]:
        """
        Get base schema by name.
        
        Args:
            schema_name: Name of the schema file (e.g., "837.5010.X222.A1.json")
            
        Returns:
            ImplementationGuideSchema or None if not found
        """
        return self._base_schemas.get(schema_name)
    
    def list_base_schemas(self) -> list[str]:
        """List available base schema names."""
        return list(self._base_schemas.keys())
    
    def reload_schemas(self):
        """Reload all schemas from filesystem."""
        self._base_schemas.clear()
        self._tenant_schemas_cache.clear()
        self._load_base_schemas()