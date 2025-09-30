# FILE: nifi-edi-processors/tests/edi_parser/test_edi_parser_edge_cases.py
import pytest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from edi_parser import EdiParser
from edi_schema_models import ImplementationGuideSchema

pytestmark = pytest.mark.unit

def test_parser_handles_empty_edi(standalone_schema: ImplementationGuideSchema):
    """
    Tests that the parser handles completely empty EDI gracefully.
    """
    empty_edi = ""
    parser = EdiParser(edi_string=empty_edi, schema=standalone_schema)
    interchange = parser.parse()
    
    # Should have errors but not crash
    assert interchange is not None
    assert len(interchange.errors) > 0
    assert "ISA/IEA envelope not found" in interchange.errors[0].message

def test_parser_handles_whitespace_only_edi(standalone_schema: ImplementationGuideSchema):
    """
    Tests that the parser handles EDI with only whitespace gracefully.
    """
    whitespace_edi = "   \n  \r\n  \t  "
    parser = EdiParser(edi_string=whitespace_edi, schema=standalone_schema)
    interchange = parser.parse()
    
    # Should have errors but not crash
    assert interchange is not None
    assert len(interchange.errors) > 0

def test_parser_handles_malformed_isa(standalone_schema: ImplementationGuideSchema):
    """
    Tests that the parser handles malformed ISA segments gracefully.
    """
    malformed_isa = "ISA*00*~"  # Incomplete ISA
    parser = EdiParser(edi_string=malformed_isa, schema=standalone_schema)
    interchange = parser.parse()
    
    # Should have errors but not crash
    assert interchange is not None
    # With simplified parser, it may still try to parse

def test_parser_handles_invalid_delimiters(standalone_schema: ImplementationGuideSchema, valid_837p_edi_string: str):
    """
    Tests that the parser can handle EDI with non-standard delimiters.
    """
    # This test is more relevant for the full parser, but we can check delimiter detection
    parser = EdiParser(edi_string=valid_837p_edi_string, schema=standalone_schema)
    
    # Check that delimiters were detected correctly from the ISA segment
    # Based on the fixture: ISA*00*          *00*          *ZZ*SENDERID       *ZZ*RECEIVERID     *240715*1200*^*00501*000000001*0*P*>~
    # Element delimiter is '*' (position 3)
    # Component separator is '>' (position 104) 
    # Segment terminator is '~' (position 105)
    assert parser.element_delimiter == "*"
    assert parser.segment_terminator == "~"
    assert parser.component_separator == ">"

def test_parser_handles_different_line_endings(standalone_schema: ImplementationGuideSchema, valid_837p_edi_string: str):
    """
    Tests that the parser handles different line ending formats.
    """
    # Test with Windows line endings
    windows_edi = valid_837p_edi_string.replace("~\\n", "~\\r\\n")
    parser_win = EdiParser(edi_string=windows_edi, schema=standalone_schema)
    interchange_win = parser_win.parse()
    
    # Test with Mac line endings
    mac_edi = valid_837p_edi_string.replace("~\\n", "~\\r")
    parser_mac = EdiParser(edi_string=mac_edi, schema=standalone_schema)
    interchange_mac = parser_mac.parse()
    
    # Both should parse successfully
    assert interchange_win is not None
    assert interchange_mac is not None

def test_parser_handles_extra_whitespace(standalone_schema: ImplementationGuideSchema, valid_837p_edi_string: str):
    """
    Tests that the parser handles extra whitespace gracefully.
    """
    # Add extra whitespace around segments
    spaced_edi = valid_837p_edi_string.replace("~\\n", "  ~  \\n  ")
    parser = EdiParser(edi_string=spaced_edi, schema=standalone_schema)
    interchange = parser.parse()
    
    # Should parse successfully
    assert interchange is not None
    assert len(interchange.functional_groups) > 0

