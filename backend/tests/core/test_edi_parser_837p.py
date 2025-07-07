import pytest
import json
from pathlib import Path

from src.core.edi_parser import EdiParser
from src.edi_schemas.edi_guide import ImplementationGuideSchema

# This string is valid as a single transaction
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

# A valid EDI file containing two transaction sets (ST/SE)
MULTI_TRANSACTION_837P_EDI = """ISA*00*          *00*          *ZZ*1234567        *ZZ*11111          *170508*1141*^*00501*000000101*1*P*:~
GS*HC*XXXXXXX*XXXXX*20170617*1741*101*X*005010X222A1~
ST*837*1239*005010X222A1~
BHT*0019*00*010*20170617*1741*CH~
NM1*41*2*SUBMITTER*****46*ABC123~
PER*IC*SUBMITTER CONTACT*TE*8005551212~
HL*1**20*1~
NM1*85*2*BILLING PROVIDER*****XX*1122334455~
N3*123 PROVIDER ST~
N4*PROVCITY*PV*12345~
REF*EI*PROVTAXID~
CLM*1000A*140***19:B:1*Y*A*Y*Y~
HI*ABK:I10~
LX*1~
SV1*HC:99213*140*UN*1***1~
DTP*472*D8*20151124~
SE*13*1239~
ST*837*1240*005010X222A1~
BHT*0019*00*011*20170617*1741*CH~
NM1*41*2*SUBMITTER*****46*ABC123~
PER*IC*SUBMITTER CONTACT*TE*8005551213~
HL*1**20*1~
NM1*85*2*BILLING PROVIDER*****XX*1122334455~
N3*456 PROVIDER AVE~
N4*OTHERCITY*PV*67890~
REF*EI*PROVTAXID2~
CLM*1000B*250***11:B:1*Y*A*Y*Y~
HI*ABK:I10~
LX*1~
SV1*HC:99214*250*UN*1***1~
DTP*472*D8*20151125~
SE*13*1240~
GE*2*101~
IEA*1*000000101~
""".strip()


@pytest.fixture
def x222a1_schema() -> ImplementationGuideSchema:
    schema_path = Path(__file__).parent.parent.parent / "src/edi_schemas/837.5010.X222.A1.json"
    with open(schema_path, 'r') as f:
        return ImplementationGuideSchema.model_validate(json.load(f))

def test_simple_837p_is_parsed_without_errors(x222a1_schema: ImplementationGuideSchema):
    """A structurally correct file should parse with no errors at any level."""
    parser = EdiParser(edi_string=SIMPLE_837P_EDI, schema=x222a1_schema)
    interchange = parser.parse()
    
    assert interchange is not None
    assert len(interchange.errors) == 0
    assert len(interchange.functional_groups) == 1
    assert len(interchange.functional_groups[0].transactions) == 1
    assert len(interchange.functional_groups[0].transactions[0].errors) == 0

def test_invalid_edi_structure_causes_transaction_error(x222a1_schema: ImplementationGuideSchema):
    """
    Tests that a file with a missing mandatory segment can still be parsed, but the
    error is correctly placed on the transaction object.
    """
    invalid_edi = SIMPLE_837P_EDI.replace("LX*1~\n", "") # Remove mandatory LX
    parser = EdiParser(edi_string=invalid_edi, schema=x222a1_schema)
    interchange = parser.parse()

    assert interchange is not None
    assert len(interchange.errors) == 0 # No file-level errors
    
    transaction = interchange.functional_groups[0].transactions[0]
    assert len(transaction.errors) == 1
    # Updated assertion for the new error message
    expected_error_msg = "Transaction parsing incomplete. Unexpected structure or missing mandatory segment at or before 'SV1' (line 11). Processed 7 segments, but expected to process 8 segments in the transaction body."
    assert transaction.errors[0].message == expected_error_msg

def test_multi_transaction_837p_is_parsed_correctly(x222a1_schema: ImplementationGuideSchema):
    """
    This is the key test. It ensures the parser can handle a file with multiple
    ST/SE blocks inside a single GS/GE group without generating any errors.
    """
    parser = EdiParser(edi_string=MULTI_TRANSACTION_837P_EDI, schema=x222a1_schema)
    interchange = parser.parse()

    assert interchange is not None
    assert len(interchange.errors) == 0

    assert len(interchange.functional_groups) == 1
    group = interchange.functional_groups[0]

    assert len(group.transactions) == 2

    tx1 = group.transactions[0]
    tx2 = group.transactions[1]
    assert tx1.header.elements[1].value == '1239'
    assert tx2.header.elements[1].value == '1240'
    assert len(tx1.errors) == 0 # First transaction should have no errors
    assert len(tx2.errors) == 0 # Second transaction should have no errors