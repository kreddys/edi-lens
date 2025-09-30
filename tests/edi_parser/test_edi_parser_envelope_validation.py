import pytest
from edi_parser import EdiParser
from ta1_defs import TA1NoteCode
from edi_schema_models import ImplementationGuideSchema
from ta1_validator import validate_interchange_envelope

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
    print(f" edi_string: {edi_string}")
    parser = EdiParser(edi_string=edi_string, schema=schema)
    interchange = parser.parse()
    # Pass the raw string to the validator, as it now needs it for delimiter checks
    errors = validate_interchange_envelope(interchange, edi_string)
    print(f"errors: {errors}")
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

def test_invalid_segment_terminator_produces_error_004(standalone_schema):
    edi = VALID_ENVELOPE.replace("~", "A")
    errors = run_validation(edi, standalone_schema)
    assert TA1NoteCode.INVALID_SEGMENT_TERMINATOR in errors

def test_invalid_component_separator_produces_error_027(standalone_schema):
    edi = VALID_ENVELOPE.replace(":~", "A~")
    errors = run_validation(edi, standalone_schema)
    assert TA1NoteCode.INVALID_COMPONENT_SEPARATOR in errors

def test_invalid_sender_id_qualifier_produces_error_005(standalone_schema):
    edi = VALID_ENVELOPE.replace("*ZZ*SENDER", "*XX*SENDER")
    errors = run_validation(edi, standalone_schema)
    assert TA1NoteCode.INVALID_SENDER_ID_QUALIFIER in errors

def test_invalid_sender_id_produces_error_006(standalone_schema):
    edi = VALID_ENVELOPE.replace("*SENDER         *", "*               *")
    errors = run_validation(edi, standalone_schema)
    assert TA1NoteCode.INVALID_SENDER_ID in errors

def test_invalid_receiver_id_qualifier_produces_error_007(standalone_schema):
    edi = VALID_ENVELOPE.replace("*ZZ*RECEIVER", "*XX*RECEIVER")
    errors = run_validation(edi, standalone_schema)
    assert TA1NoteCode.INVALID_RECEIVER_ID_QUALIFIER in errors

def test_invalid_receiver_id_produces_error_008(standalone_schema):
    edi = VALID_ENVELOPE.replace("*RECEIVER       *", "*               *")
    errors = run_validation(edi, standalone_schema)
    assert TA1NoteCode.INVALID_RECEIVER_ID in errors

def test_invalid_auth_qualifier_produces_error_010(standalone_schema):
    edi = VALID_ENVELOPE.replace("ISA*00*", "ISA*XX*")
    errors = run_validation(edi, standalone_schema)
    assert TA1NoteCode.INVALID_AUTH_QUALIFIER in errors

def test_invalid_auth_value_produces_error_011(standalone_schema):
    edi = VALID_ENVELOPE.replace("ISA*00*          *", "ISA*03*          *")
    errors = run_validation(edi, standalone_schema)
    assert TA1NoteCode.INVALID_AUTH_VALUE in errors

def test_invalid_security_qualifier_produces_error_012(standalone_schema):
    edi = VALID_ENVELOPE.replace("*00*          *ZZ*", "*XX*          *ZZ*")
    errors = run_validation(edi, standalone_schema)
    assert TA1NoteCode.INVALID_SECURITY_QUALIFIER in errors

def test_invalid_security_value_produces_error_013(standalone_schema):
    edi = VALID_ENVELOPE.replace("*00*          *ZZ*", "*01*          *ZZ*")
    errors = run_validation(edi, standalone_schema)
    assert TA1NoteCode.INVALID_SECURITY_VALUE in errors

def test_invalid_interchange_standards_id_produces_error_016(standalone_schema):
    edi = VALID_ENVELOPE.replace("*^*", "*X*")
    errors = run_validation(edi, standalone_schema)
    assert TA1NoteCode.INVALID_INTERCHANGE_STANDARDS_ID in errors

def test_invalid_interchange_version_id_produces_error_017(standalone_schema):
    edi = VALID_ENVELOPE.replace("*00501*", "*0050 *")
    errors = run_validation(edi, standalone_schema)
    assert TA1NoteCode.INVALID_INTERCHANGE_VERSION_ID in errors

def test_invalid_interchange_control_number_produces_error_018(standalone_schema):
    edi = VALID_ENVELOPE.replace("*000000001*", "*00000000X*")
    errors = run_validation(edi, standalone_schema)
    assert TA1NoteCode.INVALID_INTERCHANGE_CONTROL_NUMBER in errors

def test_invalid_group_count_with_non_integer_produces_error_021(standalone_schema):
    edi = VALID_ENVELOPE.replace("IEA*1*", "IEA*A*")
    errors = run_validation(edi, standalone_schema)
    assert TA1NoteCode.INVALID_GROUP_COUNT in errors
