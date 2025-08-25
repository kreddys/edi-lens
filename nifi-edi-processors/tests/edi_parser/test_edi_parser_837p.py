# FILE: backend/tests/core/test_edi_parser_837p.py
import pytest
from edi_parser import EdiParser
from edi_schema_models import ImplementationGuideSchema

pytestmark = pytest.mark.unit

# --- Basic Compliance and Structural Tests ---

def test_compliant_837p_is_parsed_without_errors(standalone_schema: ImplementationGuideSchema, valid_837p_edi_string: str):
    """
    Tests that a compliant EDI file is parsed with no structural or content validation errors.
    """
    parser = EdiParser(edi_string=valid_837p_edi_string, schema=standalone_schema)
    interchange = parser.parse()
    
    transaction = interchange.functional_groups[0].transactions[0]
    all_errors = interchange.errors + transaction.errors
    
    def collect_errors(loop):
        errors = list(loop.errors)
        for sub_loops in loop.loops.values():
            for sub_loop in sub_loops:
                errors.extend(collect_errors(sub_loop))
        for segment in loop.segments:
            errors.extend(segment.errors)
        return errors

    all_errors.extend(collect_errors(transaction.body))
    assert len(all_errors) == 0, f"Parser found unexpected errors: {[e.message for e in all_errors]}"

def test_validator_finds_missing_required_loop(standalone_schema: ImplementationGuideSchema, valid_837p_edi_string: str):
    """
    Tests that the parser correctly identifies a missing required loop (e.g., 1000A Submitter).
    """
    invalid_edi = valid_837p_edi_string.replace("NM1*41*2*PREMIER BILLING*****46*SUBMITTER1~\n", "")
    parser = EdiParser(edi_string=invalid_edi, schema=standalone_schema)
    interchange = parser.parse()

    transaction = interchange.functional_groups[0].transactions[0]
    transaction_body = transaction.body
    
    assert len(transaction_body.errors) > 0
    
    # The assertion now matches the new, more descriptive error message.
    expected_error_msg = "Required segment or loop '1000A' (SUBMITTER NAME) is missing from loop 'ST_LOOP'."
    assert any(expected_error_msg in e.message for e in transaction_body.errors)

# --- Advanced Data-Level Validation Tests ---

def test_validator_fails_on_min_length_error(standalone_schema: ImplementationGuideSchema, valid_837p_edi_string: str):
    """
    Tests that an element (BHT04) with a required length of 8 fails when the data is too short.
    """
    invalid_edi = valid_837p_edi_string.replace("*20240715*", "*202407*")
    parser = EdiParser(edi_string=invalid_edi, schema=standalone_schema)
    interchange = parser.parse()

    bht_segment = interchange.functional_groups[0].transactions[0].body.get_segment("BHT")
    assert len(bht_segment.errors) > 0
    error_messages = [e.message for e in bht_segment.errors]
    assert any("BHT04" in msg and "shorter than min length 8" in msg for msg in error_messages)

def test_validator_fails_on_max_length_error(standalone_schema: ImplementationGuideSchema, valid_837p_edi_string: str):
    """
    Tests that an element (BHT04) with a required length of 8 fails when the data is too long.
    """
    invalid_edi = valid_837p_edi_string.replace("*20240715*", "*2024071500*")
    parser = EdiParser(edi_string=invalid_edi, schema=standalone_schema)
    interchange = parser.parse()

    bht_segment = interchange.functional_groups[0].transactions[0].body.get_segment("BHT")
    assert len(bht_segment.errors) > 0
    error_messages = [e.message for e in bht_segment.errors]
    assert any("BHT04" in msg and "longer than max length 8" in msg for msg in error_messages)

