import json
import logging
from pathlib import Path
from typing import Dict, Optional

from src.edi_schemas.edi_guide import ImplementationGuideSchema

logger = logging.getLogger(__name__)

class SchemaManager:
    """
    A singleton class to load, manage, and provide access to EDI implementation
    guide schemas from JSON definition files.
    """
    _instance = None
    _schemas: Dict[str, ImplementationGuideSchema]
    _schemas_by_filename: Dict[str, ImplementationGuideSchema] # <-- ADD THIS

    def __new__(cls):
        if cls._instance is None:
            logger.debug("Creating new SchemaManager instance.")
            cls._instance = super(SchemaManager, cls).__new__(cls)
            # Initialize attributes here, as __init__ might be called multiple times.
            cls._instance._schemas = {}
            cls._instance._schemas_by_filename = {} # <-- AND INITIALIZE THIS
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
                    
                    # Store by filename for the new method
                    self._schemas_by_filename[file_path.name] = schema

                    # Use the GS08 version as the key (e.g., '005010X222A1')
                    schema_key = schema.get_version_key()
                    if schema_key:
                        self._schemas[schema_key] = schema
                        logger.info(f"Successfully loaded schema: {schema.transactionName} (Version: {schema_key}) from {file_path.name}")
                    else:
                        logger.warning(f"Could not determine version key for schema file: {file_path.name}")
            except Exception as e:
                logger.error(f"Failed to load or parse schema from {file_path.name}: {e}", exc_info=True)
        
        if not self._schemas:
            logger.warning("No EDI implementation guide schemas were loaded.")

    def get_schema(self, guide_version: str) -> Optional[ImplementationGuideSchema]:
        """
        Retrieves a loaded schema by its implementation guide version (e.g., GS08).
        """
        return self._schemas.get(guide_version)

    # --- THIS IS THE NEW METHOD TO ADD ---
    def get_schema_by_name(self, filename: str) -> Optional[ImplementationGuideSchema]:
        """
        Retrieves a loaded schema by its filename.
        """
        return self._schemas_by_filename.get(filename)
    # --- END OF NEW METHOD ---

# Create the singleton instance for the application to import and use.
# This makes it easy to access the single instance from anywhere in the app.
schema_manager = SchemaManager()