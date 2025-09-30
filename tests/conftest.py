# FILE: nifi-edi-processors/tests/conftest.py

import pytest
import json
import sys
import os
import logging
import uuid
import time
from pathlib import Path
from typing import Optional

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from edi_schema_models import ImplementationGuideSchema

# ==============================================================================
# PYTEST CONFIGURATION & HOOKS
# ==============================================================================

def pytest_configure(config):
    """Configure pytest settings and markers."""
    config.addinivalue_line("markers", "unit: Pure unit tests with no external dependencies.")
    config.addinivalue_line("markers", "integration: Tests requiring external services or complex setups.")
    config.addinivalue_line("markers", "format: Tests for specific output format validation.")

@pytest.fixture(scope="session", autouse=True)
def setup_test_environment(pytestconfig):
    """Set up test environment with logging configuration."""
    # Use pytest's log_cli_level if available, otherwise default to INFO
    log_level = pytestconfig.getoption("log_cli_level") or "INFO"
    logging.basicConfig(
        level=log_level.upper(),
        format="[%(asctime)s] [%(levelname)s] [%(name)s:%(lineno)d] - %(message)s",
        stream=sys.stdout,
        force=True,
    )
    if log_level.upper() != "DEBUG":
        logging.getLogger("httpx").setLevel(logging.WARNING)
    
    logging.info(f"Test logging configured with level: {log_level.upper()}")
    yield

# ==============================================================================
# TEST DATA UTILITIES
# ==============================================================================

def generate_unique_id(prefix: str = "test") -> str:
    """Generate a unique ID for tests using timestamp and random component."""
    timestamp = int(time.time() * 1000)  # milliseconds
    random_part = uuid.uuid4().hex[:8]
    return f"{prefix}-{timestamp}-{random_part}"

# ==============================================================================
# UNIT TEST FIXTURES (Completely isolated, no external dependencies)
# ==============================================================================

@pytest.fixture(scope="session")
def standalone_schema() -> Optional[ImplementationGuideSchema]:
    """
    A session-scoped fixture specifically for UNIT TESTS.
    It loads the 837p schema directly from its runtime file path,
    bypassing any complex setup. This ensures true isolation for parser tests.
    """
    try:
        # Try to find schema in the src directory structure
        project_root = Path(__file__).parent.parent
        schema_path = project_root / "src" / "schemas" / "837.5010.X222.A1.json"
        
        # If not found, try alternative locations
        if not schema_path.exists():
            schema_path = project_root / "schemas" / "837.5010.X222.A1.json"
            
        if not schema_path.exists():
            pytest.skip(f"Unit test schema file not found at: {schema_path}")
            return None  # This line won't be reached, but helps Pylance
        
        with open(schema_path, 'r') as f:
            schema_data = json.load(f)
            return ImplementationGuideSchema.model_validate(schema_data)
    except Exception as e:
        pytest.skip(f"Failed to load or parse the schema for unit tests: {e}")
        return None  # This line won't be reached, but helps Pylance

@pytest.fixture(scope="session")
def valid_837p_edi_string() -> str:
    """Provides a shared, compliant 837P EDI string for parser unit tests."""
    return """
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
DTP*431*D8*20240715~
PWK*OZ*BM***AC*CONTROL123~
HI*BK>87340~
LX*1~
SV1*HC>99213*125*UN*1***1**Y~
DTP*472*D8*20240715~
SE*25*0001~
GE*1*1~
IEA*1*000000001~
""".strip()

