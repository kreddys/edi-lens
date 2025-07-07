# backend/tests/core/test_edi_schema_models.py
import pytest

from src.edi_schemas.edi_guide import ImplementationGuideSchema, SegmentDefinition

# Mark this entire file as belonging to the 'unit' test suite
pytestmark = pytest.mark.unit

def test_get_gs08_version_success():
    """
    Tests that the helper method correctly extracts the GS08 version code
    from a mock schema object.
    """
    mock_schema_data = {
        "transactionName": "Test 837P",
        "segmentDefinitions": {
            "GS": {
                "name": "Functional Group Header", "usage": "R", "pos": "100", "max_use": 1,
                "elements": [],
                "elementsByXid": {
                    "GS08": {
                        "xid": "GS08", "data_ele": 480, "name": "Version", "usage": "R", "seq": "08",
                        "valid_codes": { "code": ["005010X222A1"] }
                    }
                }
            }
        },
        "structure": []
    }
    schema = ImplementationGuideSchema.model_validate(mock_schema_data)
    assert schema.get_gs08_version() == "005010X222A1"

def test_get_gs08_version_returns_none_if_missing():
    """
    Tests that the helper method returns None if the GS or GS08 definition is missing.
    """
    # Schema missing GS segment completely
    mock_schema_data = {
        "transactionName": "Test 837P",
        "segmentDefinitions": {},
        "structure": []
    }
    schema = ImplementationGuideSchema.model_validate(mock_schema_data)
    assert schema.get_gs08_version() is None

    # Schema with GS but missing GS08
    mock_schema_data_no_gs08 = {
        "transactionName": "Test 837P",
        "segmentDefinitions": {
            "GS": {
                "name": "Functional Group Header", "usage": "R", "pos": "100", "max_use": 1,
                "elements": [],
                "elementsByXid": {}
            }
        },
        "structure": []
    }
    schema = ImplementationGuideSchema.model_validate(mock_schema_data_no_gs08)
    assert schema.get_gs08_version() is None