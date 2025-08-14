# FILE: backend/src/services/schema_validation_service.py

import logging

from src.core.schema_manager import SchemaManager

logger = logging.getLogger(__name__)

class SchemaValidationService:
    """Service for validating EDI schemas."""

    def __init__(self):
        self.schema_manager = SchemaManager()

    async def validate_schema(self, schema_name: str, tenant_id: str) -> bool:
        """
        Validate an EDI schema.

        Args:
            schema_name: The name of the schema to validate.
            tenant_id: The tenant identifier.

        Returns:
            True if the schema is valid, False otherwise.
        """
        try:
            logger.info(f"Validating schema: {schema_name}")

            schema = self.schema_manager.get_schema(schema_name, tenant_id)
            if not schema:
                return False

            # The schema manager already validates the schema on load, so if it exists, it's valid.
            logger.info(f"Schema '{schema_name}' is valid.")
            return True

        except Exception as e:
            logger.error(f"Schema validation failed: {e}", exc_info=True)
            return False