@pytest.fixture(scope="session")
def multiple_transaction_sets_837p_edi_string() -> str:
    """
    Provides an 837P EDI string with multiple transaction sets (ST-SE blocks) in a single functional group.
    This tests the parser's ability to handle multiple transaction sets within one GS-GE envelope,
    including scenarios where some transactions contain errors.

    Contains:
    - 1 Functional Group (GS-GE)
    - 2 Transaction Sets (ST-SE blocks)
    - Transaction Set 1: VALID - 1 Billing Provider with 1 Subscriber and 1 Claim
    - Transaction Set 2: INVALID - Missing required 1000A loop, invalid date length, invalid codes
      (1 Billing Provider with 1 Subscriber and 2 Claims but with validation errors)
    Total: 2 Transaction Sets (1 valid, 1 invalid), 2 Billing Providers, 2 Subscribers, 3 Claims
    """
    return """
ISA*00*          *00*          *ZZ*SENDERID       *ZZ*RECEIVERID     *240715*1200*^*00501*000000001*0*P*>~
GS*HC*SENDER*RECEIVER*20240715*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
BHT*0019*00*TXN001*20240715*1200*CH~
NM1*41*2*PREMIER BILLING*****46*SUBMITTER1~
PER*IC*JOHN DOE*TE*8005551212~
NM1*40*2*PAYER A*****46*RECEIVER1~
HL*1**20*1~
NM1*85*2*BILLING PROVIDER 1*****XX*1234567890~
N3*123 MAIN ST~
N4*ANYTOWN*CA*90210~
REF*EI*123456789~
HL*2*1*22*0~
SBR*P*18*GRP123******CI~
NM1*IL*1*SMITH*JANE****MI*SUBID001~
NM1*PR*2*PAYER A*****PI*PAYERID123~
CLM*TXN001_CLAIM1*300***11>B>1*Y*A*Y*Y~
DTP*431*D8*20240715~
HI*BK>Z872~
LX*1~
SV1*HC>99213*300*UN*1***1**Y~
DTP*472*D8*20240715~
SE*21*0001~
ST*837*0002*005010X222A1~
BHT*0019*00*TXN002*202407*1200*CH~
PER*IC*JOHN DOE*TE*8005551212~
NM1*40*2*PAYER B*****46*RECEIVER2~
HL*1**20*1~
NM1*85*2*BILLING PROVIDER 2*****XX*9876543210~
N3*456 OAK AVE~
N4*OTHERCITY*TX*75001~
REF*EI*987654321~
HL*2*1*22*0~
SBR*P*18*GRP456******ZZ~
NM1*IL*1*JOHNSON*MIKE****MI*SUBID002~
NM1*PR*2*PAYER B*****PI*PAYERID456~
CLM*TXN002_CLAIM1*450***11>B>1*Y*A*Y*Y~
DTP*431*D8*20240715~
HI*BK>INVALID_CODE~
LX*1~
SV1*HC>99214*200*UN*1***1**Y~
DTP*472*D8*20240715~
LX*2~
SV1*HC>99215*250*UN*1***2**Y~
DTP*472*D8*20240715~
CLM*TXN002_CLAIM2*175***11>B>1*Y*A*Y*Y~
DTP*431*D8*20240716~
HI*BK>G473~
LX*1~
SV1*HC>99203*175*UN*1***1**Y~
DTP*472*D8*20240716~
SE*26*0002~
GE*2*1~
IEA*1*000000001~
""".strip()