def test_validator_finds_invalid_code_value(standalone_schema: ImplementationGuideSchema, valid_837p_edi_string: str):
    """
    Tests that the validator correctly identifies an element with a value not in its defined code set.
    """
    valid_sv1 = "SV1*HC>99213*125*UN*1***1**Y~"
    invalid_sv1 = "SV1*HC>99213*125*UN*1***1**X~"
    invalid_edi = valid_837p_edi_string.replace(valid_sv1, invalid_sv1)
    
    parser = EdiParser(edi_string=invalid_edi, schema=standalone_schema)
    interchange = parser.parse()

    service_line_loop = interchange.functional_groups[0].transactions[0].body.get_loop('2000A').get_loop('2000B').get_loop('2300').get_loop('2400')
    sv1_segment = service_line_loop.get_segment('SV1')

    assert len(sv1_segment.errors) > 0
    error_messages = [e.message for e in sv1_segment.errors]
    assert any("Element 'SV109'" in msg and "Invalid code value" in msg for msg in error_messages)

def test_validator_fails_on_date_format_error(standalone_schema: ImplementationGuideSchema, valid_837p_edi_string: str):
    """
    Tests that a date element (BHT04) with a required CCYYMMDD format fails validation with an invalid format.
    """
    invalid_edi = valid_837p_edi_string.replace("20240715", "INVALID_")
    parser = EdiParser(edi_string=invalid_edi, schema=standalone_schema)
    interchange = parser.parse()

    bht_segment = interchange.functional_groups[0].transactions[0].body.get_segment("BHT")
    assert len(bht_segment.errors) > 0
    error_messages = [e.message for e in bht_segment.errors]
    assert any("BHT04" in msg and "does not match expected format 'CCYYMMDD'" in msg for msg in error_messages)

def test_validator_fails_on_contextual_code_error(standalone_schema: ImplementationGuideSchema, valid_837p_edi_string: str):
    """
    Tests that a contextual code validation fails. The base NM1 allows many codes for NM101,
    but in the 2010AA loop, it must be '85'.
    """
    invalid_edi = valid_837p_edi_string.replace(
        "NM1*85*2*BILLING PROVIDER*****XX*1234567890~",
        "NM1*85*2*BILLING PROVIDER*****ZZ*1234567890~"
    )
    parser = EdiParser(edi_string=invalid_edi, schema=standalone_schema)
    interchange = parser.parse()

    # Collect all errors from the interchange to find the contextual validation error
    def collect_all_errors(loop):
        all_errors = list(loop.errors)
        for sub_loops in loop.loops.values():
            for sub_loop in sub_loops:
                all_errors.extend(collect_all_errors(sub_loop))
        for segment in loop.segments:
            all_errors.extend(segment.errors)
        return all_errors

    transaction = interchange.functional_groups[0].transactions[0]
    all_errors = list(interchange.errors) + list(transaction.errors) + collect_all_errors(transaction.body)
    error_messages = [e.message for e in all_errors]
    
    # Look for the contextual validation error for NM108 in the parsed errors
    assert any("NM108" in msg and "Invalid code value" in msg and "Allowed: XX" in msg for msg in error_messages), f"Expected contextual error not found. Errors: {error_messages}"

def test_validator_fails_on_composite_sub_element_error(standalone_schema: ImplementationGuideSchema, valid_837p_edi_string: str):
    """
    Tests that validation fails for an invalid code in a composite sub-element (CLM05-2).
    """
    invalid_edi = valid_837p_edi_string.replace("11>B>1", "11>Z>1")
    parser = EdiParser(edi_string=invalid_edi, schema=standalone_schema)
    interchange = parser.parse()

    claim_loop = interchange.functional_groups[0].transactions[0].body.get_loop("2000A").get_loop("2000B").get_loop("2300")
    clm_segment = claim_loop.get_segment("CLM")

    assert len(clm_segment.errors) > 0
    error_messages = [e.message for e in clm_segment.errors]
    assert any("CLM05-2" in msg and "Invalid code value" in msg and "Allowed: B" in msg for msg in error_messages)