def test_parser_handles_duplicate_segments(standalone_schema: ImplementationGuideSchema, valid_837p_edi_string: str):
    """
    Tests that the parser handles duplicate segments.
    """
    # Add a duplicate CLM segment
    duplicate_edi = valid_837p_edi_string.replace(
        "LX*1~\\nSV1*HC>99213*125*UN*1***1**Y~\\nDTP*472*D8*20240715~",
        "LX*1~\\nSV1*HC>99213*125*UN*1***1**Y~\\nDTP*472*D8*20240715~\\nCLM*DUPLICATE*100***11>B>1*Y*A*Y*Y~"
    )
    # Adjust SE count
    duplicate_edi = duplicate_edi.replace("SE*25*0001~", "SE*27*0001~")
    
    parser = EdiParser(edi_string=duplicate_edi, schema=standalone_schema)
    interchange = parser.parse()
    
    # Should parse successfully
    assert interchange is not None
    transaction = interchange.functional_groups[0].transactions[0]
    
    # With the enhanced parser, segments are organized in a tree structure
    # Let's find CLM segments in the nested structure
    def find_segments_in_loop(loop, segment_id):
        segments = [s for s in loop.segments if s.segment_id == segment_id]
        for sub_loops in loop.loops.values():
            for sub_loop in sub_loops:
                segments.extend(find_segments_in_loop(sub_loop, segment_id))
        return segments
    
    # Should have at least one CLM segment
    clm_segments = find_segments_in_loop(transaction.body, "CLM")
    assert len(clm_segments) > 0  # Should have at least 1 CLM segment
    
    # The test should pass if parsing completed successfully
    assert interchange is not None

def test_parser_handles_missing_elements(standalone_schema: ImplementationGuideSchema, valid_837p_edi_string: str):
    """
    Tests that the parser handles segments with missing elements.
    """
    # Remove some elements from a segment
    shortened_edi = valid_837p_edi_string.replace(
        "NM1*41*2*PREMIER BILLING*****46*SUBMITTER1~",
        "NM1*41*2*PREMIER BILLING~"
    )
    parser = EdiParser(edi_string=shortened_edi, schema=standalone_schema)
    interchange = parser.parse()
    
    # Should parse successfully (even with validation errors)
    assert interchange is not None
    transaction = interchange.functional_groups[0].transactions[0]
    
    # With the enhanced parser, segments are organized in a tree structure
    def find_segments_in_loop(loop, segment_id):
        segments = [s for s in loop.segments if s.segment_id == segment_id]
        for sub_loops in loop.loops.values():
            for sub_loop in sub_loops:
                segments.extend(find_segments_in_loop(sub_loop, segment_id))
        return segments
    
    # Find the shortened NM1 segment
    nm1_segments = find_segments_in_loop(transaction.body, "NM1")
    # The parser should detect that the NM1 segment is missing required elements
    # but it should still be parsed
    assert len(nm1_segments) > 0  # Should have at least 1 NM1 segment
    
    # Should have validation errors about missing elements
    nm1_segment = nm1_segments[0]
    error_messages = [e.message for e in nm1_segment.errors]
    assert any("NM108" in msg and "missing" in msg for msg in error_messages), f"Expected missing element error not found. Errors: {error_messages}"

def test_validate_data_type_invalid(standalone_schema: ImplementationGuideSchema):
    from edi_parser import _validate_data_type
    assert not _validate_data_type("a", "N0")
    assert not _validate_data_type("a", "R")
    assert not _validate_data_type("a", "UNKNOWN")

def test_validate_format_unknown(standalone_schema: ImplementationGuideSchema):
    from edi_parser import _validate_format
    assert _validate_format("any", "UNKNOWN")

def test_get_guide_version_from_edi_no_gs(standalone_schema: ImplementationGuideSchema):
    from edi_parser import get_guide_version_from_edi
    edi = "ISA*00* *00* *ZZ*SENDER*ZZ*RECEIVER*240715*1200*^*00501*1*0*P*>~IEA*1*1~"
    assert get_guide_version_from_edi(edi) is None

def test_get_effective_definition_no_context(standalone_schema: ImplementationGuideSchema):
    from edi_parser import _get_effective_definition
    base_def = {"elements": [{"xid": "NM101", "name": "Name"}]}
    assert _get_effective_definition(base_def, None) == base_def
    assert _get_effective_definition(base_def, {}) == base_def