@pytest.fixture(scope="session")
def multiple_functional_groups_837p_edi_string() -> str:
    """
    Provides an 837P EDI string with multiple functional groups (GS-GE blocks) in a single interchange.
    This tests the parser's ability to handle multiple functional groups within one ISA-IEA envelope.

    Contains:
    - 1 Interchange (ISA-IEA)
    - 2 Functional Groups (GS-GE blocks)
    - Group 1: 1 Transaction Set with 1 Billing Provider, 1 Subscriber, 1 Claim
    - Group 2: 1 Transaction Set with 1 Billing Provider, 1 Subscriber, 2 Claims
    Total: 2 Functional Groups, 2 Transaction Sets, 2 Billing Providers, 2 Subscribers, 3 Claims
    """
    return """
ISA*00*          *00*          *ZZ*SENDERID       *ZZ*RECEIVERID     *240715*1200*^*00501*000000001*0*P*>~
GS*HC*SENDER1*RECEIVER1*20240715*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
BHT*0019*00*GRP1_TXN1*20240715*1200*CH~
NM1*41*2*PREMIER BILLING*****46*SUBMITTER1~
PER*IC*JOHN DOE*TE*8005551212~
NM1*40*2*PAYER A*****46*RECEIVER1~
HL*1**20*1~
NM1*85*2*CLINIC A*****XX*1111111111~
N3*100 FIRST ST~
N4*FIRSTCITY*CA*90001~
REF*EI*111111111~
HL*2*1*22*0~
SBR*P*18*GRP100******CI~
NM1*IL*1*WILLIAMS*SARAH****MI*SUB100~
NM1*PR*2*PAYER A*****PI*PAY100~
CLM*GRP1_CLAIM1*225***11>B>1*Y*A*Y*Y~
DTP*431*D8*20240715~
HI*BK>J449~
LX*1~
SV1*HC>99212*225*UN*1***1**Y~
DTP*472*D8*20240715~
SE*21*0001~
GE*1*1~
GS*HC*SENDER2*RECEIVER2*20240715*1300*2*X*005010X222A1~
ST*837*0001*005010X222A1~
BHT*0019*00*GRP2_TXN1*20240715*1300*CH~
NM1*41*2*ADVANCED BILLING*****46*SUBMITTER2~
PER*IC*JANE SMITH*TE*8005552222~
NM1*40*2*PAYER B*****46*RECEIVER2~
HL*1**20*1~
NM1*85*2*CLINIC B*****XX*2222222222~
N3*200 SECOND ST~
N4*SECONDCITY*NY*10001~
REF*EI*222222222~
HL*2*1*22*0~
SBR*P*18*GRP200******CI~
NM1*IL*1*BROWN*DAVID****MI*SUB200~
NM1*PR*2*PAYER B*****PI*PAY200~
CLM*GRP2_CLAIM1*350***11>B>1*Y*A*Y*Y~
DTP*431*D8*20240715~
HI*BK>K219~
LX*1~
SV1*HC>99213*150*UN*1***1**Y~
DTP*472*D8*20240715~
LX*2~
SV1*HC>99214*200*UN*1***2**Y~
DTP*472*D8*20240715~
CLM*GRP2_CLAIM2*125***11>B>1*Y*A*Y*Y~
DTP*431*D8*20240716~
HI*BK>L403~
LX*1~
SV1*HC>99211*125*UN*1***1**Y~
DTP*472*D8*20240716~
SE*27*0001~
GE*1*2~
IEA*2*000000001~
""".strip()

@pytest.fixture(scope="session")
def multiple_claims_per_subscriber_837p_edi_string() -> str:
    """
    Provides an 837P EDI string demonstrating multiple claims for a single subscriber.
    This tests the parser's ability to handle multiple 2300 claim loops under one subscriber.

    Contains:
    - 1 Billing Provider
    - 1 Subscriber with 4 different claims (different dates/diagnoses)
    - Each claim has different numbers of service lines
    Total: 1 Subscriber, 4 Claims, 7 Service Lines
    """
    return """
ISA*00*          *00*          *ZZ*SENDERID       *ZZ*RECEIVERID     *240715*1200*^*00501*000000001*0*P*>~
GS*HC*SENDER*RECEIVER*20240715*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
BHT*0019*00*MULTICLAIM*20240715*1200*CH~
NM1*41*2*MULTI CLAIM BILLING*****46*SUBMITTER1~
PER*IC*BILLING DEPT*TE*8005551212~
NM1*40*2*INSURANCE CO*****46*RECEIVER1~
HL*1**20*1~
NM1*85*2*FAMILY PRACTICE*****XX*5555555555~
N3*789 MEDICAL BLVD~
N4*HEALTHCITY*FL*33101~
REF*EI*555555555~
HL*2*1*22*0~
SBR*P*18*POLICY789******CI~
NM1*IL*1*ANDERSON*ROBERT****MI*PATIENT789~
NM1*PR*2*INSURANCE CO*****PI*INSURER789~
CLM*ANDERSON_VISIT1*275***11>B>1*Y*A*Y*Y~
DTP*431*D8*20240701~
HI*BK>J069~
LX*1~
SV1*HC>99213*275*UN*1***1**Y~
DTP*472*D8*20240701~
CLM*ANDERSON_VISIT2*420***11>B>1*Y*A*Y*Y~
DTP*431*D8*20240708~
HI*BK>J069~
LX*1~
SV1*HC>99214*200*UN*1***1**Y~
DTP*472*D8*20240708~
LX*2~
SV1*HC>93000*120*UN*1***2**Y~
DTP*472*D8*20240708~
LX*3~
SV1*HC>80053*100*UN*1***3**Y~
DTP*472*D8*20240708~
CLM*ANDERSON_VISIT3*325***11>B>1*Y*A*Y*Y~
DTP*431*D8*20240715~
HI*BK>Z00121~
LX*1~
SV1*HC>99215*225*UN*1***1**Y~
DTP*472*D8*20240715~
LX*2~
SV1*HC>90471*100*UN*1***2**Y~
DTP*472*D8*20240715~
CLM*ANDERSON_VISIT4*150***11>B>1*Y*A*Y*Y~
DTP*431*D8*20240722~
HI*BK>Z515~
LX*1~
SV1*HC>99212*150*UN*1***1**Y~
DTP*472*D8*20240722~
SE*44*0001~
GE*1*1~
IEA*1*000000001~
""".strip()


