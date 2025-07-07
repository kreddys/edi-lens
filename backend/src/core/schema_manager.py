import json
import logging
from pathlib import Path
from typing import Dict, Optional

# --- THIS IS THE FIX ---
from src.edi_schemas.edi_guide import ImplementationGuideSchema

logger = logging.getLogger(__name__)

class SchemaManager:
    """
    A singleton class to load, manage, and provide access to EDI implementation
    guide schemas from JSON definition files.
    """
    _instance = None
    _schemas: Dict[str, ImplementationGuideSchema]

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SchemaManager, cls).__new__(cls)
            cls._instance._schemas = {}
        return cls._instance

    def load_schemas(self, schema_dir: Path):
        """
        Loads all .json schema files from a given directory into memory.
        This should be called once on application startup.
        """
        if not schema_dir.is_dir():
            logger.warning(f"Schema directory not found: {schema_dir}")
            return

        logger.info(f"Loading EDI schemas from: {schema_dir}")
        for file_path in schema_dir.glob("*.json"):
            try:
                with open(file_path, 'r') as f:
                    schema_data = json.load(f)
                    schema = ImplementationGuideSchema.model_validate(schema_data)
                    
                    # Use the GS08 version as the key (e.g., '005010X222A1')
                    schema_key = schema.get_gs08_version()
                    if schema_key:
                        self._schemas[schema_key] = schema
                        logger.info(f"Successfully loaded schema: {schema.transactionName} (Version: {schema_key})")
                    else:
                        logger.warning(f"Could not determine GS08 version key for schema file: {file_path.name}")
            except Exception as e:
                logger.error(f"Failed to load or parse schema from {file_path.name}: {e}", exc_info=True)
        
        if not self._schemas:
            logger.warning("No EDI implementation guide schemas were loaded.")

    def get_schema(self, guide_version: str) -> Optional[ImplementationGuideSchema]:
        """
        Retrieves a loaded schema by its implementation guide version (e.g., GS08).
        """
        return self._schemas.get(guide_version)

# Create a single, global instance of the manager
schema_manager = SchemaManager()