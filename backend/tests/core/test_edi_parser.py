import pytest
import json
from pathlib import Path

from src.core.edi_parser import EdiParser
from src.edi_schemas.edi_guide import ImplementationGuideSchema

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
SV1*HC:V2020:G4*125*UN*1~
SE*10*0001~
GE*1*1~
IEA*1*000000001~
""".strip()

@pytest.fixture
def x222a1_schema() -> ImplementationGuideSchema:
    """Loads the test schema from the actual file."""
    schema_path = Path(__file__).parent.parent.parent / "src/edi_schemas/837.5010.X222.A1.json"
    with open(schema_path, 'r') as f:
        return ImplementationGuideSchema.model_validate(json.load(f))

def test_parser_creates_valid_cdm_transaction(x222a1_schema: ImplementationGuideSchema):
    """Tests if the parser can successfully create a CDM from a valid EDI string."""
    parser = EdiParser(edi_string=SIMPLE_837P_EDI, schema=x222a1_schema)
    cdm = parser.parse()

    assert cdm is not None
    assert cdm.header.segment_id == 'ST'
    assert cdm.header.elements[0].value == '837'
    assert cdm.trailer.segment_id == 'SE'
    assert cdm.trailer.elements[0].value == '10'

def test_parser_identifies_loops_correctly(x222a1_schema: ImplementationGuideSchema):
    """Tests the hierarchical structure of the parsed CDM."""
    parser = EdiParser(edi_string=SIMPLE_837P_EDI, schema=x222a1_schema)
    cdm = parser.parse()
    
    transaction_body = cdm.body
    
    assert '1000A' in transaction_body.loops
    loop_1000a = transaction_body.loops['1000A'][0]
    assert loop_1000a.segments[0].segment_id == 'NM1'

    assert '2000A' in transaction_body.loops
    loop_2000a = transaction_body.loops['2000A'][0]
    assert loop_2000a.segments[0].segment_id == 'HL'
    
    assert '2000B' in loop_2000a.loops
    loop_2000b = loop_2000a.loops['2000B'][0]
    assert loop_2000b.segments[0].segment_id == 'HL'
    
    assert '2300' in loop_2000b.loops
    loop_2300 = loop_2000b.loops['2300'][0]
    assert loop_2300.segments[0].segment_id == 'CLM'
    
    assert '2400' in loop_2300.loops
    loop_2400 = loop_2300.loops['2400'][0]
    assert loop_2400.segments[0].segment_id == 'LX'
    assert loop_2400.segments[1].segment_id == 'SV1'

def test_parser_handles_incomplete_edi_gracefully(x222a1_schema: ImplementationGuideSchema):
    """Ensures the parser raises an error for truncated files."""
    incomplete_edi = "ISA*00* *00* *ZZ*SENDER*ZZ*RECEIVER*240715*1200*^*00501*1*0*P*>~GS*HC*S*R*20240715*1200*1*X*005010X222A1~"
    parser = EdiParser(edi_string=incomplete_edi, schema=x222a1_schema)
    
    # --- THIS IS THE FIX ---
    # Update the expected error message to match the new parser's error.
    with pytest.raises(ValueError, match="ST segment not found or out of order."):
        parser.parse()
        
    edi_missing_se = SIMPLE_837P_EDI.replace("SE*10*0001~", "")
    parser_missing_se = EdiParser(edi_string=edi_missing_se, schema=x222a1_schema)
    with pytest.raises(ValueError, match="SE segment not found at expected position."):
        parser_missing_se.parse()