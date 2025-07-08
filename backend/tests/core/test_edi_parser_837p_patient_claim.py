import pytest
import json
from pathlib import Path

from src.core.edi_parser import EdiParser
from src.edi_schemas.edi_guide import ImplementationGuideSchema

pytestmark = pytest.mark.unit

@pytest.fixture
def x222a1_schema() -> ImplementationGuideSchema:
    """Loads the 837P schema for the parser."""
    schema_path = Path(__file__).parent.parent.parent / "src/edi_schemas/837.5010.X222.A1.json"
    with open(schema_path, 'r') as f:
        return ImplementationGuideSchema.model_validate(json.load(f))

# This 837P EDI file represents a common scenario where the patient is not the subscriber.
# The claim information (CLM loop 2300) is located under the patient loop (2000C),
# which is itself a child of the subscriber loop (2000B).
PATIENT_CLAIM_837P_EDI = """
ISA*00*          *00*          *ZZ*TGJ23          *ZZ*66783JJT       *061015*1023*^*00501*000000021*0*P*:~
GS*HC*PREMIER BILLING SERVICE*KEY INSURANCE COMPANY*20061015*1023*21*X*005010X222A1~
ST*837*0021*005010X222A1~
BHT*0019*00*244579*20061015*1023*CH~
NM1*41*2*PREMIER BILLING SERVICE*****46*TGJ23~
PER*IC*JERRY*TE*3055552222*EX*231~
NM1*40*2*KEY INSURANCE COMPANY*****46*66783JJT~
HL*1**20*1~
NM1*85*2*Ben Kildare Service*****XX*9876543210~
N3*234 SEAWAY ST~
N4*MIAMI*FL*33111~
REF*EI*587654321~
HL*2*1*22*1~
SBR*P**2222-SJ******CI~
NM1*IL*1*Smith*Jane****MI*JS00111223333~
N4*MAIMI*FL*33111~
DMG*D8*19430501*F~
NM1*PR*2*KEY INSURANCE COMPANY*****PI*999996666~
REF*G2*KA6663~
HL*3*2*23*0~
PAT*19~
NM1*QC*1*Smith*Ted~
N3*236 N MAIN ST~
N4*MIAMI*FL*33413~
DMG*D8*19730501*M~
CLM*26463774*100***11:B:1*Y*A*Y*I~
REF*D9*17312345600006351~
HI*ABK:J020*ABF:Z1159~
LX*1~
SV1*HC:99213*40*UN*1***1~
DTP*472*D8*20061003~
LX*2~
SV1*HC:87070*15*UN*1***1~
DTP*472*D8*20061003~
LX*3~
SV1*HC:99214*35*UN*1***2~
DTP*472*D8*20061010~
SE*34*0021~
GE*1*21~
IEA*1*000000021~
""".strip()


def test_parser_handles_patient_claim_837p_without_errors(x222a1_schema: ImplementationGuideSchema):
    """
    Tests that a standard 837P with a patient-level claim is parsed completely
    without generating any structural errors.
    """
    parser = EdiParser(edi_string=PATIENT_CLAIM_837P_EDI, schema=x222a1_schema)
    interchange = parser.parse()

    assert interchange is not None
    assert len(interchange.errors) == 0
    assert len(interchange.functional_groups) == 1
    
    group = interchange.functional_groups[0]
    assert len(group.errors) == 0
    assert len(group.transactions) == 1
    
    transaction = group.transactions[0]
    assert len(transaction.errors) == 0

def test_parser_extracts_patient_level_claim_data(x222a1_schema: ImplementationGuideSchema):
    """
    Verifies that claim data (2300 loop) is correctly located and parsed
    within the patient loop (2000C).
    """
    parser = EdiParser(edi_string=PATIENT_CLAIM_837P_EDI, schema=x222a1_schema)
    interchange = parser.parse()
    
    # Navigate down the hierarchy to the patient loop (2000C)
    patient_loop = interchange.functional_groups[0].transactions[0].body.loops['DETAIL'][0].loops['2000A'][0].loops['2000B'][0].loops['2000C'][0]
    
    assert patient_loop.loop_id == '2000C'
    
    # FIX: The NM1 segment is inside the 2010CA loop, which is a child of 2000C.
    patient_name_loop = patient_loop.loops['2010CA'][0]
    nm1_patient = next(s for s in patient_name_loop.segments if s.segment_id == 'NM1')
    assert nm1_patient.elements[2].value == 'Smith'
    assert nm1_patient.elements[3].value == 'Ted'

    # Verify the claim loop (2300) exists within the patient loop
    assert '2300' in patient_loop.loops
    claim_loop = patient_loop.loops['2300'][0]
    clm_segment = next(s for s in claim_loop.segments if s.segment_id == 'CLM')
    
    assert clm_segment.elements[0].value == '26463774' # CLM01 - Patient Control Number
    assert clm_segment.elements[1].value == '100'      # CLM02 - Total Claim Charge

def test_parser_accesses_subscriber_data_in_patient_claim(x222a1_schema: ImplementationGuideSchema):
    """
    Tests that subscriber information is still correctly accessible even when
    the claim is at the patient level.
    """
    parser = EdiParser(edi_string=PATIENT_CLAIM_837P_EDI, schema=x222a1_schema)
    interchange = parser.parse()
    
    # Navigate to the Subscriber loop (2000B)
    subscriber_loop = interchange.functional_groups[0].transactions[0].body.loops['DETAIL'][0].loops['2000A'][0].loops['2000B'][0]

    assert subscriber_loop.loop_id == '2000B'

    # FIX: The NM1 segment is inside the 2010BA loop, which is a child of 2000B.
    subscriber_name_loop = subscriber_loop.loops['2010BA'][0]
    nm1_subscriber = next(s for s in subscriber_name_loop.segments if s.segment_id == 'NM1')
    assert nm1_subscriber.elements[2].value == 'Smith'
    assert nm1_subscriber.elements[3].value == 'Jane'
    assert nm1_subscriber.elements[8].value == 'JS00111223333' # Subscriber ID

def test_parser_handles_repeating_service_lines_in_patient_claim(x222a1_schema: ImplementationGuideSchema):
    """
    Verifies that repeating service lines (2400 loop) are correctly parsed
    within a patient-level claim structure.
    """
    parser = EdiParser(edi_string=PATIENT_CLAIM_837P_EDI, schema=x222a1_schema)
    interchange = parser.parse()
    
    # Navigate down to the claim loop (2300)
    claim_loop = interchange.functional_groups[0].transactions[0].body.loops['DETAIL'][0].loops['2000A'][0].loops['2000B'][0].loops['2000C'][0].loops['2300'][0]
    
    assert '2400' in claim_loop.loops
    service_lines = claim_loop.loops['2400']
    
    assert len(service_lines) == 3
    
    # Check data from the first service line
    sv1_line1 = next(s for s in service_lines[0].segments if s.segment_id == 'SV1')
    assert sv1_line1.elements[0].value == 'HC:99213'
    assert sv1_line1.elements[1].value == '40'
    
    # Check data from the third service line
    sv1_line3 = next(s for s in service_lines[2].segments if s.segment_id == 'SV1')
    assert sv1_line3.elements[0].value == 'HC:99214'
    assert sv1_line3.elements[1].value == '35'