@pytest.fixture(scope="session")
def subscriber_vs_patient_837p_edi_string() -> str:
    """
    Provides an 837P EDI string demonstrating both subscriber-as-patient and dependent patient scenarios.
    This tests the parser's ability to handle HL03=22 (subscriber) vs HL03=23 (dependent patient) scenarios.

    Contains:
    - 1 Billing Provider
    - 2 Subscribers:
      - Subscriber 1: Self-insured (HL03=22, no dependent)
      - Subscriber 2: Has dependent patient (HL03=22 subscriber + HL03=23 dependent)
    Total: 2 Subscribers, 1 Dependent Patient, 3 Claims, 4 Service Lines
    """
    return """
ISA*00*          *00*          *ZZ*SENDERID       *ZZ*RECEIVERID     *240715*1200*^*00501*000000001*0*P*>~
GS*HC*SENDER*RECEIVER*20240715*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
BHT*0019*00*SUBVSPAT*20240715*1200*CH~
NM1*41*2*FAMILY BILLING SERVICE*****46*SUBMITTER1~
PER*IC*BILLING COORDINATOR*TE*8005551212~
NM1*40*2*FAMILY HEALTH PLAN*****46*RECEIVER1~
HL*1**20*1~
NM1*85*2*COMMUNITY HEALTH CENTER*****XX*4444444444~
N3*400 COMMUNITY DR~
N4*WELLNESS*OH*44101~
REF*EI*444444444~
HL*2*1*22*0~
SBR*P*18*SELF001******CI~
NM1*IL*1*SELFINSURED*JOHN****MI*SELF001~
NM1*PR*2*FAMILY HEALTH PLAN*****PI*FHP001~
CLM*SELF_CLAIM1*195***11>B>1*Y*A*Y*Y~
DTP*431*D8*20240715~
HI*BK>Z00000~
LX*1~
SV1*HC>99213*195*UN*1***1**Y~
DTP*472*D8*20240715~
HL*3*1*22*1~
SBR*P*18*FAMILY002******CI~
NM1*IL*1*SUBSCRIBER*MARY****MI*SUB002~
NM1*PR*2*FAMILY HEALTH PLAN*****PI*FHP002~
CLM*SUB_CLAIM1*275***11>B>1*Y*A*Y*Y~
DTP*431*D8*20240715~
HI*BK>Z00121~
LX*1~
SV1*HC>99214*275*UN*1***1**Y~
DTP*472*D8*20240715~
HL*4*3*23*0~
PAT*19~
NM1*QC*1*DEPENDENT*CHILD~
N3*400 COMMUNITY DR~
N4*WELLNESS*OH*44101~
DMG*D8*20100515*F~
CLM*DEP_CLAIM1*125***11>B>1*Y*A*Y*Y~
DTP*431*D8*20240715~
HI*BK>Z00129~
LX*1~
SV1*HC>99212*75*UN*1***1**Y~
DTP*472*D8*20240715~
LX*2~
SV1*HC>90471*50*UN*1***2**Y~
DTP*472*D8*20240715~
SE*39*0001~
GE*1*1~
IEA*1*000000001~
""".strip()

