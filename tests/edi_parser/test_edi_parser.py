# FILE: backend/tests/core/test_edi_parser.py
import pytest
from edi_parser import EdiParser
from edi_schema_models import ImplementationGuideSchema

pytestmark = pytest.mark.unit

# The SIMPLE_837P_EDI constant can be removed as we will now use the conftest fixture for all relevant tests.

# This test was already correct, but we'll include it for completeness
def test_parser_creates_valid_cdm_interchange(standalone_schema: ImplementationGuideSchema, valid_837p_edi_string: str):
    parser = EdiParser(edi_string=valid_837p_edi_string, schema=standalone_schema)
    interchange = parser.parse()
    assert interchange is not None
    assert len(parser._collect_all_errors(interchange)) == 0, "Parser found unexpected errors in a valid file."

# This test was also correct
def test_parser_identifies_loops_correctly(standalone_schema: ImplementationGuideSchema, valid_837p_edi_string: str):
    parser = EdiParser(edi_string=valid_837p_edi_string, schema=standalone_schema)
    interchange = parser.parse()
    
    transaction = interchange.functional_groups[0].transactions[0]
    st_loop = transaction.body

    loop_2000a = st_loop.get_loop('2000A')
    assert loop_2000a is not None and loop_2000a.loop_id == '2000A'

    loop_2000b = loop_2000a.get_loop('2000B')
    assert loop_2000b is not None and loop_2000b.loop_id == '2000B'

    loop_2300 = loop_2000b.get_loop('2300')
    assert loop_2300 is not None and loop_2300.loop_id == '2300'

    loop_2400 = loop_2300.get_loop('2400')
    assert loop_2400 is not None and any(s.segment_id == 'SV1' for s in loop_2400.segments)

def test_parser_handles_incomplete_edi_gracefully(standalone_schema: ImplementationGuideSchema, valid_837p_edi_string: str):
    # This test is fine as is for the ISA/IEA check
    incomplete_edi = "ISA*00* *00* *ZZ*SENDER*ZZ*RECEIVER*240715*1200*^*00501*1*0*P*>~"
    parser_no_iea = EdiParser(edi_string=incomplete_edi, schema=standalone_schema)
    interchange_no_iea = parser_no_iea.parse()
    assert len(interchange_no_iea.errors) > 0
    assert "ISA/IEA envelope not found" in interchange_no_iea.errors[0].message

    # Use the valid fixture to test for a missing SE
    edi_missing_se = valid_837p_edi_string.replace("SE*25*0001~", "")
    parser_no_se = EdiParser(edi_string=edi_missing_se, schema=standalone_schema)
    interchange_no_se = parser_no_se.parse()
    assert len(interchange_no_se.errors) > 0
    assert "Unclosed transaction set" in interchange_no_se.errors[0].message

# --- THIS IS THE REFACTORED AND FIXED TEST ---
def test_parser_handles_missing_mandatory_segment(standalone_schema: ImplementationGuideSchema, valid_837p_edi_string: str):
    """
    Tests that the parser correctly flags an error when a mandatory segment (LX)
    that starts a required loop (2400) is missing.
    """
    # 1. Start with a compliant EDI string
    # 2. Remove the mandatory LX segment that begins the 2400 loop
    edi_missing_lx = valid_837p_edi_string.replace("LX*1~\n", "")
    # 3. Decrement the SE segment count to avoid a control number mismatch error
    edi_missing_lx = edi_missing_lx.replace("SE*25*0001~", "SE*24*0001~")
    
    parser = EdiParser(edi_string=edi_missing_lx, schema=standalone_schema)
    interchange = parser.parse()
    
    # 4. Find the claim loop where the error should have been logged
    claim_loop = interchange.functional_groups[0].transactions[0].body.get_loop("2000A").get_loop("2000B").get_loop("2300")
    
    # 5. Assert that the specific, expected error was logged
    assert claim_loop is not None
    assert len(claim_loop.errors) > 0

    # The new assertion checks for the correct error message.
    expected_error_msg = "Required segment or loop '2400' (SERVICE LINE) is missing from loop '2300'."
    assert any(expected_error_msg in e.message for e in claim_loop.errors)