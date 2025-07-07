import pytest
import json
from pathlib import Path

from src.core.edi_parser import EdiParser
from src.edi_schemas.edi_guide import ImplementationGuideSchema

SIMPLE_837P_EDI = """ISA*00*          *00*          *ZZ*SENDERID       *ZZ*RECEIVERID     *240715*1200*^*00501*000000001*0*P*>~
GS*HC*SENDER*RECEIVER*20240715*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
BHT*0019*00*1234*20240715*1200*CH~
HL*1**20*1~
NM1*85*2*BILLING PROVIDER*****XX*1234567890~
HL*2*1*22*0~
SBR*P*18*GRP123~
NM1*IL*1*DOE*JOHN****MI*SUBID123~
CLM*PATCTRL123*500***11:B:1*Y*A*Y*Y~
SV1*HC:V2020:G4*125*UN*1~
SE*10*0001~
GE*1*1~
IEA*1*000000001~
""".strip()

@pytest.fixture
def x222a1_schema() -> ImplementationGuideSchema:
    schema_path = Path(__file__).parent.parent.parent / "src/edi_schemas/837.5010.X222.A1.json"
    with open(schema_path, 'r') as f:
        return ImplementationGuideSchema.model_validate(json.load(f))

def test_parser_creates_valid_cdm_transaction(x222a1_schema: ImplementationGuideSchema):
    parser = EdiParser(edi_string=SIMPLE_837P_EDI, schema=x222a1_schema)
    cdm = parser.parse()
    assert cdm is not None
    assert cdm.header.segment_id == 'ST'
    assert cdm.trailer.segment_id == 'SE'
    assert cdm.body.loop_id == "ST_LOOP"

def test_parser_identifies_loops_correctly(x222a1_schema: ImplementationGuideSchema):
    parser = EdiParser(edi_string=SIMPLE_837P_EDI, schema=x222a1_schema)
    cdm = parser.parse()
    
    st_loop = cdm.body
    
    header_loop = st_loop.loops['HEADER'][0]
    assert any(s.segment_id == 'BHT' for s in header_loop.segments)

    detail_loop = st_loop.loops['DETAIL'][0]
    
    loop_2000a = detail_loop.loops['2000A'][0]
    assert loop_2000a.loop_id == '2000A'
    
    loop_2000b = loop_2000a.loops['2000B'][0]
    assert loop_2000b.loop_id == '2000B'
    
    loop_2300 = loop_2000b.loops['2300'][0]
    assert loop_2300.loop_id == '2300'
    
    loop_2400 = loop_2300.loops['2400'][0]
    assert loop_2400.loop_id == '2400'
    assert any(s.segment_id == 'SV1' for s in loop_2400.segments)

def test_parser_handles_incomplete_edi_gracefully(x222a1_schema: ImplementationGuideSchema):
    incomplete_edi = "ISA*00* *00* *ZZ*SENDER*ZZ*RECEIVER*240715*1200*^*00501*1*0*P*>~"
    with pytest.raises(ValueError, match="ST segment not found."):
        EdiParser(edi_string=incomplete_edi, schema=x222a1_schema).parse()
        
    edi_missing_se = SIMPLE_837P_EDI.replace("SE*10*0001~", "")
    with pytest.raises(ValueError, match="SE segment not found at end of transaction."):
        EdiParser(edi_string=edi_missing_se, schema=x222a1_schema).parse()