@pytest.fixture(scope="session")
def multiple_billing_providers_mixed_claims_837p_edi_string() -> str:
    """
    Provides an 837P EDI string with multiple billing providers in a single transaction set,
    demonstrating various claim scenarios:
    - Billing Provider 1:
      - Subscriber 1 (self-patient): 2 direct subscriber claims
      - Subscriber 2: 1 direct subscriber claim + 1 dependent patient claim
    - Billing Provider 2:
      - Subscriber 3: 2 dependent patient claims (no direct subscriber claims)
      - Subscriber 4 (self-patient): 1 direct subscriber claim

    Total: 2 Billing Providers, 4 Subscribers, 2 Patients, 7 Claims, 8 Service Lines
    """
    return """
ISA*00*          *00*          *ZZ*SENDERID       *ZZ*RECEIVERID     *240715*1200*^*00501*000000001*0*P*>~
GS*HC*SENDER*RECEIVER*20240715*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
BHT*0019*00*MULTIPROV*20240715*1200*CH~
NM1*41*2*MULTI PROVIDER BILLING*****46*SUBMITTER1~
PER*IC*BILLING DEPT*TE*8005551212~
NM1*40*2*UNIFIED PAYER*****46*RECEIVER1~
HL*1**20*1~
NM1*85*2*PRIMARY CARE CLINIC*****XX*1111111111~
N3*100 MAIN ST~
N4*MEDTOWN*CA*90210~
REF*EI*111111111~
HL*2*1*22*0~
SBR*P*18*GRP100******CI~
NM1*IL*1*WILSON*SARAH****MI*SUB100~
NM1*PR*2*UNIFIED PAYER*****PI*PAYER100~
CLM*WILSON_OFFICE1*150***11>B>1*Y*A*Y*Y~
DTP*431*D8*20240701~
HI*BK>Z000~
LX*1~
SV1*HC>99213*150*UN*1***1**Y~
DTP*472*D8*20240701~
CLM*WILSON_OFFICE2*200***11>B>1*Y*A*Y*Y~
DTP*431*D8*20240708~
HI*BK>Z001~
LX*1~
SV1*HC>99214*200*UN*1***1**Y~
DTP*472*D8*20240708~
HL*3*1*22*1~
SBR*P*18*GRP200******CI~
NM1*IL*1*GARCIA*MARIA****MI*SUB200~
NM1*PR*2*UNIFIED PAYER*****PI*PAYER200~
CLM*GARCIA_SELF*100***11>B>1*Y*A*Y*Y~
DTP*431*D8*20240705~
HI*BK>Z002~
LX*1~
SV1*HC>99212*100*UN*1***1**Y~
DTP*472*D8*20240705~
HL*4*3*23*0~
PAT*19~
NM1*QC*1*GARCIA*PEDRO~
N3*456 FAMILY WAY~
N4*MEDTOWN*CA*90210~
DMG*D8*20100615*M~
CLM*PEDRO_CHECKUP*125***11>B>1*Y*A*Y*Y~
DTP*431*D8*20240710~
HI*BK>Z003~
LX*1~
SV1*HC>99213*125*UN*1***1**Y~
DTP*472*D8*20240710~
HL*5**20*1~
NM1*85*2*SPECIALTY CLINIC*****XX*2222222222~
N3*200 HEALTH BLVD~
N4*CARETOWN*TX*75001~
REF*EI*222222222~
HL*6*5*22*1~
SBR*P*18*GRP300******CI~
NM1*IL*1*THOMPSON*JAMES****MI*SUB300~
NM1*PR*2*UNIFIED PAYER*****PI*PAYER300~
HL*7*6*23*0~
PAT*19~
NM1*QC*1*THOMPSON*EMILY~
N3*789 CHILD ST~
N4*CARETOWN*TX*75001~
DMG*D8*20120320*F~
CLM*EMILY_EXAM1*175***11>B>1*Y*A*Y*Y~
DTP*431*D8*20240712~
HI*BK>Z004~
LX*1~
SV1*HC>99214*175*UN*1***1**Y~
DTP*472*D8*20240712~
CLM*EMILY_EXAM2*225***11>B>1*Y*A*Y*Y~
DTP*431*D8*20240715~
HI*BK>Z005~
LX*1~
SV1*HC>99215*125*UN*1***1**Y~
DTP*472*D8*20240715~
LX*2~
SV1*HC>90834*100*UN*1***2**Y~
DTP*472*D8*20240715~
HL*8*5*22*0~
SBR*P*18*GRP400******CI~
NM1*IL*1*DAVIS*MICHAEL****MI*SUB400~
NM1*PR*2*UNIFIED PAYER*****PI*PAYER400~
CLM*DAVIS_CONSULT*300***11>B>1*Y*A*Y*Y~
DTP*431*D8*20240716~
HI*BK>Z006~
LX*1~
SV1*HC>99215*300*UN*1***1**Y~
DTP*472*D8*20240716~
SE*75*0001~
GE*1*1~
IEA*1*000000001~
""".strip()

