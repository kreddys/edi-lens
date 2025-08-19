# FILE: nifi-edi-processors/tests/conftest.py

import pytest
import json
import sys
import os
import logging
import uuid
import time
from pathlib import Path
from typing import Generator

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from edi_common.edi_schema_models import ImplementationGuideSchema

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
def standalone_schema() -> ImplementationGuideSchema:
    """
    A session-scoped fixture specifically for UNIT TESTS.
    It loads the 837p schema directly from its runtime file path,
    bypassing any complex setup. This ensures true isolation for parser tests.
    """
    try:
        # Try to find schema in the nifi-edi-processors directory structure
        project_root = Path(__file__).parent.parent
        schema_path = project_root / "schemas" / "837.5010.X222.A1.json"
        
        # If not found, try alternative locations
        if not schema_path.exists():
            schema_path = project_root / "data" / "edi_schemas" / "837.5010.X222.A1.json"
            
        if not schema_path.exists():
            pytest.skip(f"Unit test schema file not found at: {schema_path}")
        
        with open(schema_path, 'r') as f:
            schema_data = json.load(f)
            return ImplementationGuideSchema.model_validate(schema_data)
    except Exception as e:
        pytest.skip(f"Failed to load or parse the schema for unit tests: {e}")

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