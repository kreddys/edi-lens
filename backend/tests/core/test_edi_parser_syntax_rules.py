# FILE: backend/tests/core/test_edi_parser_syntax_rules.py
import pytest
from src.core.edi_parser import EdiParser
from src.edi_schemas.edi_guide import ImplementationGuideSchema

pytestmark = pytest.mark.unit

def test_syntax_rule_conditional_length_fail(standalone_schema: ImplementationGuideSchema, valid_837p_edi_string: str):
    """
    Tests a conditional rule: IF DTP02 is 'D8', THEN DTP03 must have length 8.
    This test mutates a valid DTP to make it invalid.
    """
    # Mutate the valid DTP to have an invalid date length
    invalid_edi = valid_837p_edi_string.replace(
        "DTP*431*D8*20240715~",
        "DTP*431*D8*202407~"
    )
    # Adjust segment count in SE
    invalid_edi = invalid_edi.replace("SE*24*0001~", "SE*24*0001~") # Count remains the same
    
    parser = EdiParser(edi_string=invalid_edi, schema=standalone_schema)
    interchange = parser.parse()

    claim_loop = interchange.functional_groups[0].transactions[0].body.get_loop("2000A").get_loop("2000B").get_loop("2300")
    dtp_segment = claim_loop.get_segment("DTP")
    
    assert dtp_segment is not None
    assert len(dtp_segment.errors) > 0
    error_messages = [e.message for e in dtp_segment.errors]
    assert any("Syntax Rule Failed (DTP_D8_FormatCheck)" in msg for msg in error_messages)

def test_syntax_rule_paired_elements_fail(standalone_schema: ImplementationGuideSchema, valid_837p_edi_string: str):
    """
    Tests a paired element rule: IF PWK05 is present, THEN PWK06 must be present.
    This test mutates a valid PWK to make it invalid.
    """
    # Mutate the valid PWK to remove PWK06
    invalid_edi = valid_837p_edi_string.replace(
        "PWK*OZ*BM***AC*CONTROL123~",
        "PWK*OZ*BM***AC~"
    )
    
    parser = EdiParser(edi_string=invalid_edi, schema=standalone_schema)
    interchange = parser.parse()

    claim_loop = interchange.functional_groups[0].transactions[0].body.get_loop("2000A").get_loop("2000B").get_loop("2300")
    pwk_segment = claim_loop.get_segment("PWK")
    
    assert pwk_segment is not None
    assert len(pwk_segment.errors) > 0
    error_messages = [e.message for e in pwk_segment.errors]
    assert any("Syntax Rule Failed (PWK_Paired_PWK05_PWK06)" in msg for msg in error_messages)

def test_syntax_rule_at_least_one_of_fail(standalone_schema: ImplementationGuideSchema, valid_837p_edi_string: str):
    """
    Tests a group rule: At least one of FRM02-FRM05 must be present.
    Injects a valid 2440 loop structure with an invalid FRM segment.
    """
    # --- THIS IS THE FIX ---
    # We find the SV1 segment and inject the 2440 loop (LQ and FRM) right after it.
    # This is a valid structural position according to the schema.
    injection_point = "SV1*HC>99213*125*UN*1***1**Y~"
    invalid_structure = injection_point + "\nDTP*472*D8*20240715~\nLQ*UT*ABC~\nFRM*1~" # Valid LQ, Invalid FRM
    
    invalid_edi = valid_837p_edi_string.replace(injection_point, invalid_structure)
    
    # Adjust segment count in SE (we added 3 segments)
    invalid_edi = invalid_edi.replace("SE*25*0001~", "SE*28*0001~")
    
    parser = EdiParser(edi_string=invalid_edi, schema=standalone_schema)
    interchange = parser.parse()
    
    service_line_loop = interchange.functional_groups[0].transactions[0].body.get_loop("2000A").get_loop("2000B").get_loop("2300").get_loop("2400")
    form_loop = service_line_loop.get_loop("2440")
    assert form_loop is not None, "Parser did not create the 2440 loop for the FRM segment."
    
    frm_segment = form_loop.get_segment("FRM")
    assert frm_segment is not None
    
    assert len(frm_segment.errors) > 0
    error_messages = [e.message for e in frm_segment.errors]
    assert any("Syntax Rule Failed (FRM_Required_Response)" in msg for msg in error_messages)