@pytest.fixture(scope="session")
def edi_with_ack_requested(valid_837p_edi_string: str) -> str:
    """
    Takes the valid 837P EDI and flips the ISA14 flag to '1'
    to request a TA1 acknowledgment.
    """
    return valid_837p_edi_string.replace("*0*P*>", "*1*P*>")

@pytest.fixture(scope="session")
def edi_with_isa_error(valid_837p_edi_string: str) -> str:
    """
    Takes the valid 837P EDI and creates an ICN mismatch error
    between the ISA and IEA segments.
    """
    return valid_837p_edi_string.replace("IEA*1*000000001~", "IEA*1*999999999~")

@pytest.fixture(scope="session")
def complex_837p_edi_string() -> str:
    """
    Provides a complex, compliant 837P EDI string for advanced structure parsing tests.
    This file contains:
    - Subscriber 1 (John Doe), who is the patient, with 2 claims.
      - Claim 1 has 2 service lines.
      - Claim 2 has 1 service line.
    - Subscriber 2 (Jane Smith), with 1 dependent patient (Ted Smith).
      - Dependent has 1 claim with 1 service line.
    Total: 2 Subscribers, 3 Claims, 4 Service Lines.
    """
    return """
ISA*00*          *00*          *ZZ*SENDERID       *ZZ*RECEIVERID     *240715*1200*^*00501*000000001*0*P*>~
GS*HC*SENDER*RECEIVER*20240715*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
BHT*0019*00*BATCH01*20240715*1200*CH~
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
CLM*JOHNDOE_CLAIM1*500***11>B>1*Y*A*Y*Y~
HI*BK>J100~
LX*1~
SV1*HC>99213*125*UN*1***1**Y~
DTP*472*D8*20240715~
LX*2~
SV1*HC>99214*125*UN*1***2**Y~
DTP*472*D8*20240715~
CLM*JOHNDOE_CLAIM2*25***11>B>1*Y*A*Y*Y~
HI*BK>F410~
LX*1~
SV1*HC>99203*25*UN*1***1**Y~
DTP*472*D8*20240715~
HL*3*1*22*1~
SBR*P*18*GRP456******CI~
NM1*IL*1*SMITH*JANE****MI*SUBID456~
NM1*PR*2*PAYER A*****PI*PAYERID123~
HL*4*3*23*0~
PAT*19~
NM1*QC*1*SMITH*TED~
N3*456 OAK AVE~
N4*OTHERTOWN*FL*33123~
DMG*D8*20150510*M~
CLM*TEDSMITH_CLAIM1*75***11>B>1*Y*A*Y*Y~
HI*BK>R05~
LX*1~
SV1*HC>99215*75*UN*1***1**Y~
DTP*472*D8*20240715~
SE*50*0001~
GE*1*1~
IEA*1*000000001~
""".strip()