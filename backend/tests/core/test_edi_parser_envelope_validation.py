import pytest
from src.core.edi_parser import EdiParser
from src.core.acknowledgements.ta1_defs import TA1NoteCode
from src.edi_schemas.edi_guide import ImplementationGuideSchema
from src.core.acknowledgements.ta1_validator import validate_interchange_envelope

pytestmark = pytest.mark.unit

VALID_ENVELOPE = (
    "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *240718*1200*^*00501*000000001*0*P*:~"
    "GS*HC*SENDER*RECEIVER*20240718*1200*1*X*005010X222A1~"
    "ST*837*0001~"
    "SE*1*0001~"
    "GE*1*1~"
    "IEA*1*000000001~"
)

def run_validation(edi_string: str, schema: ImplementationGuideSchema) -> list[TA1NoteCode]:
    parser = EdiParser(edi_string=edi_string, schema=schema)
    interchange = parser.parse()
    # Pass the raw string to the validator, as it now needs it for delimiter checks
    errors = validate_interchange_envelope(interchange, edi_string)
    return [e.note_code for e in errors]

def test_valid_envelope_has_no_errors(standalone_schema):
    errors = run_validation(VALID_ENVELOPE, standalone_schema)
    assert not errors

def test_icn_mismatch_produces_error_001(standalone_schema):
    edi = VALID_ENVELOPE.replace("IEA*1*000000001~", "IEA*1*999999999~")
    errors = run_validation(edi, standalone_schema)
    assert TA1NoteCode.ICN_MISMATCH_IN_HEADER_TRAILER in errors

def test_invalid_date_produces_error_014(standalone_schema):
    # Use a value with the same length to preserve ISA structure
    edi = VALID_ENVELOPE.replace("*240718*", "*BADATE*")
    errors = run_validation(edi, standalone_schema)
    assert TA1NoteCode.INVALID_INTERCHANGE_DATE in errors

# --- THIS IS THE FIX (Part 1) ---
def test_invalid_time_produces_error_015(standalone_schema):
    # Use a value with the same length but invalid format
    edi = VALID_ENVELOPE.replace("*1200*", "*9999*")
    errors = run_validation(edi, standalone_schema)
    assert TA1NoteCode.INVALID_INTERCHANGE_TIME in errors
# --- END OF FIX ---

def test_invalid_ack_requested_produces_error_019(standalone_schema):
    edi = VALID_ENVELOPE.replace("*0*P*:", "*X*P*:")
    errors = run_validation(edi, standalone_schema)
    assert TA1NoteCode.INVALID_ACKNOWLEDGMENT_REQUESTED in errors

def test_invalid_test_indicator_produces_error_020(standalone_schema):
    edi = VALID_ENVELOPE.replace("*P*:", "*X*:")
    errors = run_validation(edi, standalone_schema)
    assert TA1NoteCode.INVALID_TEST_INDICATOR in errors

def test_group_count_mismatch_produces_error_021(standalone_schema):
    edi = VALID_ENVELOPE.replace("IEA*1*", "IEA*5*")
    errors = run_validation(edi, standalone_schema)
    assert TA1NoteCode.INVALID_GROUP_COUNT in errors

def test_missing_iea_produces_error_022(standalone_schema):
    edi = VALID_ENVELOPE.split("IEA")[0]
    errors = run_validation(edi, standalone_schema)
    assert TA1NoteCode.INVALID_CONTROL_STRUCTURE in errors

def test_invalid_element_separator_produces_error_026(standalone_schema):
    # Construct an ISA where the character at index 3 is an alphanumeric 'A', which is invalid.
    # The rest of the segment is split by 'A', but the content remains the same to keep the length at 106.
    edi = "ISAA00A          A00A          AZZA SENDER        AZZA RECEIVER      A240718A1200A^A00501A000000001A0AP A:~" \
          "IEA*1*000000001~"
    assert len(edi.split('~')[0]) == 106
    
    errors = run_validation(edi, standalone_schema)
    assert TA1NoteCode.INVALID_ELEMENT_SEPARATOR in errors

def test_multiple_errors_are_detected(standalone_schema):
    edi = VALID_ENVELOPE.replace("*240718*", "*BADATE*").replace("IEA*1*000000001~", "IEA*1*999999999~")
    errors = run_validation(edi, standalone_schema)
    assert TA1NoteCode.INVALID_INTERCHANGE_DATE in errors
    assert TA1NoteCode.ICN_MISMATCH_IN_HEADER_TRAILER in errors
    assert len(errors) == 2