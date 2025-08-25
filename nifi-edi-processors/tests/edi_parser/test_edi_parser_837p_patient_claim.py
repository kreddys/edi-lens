# FILE: backend/tests/core/test_edi_parser_837p_patient_claim.py
import pytest
from edi_parser import EdiParser
from edi_schema_models import ImplementationGuideSchema

pytestmark = pytest.mark.unit

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

def test_parser_handles_patient_claim_837p_without_errors(standalone_schema: ImplementationGuideSchema):
    parser = EdiParser(edi_string=PATIENT_CLAIM_837P_EDI, schema=standalone_schema)
    interchange = parser.parse()
    assert interchange is not None
    assert len(interchange.errors) == 0, f"Parser found errors: {[e.message for e in interchange.errors]}"

def test_parser_extracts_patient_level_claim_data(standalone_schema: ImplementationGuideSchema):
    parser = EdiParser(edi_string=PATIENT_CLAIM_837P_EDI, schema=standalone_schema)
    interchange = parser.parse()

    subscriber_loop = interchange.functional_groups[0].transactions[0].body.get_loop("2000A").get_loop("2000B")

    # Patient (2000C) is a child of the subscriber (2000B)
    patient_loop = subscriber_loop.get_loop('2000C')
    assert patient_loop is not None and patient_loop.loop_id == '2000C'

    patient_name_loop = patient_loop.get_loop('2010CA')
    nm1_patient = patient_name_loop.get_segment('NM1')
    assert nm1_patient.elements[2].value == 'Smith'

    # The claim (2300) is a SIBLING of the patient (2000C) under subscriber (2000B)
    claim_loop = subscriber_loop.get_loop('2300')
    assert claim_loop is not None
    clm_segment = claim_loop.get_segment('CLM')
    assert clm_segment.elements[0].value == '26463774'

def test_parser_accesses_subscriber_data_in_patient_claim(standalone_schema: ImplementationGuideSchema):
    parser = EdiParser(edi_string=PATIENT_CLAIM_837P_EDI, schema=standalone_schema)
    interchange = parser.parse()

    subscriber_loop = interchange.functional_groups[0].transactions[0].body.loops['2000A'][0].loops['2000B'][0]
    assert subscriber_loop.loop_id == '2000B'

    subscriber_name_loop = subscriber_loop.loops['2010BA'][0]
    nm1_subscriber = next(s for s in subscriber_name_loop.segments if s.segment_id == 'NM1')
    assert nm1_subscriber.elements[2].value == 'Smith'

def test_parser_handles_repeating_service_lines_in_patient_claim(standalone_schema: ImplementationGuideSchema):
    parser = EdiParser(edi_string=PATIENT_CLAIM_837P_EDI, schema=standalone_schema)
    interchange = parser.parse()

    # The claim (2300) is a sibling of the patient (2000C) under subscriber (2000B)
    subscriber_loop = interchange.functional_groups[0].transactions[0].body.get_loop("2000A").get_loop("2000B")
    claim_loop = subscriber_loop.get_loop('2300')

    assert '2400' in claim_loop.loops
    service_lines = claim_loop.loops['2400']

    assert len(service_lines) == 3
