# FILE: backend/tests/core/test_edi_parser.py
import pytest
from src.core.edi_parser import EdiParser
from src.edi_schemas.edi_guide import ImplementationGuideSchema

pytestmark = pytest.mark.unit

SIMPLE_837P_EDI = """
ISA*00*          *00*          *ZZ*SENDERID       *ZZ*RECEIVERID     *240715*1200*^*00501*000000001*0*P*>~
GS*HC*SENDER*RECEIVER*20240715*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
BHT*0019*00*1234*20240715*1200*CH~
HL*1**20*1~
NM1*85*2*BILLING PROVIDER*****XX*1234567890~
HL*2*1*22*0~
SBR*P*18*GRP123~
NM1*IL*1*DOE*JOHN****MI*SUBID123~
CLM*PATCTRL123*500***11:B:1*Y*A*Y*Y~
LX*1~
SV1*HC:V2020:G4*125*UN*1~
SE*11*0001~
GE*1*1~
IEA*1*000000001~
""".strip()

def test_parser_creates_valid_cdm_interchange(standalone_schema: ImplementationGuideSchema):
    parser = EdiParser(edi_string=SIMPLE_837P_EDI, schema=standalone_schema)
    interchange = parser.parse()
    assert interchange is not None
    assert interchange.header.segment_id == 'ISA'
    assert len(interchange.errors) == 0

def test_parser_identifies_loops_correctly(standalone_schema: ImplementationGuideSchema):
    parser = EdiParser(edi_string=SIMPLE_837P_EDI, schema=standalone_schema)
    interchange = parser.parse()
    
    transaction = interchange.functional_groups[0].transactions[0]
    st_loop = transaction.body
    
    loop_2000a = st_loop.loops['2000A'][0]
    assert loop_2000a.loop_id == '2000A'
    
    # In the simple EDI, the claim is directly under the subscriber (2000B)
    loop_2000b = loop_2000a.loops['2000B'][0]
    assert loop_2000b.loop_id == '2000B'
    
    loop_2300 = loop_2000b.loops['2300'][0]
    assert loop_2300.loop_id == '2300'
    
    loop_2400 = loop_2300.loops['2400'][0]
    assert loop_2400.loop_id == '2400'
    assert any(s.segment_id == 'SV1' for s in loop_2400.segments)

def test_parser_handles_incomplete_edi_gracefully(standalone_schema: ImplementationGuideSchema):
    # --- FIX: Let the parser run and check the results naturally ---
    incomplete_edi = "ISA*00* *00* *ZZ*SENDER*ZZ*RECEIVER*240715*1200*^*00501*1*0*P*>~"
    parser_no_iea = EdiParser(edi_string=incomplete_edi, schema=standalone_schema)
    interchange_no_iea = parser_no_iea.parse()
    assert len(interchange_no_iea.errors) > 0
    assert "ISA/IEA envelope not found" in interchange_no_iea.errors[0].message
    
    edi_missing_se = SIMPLE_837P_EDI.replace("SE*11*0001~", "")
    parser_no_se = EdiParser(edi_string=edi_missing_se, schema=standalone_schema)
    interchange_no_se = parser_no_se.parse()
    assert len(interchange_no_se.errors) > 0
    assert "Unclosed transaction set" in interchange_no_se.errors[0].message

def test_parser_handles_missing_mandatory_segment(standalone_schema: ImplementationGuideSchema):
    edi_missing_lx = SIMPLE_837P_EDI.replace("LX*1~\n", "")
    parser = EdiParser(edi_string=edi_missing_lx, schema=standalone_schema)
    interchange = parser.parse()
    
    transaction = interchange.functional_groups[0].transactions[0]
    assert len(transaction.errors) == 1
    expected_error_msg = "Transaction parsing incomplete. Unexpected structure or missing mandatory segment at or before 'SV1' (line 11)."
    assert transaction.errors[0].message == expected_error_msg