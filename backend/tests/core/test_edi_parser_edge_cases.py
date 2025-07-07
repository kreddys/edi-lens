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

# A valid ISA segment of the correct length (106 chars) using standard delimiters
VALID_ISA_STD_DELIMITERS = "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *240715*1200*^*00501*000000001*0*P*:"

# An ISA using a newline as the segment terminator
VALID_ISA_NEWLINE_DELIMITER = "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *240715*1200*^*00501*000000001*0*P*:\n"


# --- Existing Test Data ---
MULTI_GROUP_EDI = """
ISA*00*          *00*          *ZZ*SENDER1        *ZZ*RECEIVER1      *240715*1200*^*00501*000000001*0*P*:~
GS*HC*SENDER1*RECEIVER1*20240715*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
BHT*0019*00*TXN1*20240715*1200*CH~
SE*3*0001~
GE*1*1~
GS*HC*SENDER2*RECEIVER2*20240715*1201*2*X*005010X222A1~
ST*837*0002*005010X222A1~
BHT*0019*00*TXN2*20240715*1201*CH~
SE*3*0002~
GE*1*2~
IEA*2*000000001~
""".strip().replace(">", ":")

MIXED_LINE_ENDINGS_EDI = f"{VALID_ISA_STD_DELIMITERS}~\r\nGS*HC*SENDER*RECEIVER*20240715*1200*1*X*005010X222A1~\nST*837*0001*005010X222A1~\rSE*2*0001~\r\nGE*1*1~\nIEA*1*1~"
MISMATCHED_CONTROL_NUMBERS_EDI = f"{VALID_ISA_STD_DELIMITERS}~\nGS*HC*SENDER*RECEIVER*20240715*1200*10*X*005010X222A1~\nST*837*0001*005010X222A1~\nSE*2*9999~\nGE*1*20~\nIEA*1*000000999~"
TRAILING_DATA_EDI = MISMATCHED_CONTROL_NUMBERS_EDI + "\n~JUNK*DATA*AFTER*IEA~"
SINGLE_LINE_EDI = f"{VALID_ISA_STD_DELIMITERS}~GS*HC*SENDER*RECEIVER*20240715*1200*1*X*005010X222A1~ST*837*0001*005010X222A1~SE*2*0001~GE*1*1~IEA*1*1~"
NEWLINE_TERMINATOR_EDI = f"{VALID_ISA_NEWLINE_DELIMITER}GS*HC*SENDER*RECEIVER*20240715*1200*1*X*005010X222A1\nST*837*0001\nSE*2*0001\nGE*1*1\nIEA*1*1\n"

# --- New Test Data for Additional Edge Cases ---
EMPTY_SEGMENTS_EDI = f"{VALID_ISA_STD_DELIMITERS}~GS*HC*SENDER*RECEIVER*240715*1200*1*X*005010X222A1~~ST*837*0001~SE*2*0001~GE*1*1~IEA*1*1~"
ENVELOPE_ONLY_EDI = f"{VALID_ISA_STD_DELIMITERS}~IEA*0*000000001~"
EMPTY_GROUP_EDI = f"{VALID_ISA_STD_DELIMITERS}~GS*HC*SENDER*RECEIVER*240715*1200*1*X*005010X222A1~GE*0*1~IEA*1*000000001~"


# --- Existing Tests ---
def test_parser_handles_multiple_functional_groups(x222a1_schema: ImplementationGuideSchema):
    parser = EdiParser(edi_string=MULTI_GROUP_EDI, schema=x222a1_schema)
    interchange = parser.parse()
    assert interchange is not None
    assert len(interchange.errors) == 0
    assert len(interchange.functional_groups) == 2

def test_parser_handles_mixed_line_endings(x222a1_schema: ImplementationGuideSchema):
    parser = EdiParser(edi_string=MIXED_LINE_ENDINGS_EDI, schema=x222a1_schema)
    assert len(parser.all_segments) == 6
    interchange = parser.parse()
    assert len(interchange.errors) == 0

def test_parser_is_not_responsible_for_control_number_validation(x222a1_schema: ImplementationGuideSchema):
    parser = EdiParser(edi_string=MISMATCHED_CONTROL_NUMBERS_EDI, schema=x222a1_schema)
    interchange = parser.parse()
    assert len(interchange.errors) == 0

def test_parser_ignores_trailing_data_after_iea(x222a1_schema: ImplementationGuideSchema):
    parser = EdiParser(edi_string=TRAILING_DATA_EDI, schema=x222a1_schema)
    assert len(parser.all_segments) == 6
    interchange = parser.parse()
    assert len(interchange.errors) == 0

def test_parser_handles_single_line_edi(x222a1_schema: ImplementationGuideSchema):
    parser = EdiParser(edi_string=SINGLE_LINE_EDI, schema=x222a1_schema)
    assert len(parser.all_segments) == 6
    interchange = parser.parse()
    assert len(interchange.errors) == 0

def test_parser_handles_newline_segment_terminator(x222a1_schema: ImplementationGuideSchema):
    parser = EdiParser(edi_string=NEWLINE_TERMINATOR_EDI, schema=x222a1_schema)
    assert len(parser.all_segments) == 6
    interchange = parser.parse()
    assert len(interchange.errors) == 0

# --- New Tests ---
def test_parser_ignores_empty_segments(x222a1_schema: ImplementationGuideSchema):
    """
    Ensures that consecutive segment terminators (e.g., '~~') result in the
    empty segment being ignored, not causing a parse failure.
    """
    parser = EdiParser(edi_string=EMPTY_SEGMENTS_EDI, schema=x222a1_schema)
    # The empty segment '~~' should be ignored, resulting in 6 total segments.
    assert len(parser.all_segments) == 6
    interchange = parser.parse()
    assert len(interchange.errors) == 0
    assert len(interchange.functional_groups) == 1
    assert len(interchange.functional_groups[0].transactions) == 1
    assert interchange.functional_groups[0].transactions[0].header.segment_id == "ST"

def test_parser_handles_envelope_only_file(x222a1_schema: ImplementationGuideSchema):
    """
    Verifies the parser can handle a file that contains only an ISA/IEA
    and no functional groups, which is a valid scenario.
    """
    parser = EdiParser(edi_string=ENVELOPE_ONLY_EDI, schema=x222a1_schema)
    assert len(parser.all_segments) == 2
    interchange = parser.parse()
    assert len(interchange.errors) == 0
    assert len(interchange.functional_groups) == 0

def test_parser_handles_empty_functional_group(x222a1_schema: ImplementationGuideSchema):
    """
    Verifies the parser can handle a file with a GS/GE group that contains
    no ST/SE transactions. This is a validation issue, not a parsing one.
    """
    parser = EdiParser(edi_string=EMPTY_GROUP_EDI, schema=x222a1_schema)
    assert len(parser.all_segments) == 4
    interchange = parser.parse()
    assert len(interchange.errors) == 0
    assert len(interchange.functional_groups) == 1
    # The functional group should be present but contain no transactions.
    assert len(interchange.functional_groups[0].transactions) == 0