# FILE: backend/tests/core/test_edi_schema_models.py
import pytest
from src.edi_schemas.edi_guide import ImplementationGuideSchema

pytestmark = pytest.mark.unit

# --- THIS IS THE FIX: A minimal, but structurally VALID, mock schema ---
# It includes the 'version' and 'description' fields, and a valid 'structure' array.
VALID_MOCK_SCHEMA_DATA = {
    "transactionName": "Test 837P",
    "version": "005010X222A1",
    "description": "A valid mock schema for testing.",
    "segmentDefinitions": {
        "GS": {
            "id": "GS", "name": "Functional Group Header", "description": "", "usage": "R", "max_use": 1,
            "elements": [
                { "xid": "GS08", "data_ele": "480", "name": "Version", "usage": "R", "seq": 8, "dataType": "AN",
                  "valid_codes": [{"code": "005010X222A1", "description": "Version"}] }
            ]
        }
    },
    "structure": [] # An empty structure is valid
}

MINIMAL_INVALID_SCHEMA = {
    "transactionName": "Test 837P",
    "version": "005010X222A1",
    "description": "An invalid mock schema for testing.",
    "segmentDefinitions": {},
    "structure": []
}

def test_get_version_key_success():
    """
    Tests that the helper method correctly extracts the version key.
    """
    schema = ImplementationGuideSchema.model_validate(VALID_MOCK_SCHEMA_DATA)
    assert schema.get_version_key() == "005010X222A1"

def test_get_version_key_returns_version():
    """
    Tests that the helper returns the version even if GS is missing,
    as it's a top-level required field now.
    """
    schema = ImplementationGuideSchema.model_validate(MINIMAL_INVALID_SCHEMA)
    assert schema.get_version_key() == "005010X222A1"