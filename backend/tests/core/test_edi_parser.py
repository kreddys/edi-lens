import pytest
import json
from pathlib import Path

from src.core.edi_parser import EdiParser
from src.edi_schemas.edi_guide import ImplementationGuideSchema

# The same valid EDI string, but now used to test the full hierarchy.
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
LX*1~
SV1*HC:V2020:G4*125*UN*1~
SE*11*0001~
GE*1*1~
IEA*1*000000001~
""".strip()

@pytest.fixture
def x222a1_schema() -> ImplementationGuideSchema:
    schema_path = Path(__file__).parent.parent.parent / "src/edi_schemas/837.5010.X222.A1.json"
    with open(schema_path, 'r') as f:
        return ImplementationGuideSchema.model_validate(json.load(f))

def test_parser_creates_valid_cdm_interchange(x222a1_schema: ImplementationGuideSchema):
    """Tests that a simple, valid EDI file is parsed into the full hierarchical model."""
    parser = EdiParser(edi_string=SIMPLE_837P_EDI, schema=x222a1_schema)
    interchange = parser.parse()
    
    assert interchange is not None
    assert interchange.header.segment_id == 'ISA'
    assert interchange.trailer.segment_id == 'IEA'
    assert len(interchange.errors) == 0

    assert len(interchange.functional_groups) == 1
    group = interchange.functional_groups[0]
    assert group.header.segment_id == 'GS'
    assert group.trailer.segment_id == 'GE'

    assert len(group.transactions) == 1
    transaction = group.transactions[0]
    assert transaction.header.segment_id == 'ST'
    assert transaction.trailer.segment_id == 'SE'
    assert transaction.body.loop_id == "ST_LOOP"

def test_parser_identifies_loops_correctly(x222a1_schema: ImplementationGuideSchema):
    """Tests that nested loops are still correctly identified within the new structure."""
    parser = EdiParser(edi_string=SIMPLE_837P_EDI, schema=x222a1_schema)
    interchange = parser.parse()
    
    transaction = interchange.functional_groups[0].transactions[0]
    st_loop = transaction.body
    
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
    """Tests that missing envelope segments are caught at the interchange level."""
    incomplete_edi = "ISA*00* *00* *ZZ*SENDER*ZZ*RECEIVER*240715*1200*^*00501*1*0*P*>~"
    parser = EdiParser(edi_string=incomplete_edi, schema=x222a1_schema)
    interchange = parser.parse()
    assert len(interchange.errors) == 1
    assert interchange.errors[0].message == "ISA/IEA envelope not found."

    edi_missing_se = SIMPLE_837P_EDI.replace("SE*11*0001~", "")
    parser = EdiParser(edi_string=edi_missing_se, schema=x222a1_schema)
    interchange = parser.parse()
    assert len(interchange.errors) == 1
    assert "Unclosed transaction set found" in interchange.errors[0].message

def test_parser_handles_missing_mandatory_segment(x222a1_schema: ImplementationGuideSchema):
    """Tests that a structural error within a transaction is caught and added to that transaction's error list."""
    edi_missing_lx = SIMPLE_837P_EDI.replace("LX*1~\n", "")
    parser = EdiParser(edi_string=edi_missing_lx, schema=x222a1_schema)
    interchange = parser.parse()
    
    # No interchange-level errors
    assert len(interchange.errors) == 0
    
    # The error should be on the specific transaction
    transaction = interchange.functional_groups[0].transactions[0]
    assert len(transaction.errors) == 1
    # Updated assertion for the new error message
    expected_error_msg = "Transaction parsing incomplete. Unexpected structure or missing mandatory segment at or before 'SV1' (line 11). Processed 7 segments, but expected to process 8 segments in the transaction body."
    assert transaction.errors[0].message == expected_error_msg