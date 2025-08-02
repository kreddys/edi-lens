import json
import logging
from pathlib import Path
from typing import Dict, Optional

from src.edi_schemas.edi_guide import ImplementationGuideSchema
from src.core.storage import storage_client # Import the new client

logger = logging.getLogger(__name__)

class SchemaManager:
    _instance = None
    _base_schemas: Dict[str, ImplementationGuideSchema]
    _specialized_schemas_cache: Dict[str, ImplementationGuideSchema]

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SchemaManager, cls).__new__(cls)
            cls._instance._base_schemas = {}
            cls._instance._specialized_schemas_cache = {}
        return cls._instance

    def load_base_schemas(self, schema_dir: Path):
        """Loads only the base schemas from the local filesystem at startup."""
        if not schema_dir.is_dir():
            logger.warning(f"Base schema directory not found: {schema_dir}")
            return
        logger.info(f"Loading BASE EDI schemas from: {schema_dir}")
        for file_path in schema_dir.glob("*.json"):
            try:
                with open(file_path, 'r') as f:
                    schema_data = json.load(f)
                    schema = ImplementationGuideSchema.model_validate(schema_data)
                    # Use filename as the key now for simplicity and consistency
                    self._base_schemas[file_path.name] = schema
                    logger.info(f"Successfully loaded BASE schema: {file_path.name}")
            except Exception as e:
                logger.error(f"Failed to load or parse base schema from {file_path.name}: {e}")

    def get_schema(self, schema_name: str, tenant_id: str) -> Optional[ImplementationGuideSchema]:
        """
        Retrieves a schema. It checks for a base schema first, then the in-memory cache
        for specialized schemas, and finally falls back to downloading from object storage.
        """
        # 1. Check for base schema
        if schema_name in self._base_schemas:
            return self._base_schemas[schema_name]

        # 2. Check in-memory cache for specialized schema
        cache_key = f"{tenant_id}/{schema_name}"
        if cache_key in self._specialized_schemas_cache:
            return self._specialized_schemas_cache[cache_key]

        # 3. Download from object storage
        logger.info(f"Schema '{schema_name}' for tenant '{tenant_id}' not in cache. Fetching from storage.")
        s3_key = f"{tenant_id}/schemas/{schema_name}"
        schema_bytes = storage_client.download(s3_key)

        if not schema_bytes:
            logger.warning(f"Schema '{schema_name}' not found for tenant '{tenant_id}' in object storage.")
            return None
        
        try:
            schema_data = json.loads(schema_bytes)
            schema = ImplementationGuideSchema.model_validate(schema_data)
            self._specialized_schemas_cache[cache_key] = schema # Cache it
            return schema
        except Exception as e:
            logger.error(f"Failed to parse specialized schema {schema_name} from storage: {e}")
            return None

    def list_base_schemas(self) -> list[str]:
        return list(self._base_schemas.keys())

# Singleton instance
schema_manager = SchemaManager()