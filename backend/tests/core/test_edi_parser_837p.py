# FILE: backend/tests/core/test_edi_parser_837p.py
import pytest
from src.core.edi_parser import EdiParser
from src.edi_schemas.edi_guide import ImplementationGuideSchema

pytestmark = pytest.mark.unit

# A more compliant 837P string for "happy path" testing
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
SBR*P*18*GRP123*******CI~
NM1*IL*1*DOE*JOHN****MI*SUBID123~
NM1*PR*2*PAYER A*****PI*PAYERID123~
CLM*PATCTRL123*500***11:B:1*Y*A*Y*Y~
HI*BK:87340~
LX*1~
SV1*HC:99213*125*UN*1***1~
SE*22*0001~
GE*1*1~
IEA*1*000000001~
""".strip()


MULTI_TRANSACTION_837P_EDI = """
ISA*00*          *00*          *ZZ*1234567        *ZZ*11111          *170508*1141*^*00501*000000101*1*P*:~
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
HL*2*1*22*0~
SBR*P*18*SUBSCRIBERID*GRP001********CI~
NM1*IL*1*SUBLAST*SUBFIRST****MI*SUBMEMID1~
CLM*1000A*140***19:B:1*Y*A*Y*Y~
HI*ABK:I10~
LX*1~
SV1*HC:99213*140*UN*1***1~
DTP*472*D8*20151124~
SE*16*1239~
ST*837*1240*005010X222A1~
BHT*0019*00*011*20170617*1741*CH~
NM1*41*2*SUBMITTER*****46*ABC123~
PER*IC*SUBMITTER CONTACT*TE*8005551213~
HL*1**20*1~
NM1*85*2*BILLING PROVIDER*****XX*1122334455~
N3*456 PROVIDER AVE~
N4*OTHERCITY*PV*67890~
REF*EI*PROVTAXID2~
HL*2*1*22*0~
SBR*P*18*SUBSCRIBERID2*GRP002********CI~
NM1*IL*1*SUBLAST2*SUBFIRST2****MI*SUBMEMID2~
CLM*1000B*250***11:B:1*Y*A*Y*Y~
HI*ABK:I10~
LX*1~
SV1*HC:99214*250*UN*1***1~
DTP*472*D8*20151125~
SE*16*1240~
GE*2*101~
IEA*1*000000101~
""".strip()

def test_compliant_837p_is_parsed_without_errors(standalone_schema: ImplementationGuideSchema):
    parser = EdiParser(edi_string=VALID_837P_EDI, schema=standalone_schema)
    interchange = parser.parse()
    
    transaction = interchange.functional_groups[0].transactions[0]
    all_errors = interchange.errors + transaction.errors
    
    for loop in [transaction.body] + list(transaction.body.loops.values()):
        if isinstance(loop, list): # Handle multiple loops of same type
             for l in loop:
                all_errors.extend(l.errors)
        else:
             all_errors.extend(loop.errors)

    assert len(all_errors) == 0, f"Parser found unexpected errors: {[e.message for e in all_errors]}"

def test_validator_finds_missing_required_loop(standalone_schema: ImplementationGuideSchema):
    invalid_edi = VALID_837P_EDI.replace("NM1*41*2*PREMIER BILLING*****46*SUBMITTER1~\n", "")
    parser = EdiParser(edi_string=invalid_edi, schema=standalone_schema)
    interchange = parser.parse()

    transaction = interchange.functional_groups[0].transactions[0]
    transaction_body = transaction.body
    
    assert len(transaction_body.errors) > 0
    assert "Required segment or loop '1000A' not found" in transaction_body.errors[0].message

def test_multi_transaction_837p_is_parsed_correctly(standalone_schema: ImplementationGuideSchema):
    parser = EdiParser(edi_string=MULTI_TRANSACTION_837P_EDI, schema=standalone_schema)
    interchange = parser.parse()

    assert interchange is not None and len(interchange.errors) == 0
    assert len(interchange.functional_groups[0].transactions) == 2