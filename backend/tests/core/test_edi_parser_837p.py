# FILE: backend/tests/core/test_edi_parser_837p.py
import pytest
from src.core.edi_parser import EdiParser
from src.edi_schemas.edi_guide import ImplementationGuideSchema

pytestmark = pytest.mark.unit

# A fully compliant 837P string that satisfies all schema requirements
VALID_837P_EDI = """
ISA*00*          *00*          *ZZ*SENDERID       *ZZ*RECEIVERID     *240715*1200*^*00501*000000001*0*P*>~
GS*HC*SENDER*RECEIVER*20240715*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
BHT*0019*00*1234*20240715*1200*CH~
NM1*41*2*PREMIER BILLING*****46*SUBMITTER1~
PER*IC*JOHN DOE*TE*8005551212~
NM1*40*2*PAYER A*****46*RECEIVER1~
HL*1**20*1~
NM1*85*2*BILLING PROVIDER*****XX*1234567890~
N3*123 MAIN ST~
N4*ANYTOWN*CA*90210~
REF*EI*123456789~
HL*2*1*22*0~
SBR*P*18*GRP123******CI~
NM1*IL*1*DOE*JOHN****MI*SUBID123~
NM1*PR*2*PAYER A*****PI*PAYERID123~
CLM*PATCTRL123*500***11>B>1*Y*A*Y*Y~
HI*BK>87340~
LX*1~
SV1*HC>99213*125*UN*1***1**Y~
SE*22*0001~
GE*1*1~
IEA*1*000000001~
""".strip()

def test_compliant_837p_is_parsed_without_errors(standalone_schema: ImplementationGuideSchema):
    """
    Tests that a compliant EDI file is parsed with no structural or content validation errors.
    """
    parser = EdiParser(edi_string=VALID_837P_EDI, schema=standalone_schema)
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

def test_validator_finds_missing_required_loop(standalone_schema: ImplementationGuideSchema):
    """
    Tests that the parser correctly identifies a missing required loop (e.g., 1000A Submitter).
    """
    invalid_edi = VALID_837P_EDI.replace("NM1*41*2*PREMIER BILLING*****46*SUBMITTER1~\n", "")
    parser = EdiParser(edi_string=invalid_edi, schema=standalone_schema)
    interchange = parser.parse()

    transaction = interchange.functional_groups[0].transactions[0]
    transaction_body = transaction.body
    
    assert len(transaction_body.errors) > 0
    assert "Required segment or loop '1000A' not found" in transaction_body.errors[0].message

def test_validator_finds_invalid_code_value(standalone_schema: ImplementationGuideSchema):
    """
    Tests that the validator correctly identifies an element with a value not in its defined code set.
    """
    # --- THIS IS THE FIX ---
    # Be very specific about the replacement to ensure only SV110 is changed.
    valid_sv1 = "SV1*HC>99213*125*UN*1***1**Y~"
    invalid_sv1 = "SV1*HC>99213*125*UN*1***1**X~" # Note the X in the SV110 position
    invalid_edi = VALID_837P_EDI.replace(valid_sv1, invalid_sv1)
    
    parser = EdiParser(edi_string=invalid_edi, schema=standalone_schema)
    interchange = parser.parse()

    service_line_loop = interchange.functional_groups[0].transactions[0].body.get_loop('2000A').get_loop('2000B').get_loop('2300').get_loop('2400')
    sv1_segment = service_line_loop.get_segment('SV1')

    assert len(sv1_segment.errors) > 0
    error_messages = [e.message for e in sv1_segment.errors]
    assert any("Element 'SV109'" in msg and "Invalid code value" in msg for msg in error_messages)