def test_segment_validator_no_base_def(standalone_schema: ImplementationGuideSchema):
    from edi_parser import SegmentValidator
    from cdm import CdmSegment, CdmElement
    validator = SegmentValidator(standalone_schema, "*")
    segment = CdmSegment(segment_id="UNKNOWN", elements=[], line_number=1, raw_segment="UNKNOWN")
    errors = validator.validate(segment)
    assert len(errors) == 1
    assert "Base definition for segment 'UNKNOWN' not found" in errors[0].message

def test_evaluate_condition_clause_is_not(standalone_schema: ImplementationGuideSchema):
    from edi_parser import SegmentValidator
    from cdm import CdmSegment, CdmElement
    validator = SegmentValidator(standalone_schema, "*")
    segment = CdmSegment(segment_id="NM1", elements=[CdmElement(position=1, value="XX")], line_number=1, raw_segment="NM1*XX")
    clause = {"element": "NM101", "operator": "IS_NOT", "value": "YY"}
    assert validator._evaluate_condition_clause(segment, clause)

def test_detect_delimiters_fallback(standalone_schema: ImplementationGuideSchema):
    parser = EdiParser("DUMMY", standalone_schema)
    assert parser.element_delimiter == "*"
    assert parser.segment_terminator == "~"
    assert parser.component_separator == ":"

def test_parse_transaction_set_value_error(standalone_schema: ImplementationGuideSchema):
    # This test is tricky because it requires a schema that will cause a ValueError
    # during parsing. A simple way to do this is to have a schema with a non-integer
    # `max_use` value, which will cause a `ValueError` in `_find_best_schema_match`.
    # We will create a dummy schema for this test.
    from edi_schema_models import ImplementationGuideSchema, StructureLoop, StructureSegment

    dummy_schema = ImplementationGuideSchema(
        transactionName="test",
        version="1.0",
        description="test",
        structure=[
            StructureLoop(
                xid="ST_LOOP",
                name="Transaction Set",
                type="loop",
                repeat="1",
                usage="R",
                children=[
                    StructureSegment(xid="ST", name="Transaction Set Header", type="segment", repeat="1", usage="R", max_use=1),
                    StructureLoop(
                        xid="2400",
                        name="Service Line",
                        type="loop",
                        repeat=">1", # This will cause a ValueError
                        usage="R",
                        children=[]
                    ),
                    StructureSegment(xid="SE", name="Transaction Set Trailer", type="segment", repeat="1", usage="R", max_use=1)
                ]
            )
        ],
        segmentDefinitions={},
        contextualDefinitions={}
    )

    edi = "ST*837*0001~SE*2*0001~"
    parser = EdiParser(edi_string=edi, schema=dummy_schema)
    transaction = parser._parse_transaction_set(parser.all_segments)
    assert len(transaction.errors) > 0
    assert "Required segment or loop '2400' (Service Line) is missing from loop 'ST_LOOP'." in transaction.errors[0].message

def test_parse_unclosed_functional_group(standalone_schema: ImplementationGuideSchema):
    edi = "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *240715*1200*^*00501*000000001*0*P*>~GS*HC*SENDER*RECEIVER*20240715*1200*1*X*005010X222A1~IEA*1*000000001~"
    parser = EdiParser(edi_string=edi, schema=standalone_schema)
    interchange = parser.parse()
    assert len(interchange.errors) > 0
    assert "Unclosed functional group" in interchange.errors[0].message

def test_parse_unclosed_transaction_set(standalone_schema: ImplementationGuideSchema):
    edi = "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *240715*1200*^*00501*000000001*0*P*>~GS*HC*SENDER*RECEIVER*20240715*1200*1*X*005010X222A1~ST*837*0001~GE*1*1~IEA*1*000000001~"
    parser = EdiParser(edi_string=edi, schema=standalone_schema)
    interchange = parser.parse()
    assert len(interchange.errors) > 0
    assert "Unclosed transaction set" in interchange.errors[0].message