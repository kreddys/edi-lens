import pytest
import json
from pathlib import Path

from src.core.edi_parser import EdiParser
# --- THIS IS THE FIX ---
from src.edi_schemas.edi_guide import ImplementationGuideSchema

# A simple but structurally correct EDI file for testing the new parser
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
"""

@pytest.fixture
def x222a1_schema() -> ImplementationGuideSchema:
    """Loads the test schema from the actual file."""
    # --- THIS IS THE FIX ---
    # Path logic is updated to reflect the test file's location relative to the src directory
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
    
    # The body is a virtual root loop
    assert '2000A' in cdm.body.loops
    assert len(cdm.body.loops['2000A']) == 1

    loop_2000a = cdm.body.loops['2000A'][0]
    assert loop_2000a.loop_id == '2000A'
    assert len(loop_2000a.segments) > 0 # Should have HL, NM1
    assert loop_2000a.segments[0].segment_id == 'HL'
    
    # Check for nested loop
    assert '2000B' in loop_2000a.loops
    assert len(loop_2000a.loops['2000B']) == 1

    loop_2000b = loop_2000a.loops['2000B'][0]
    assert loop_2000b.loop_id == '2000B'
    assert len(loop_2000b.segments) > 0 # Should have HL, SBR
    
    # Check for the claim loop
    assert '2300' in loop_2000b.loops
    loop_2300 = loop_2000b.loops['2300'][0]
    assert loop_2300.loop_id == '2300'
    assert any(seg.segment_id == 'CLM' for seg in loop_2300.segments)
    
    # Check for the service line loop
    assert '2400' in loop_2300.loops
    loop_2400 = loop_2300.loops['2400'][0]
    assert loop_2400.loop_id == '2400'
    assert any(seg.segment_id == 'SV1' for seg in loop_2400.segments)

def test_parser_handles_incomplete_edi_gracefully(x222a1_schema: ImplementationGuideSchema):
    """Ensures the parser raises an error for truncated files."""
    incomplete_edi = "ISA*00* *00* *ZZ*SENDER*ZZ*RECEIVER*240715*1200*^*00501*1*0*P*>~GS*HC*S*R*20240715*1200*1*X*005010X222A1~"
    parser = EdiParser(edi_string=incomplete_edi, schema=x222a1_schema)
    
    with pytest.raises(ValueError, match="incomplete or missing ST segment"):
        parser.parse()
        
    edi_missing_se = SIMPLE_837P_EDI.replace("SE*10*0001~", "")
    parser_missing_se = EdiParser(edi_string=edi_missing_se, schema=x222a1_schema)
    with pytest.raises(ValueError, match="SE segment not found"):
        parser_missing_se.parse()