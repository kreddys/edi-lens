import pytest
from src.core.edi_parser import parse_edi

# A correctly padded, simple EDI file for testing
VALID_EDI_STRING = "ISA*00*          *00*          *ZZ*SENDERID       *ZZ*RECEIVERID     *240704*1200*^*00501*000000001*0*P*>~GS*HC*SENDER*RECEIVER*20240704*1200*1*X*005010X222A1~ST*837*0001~SE*3*0001~IEA*1*000000001~"

def test_parse_valid_edi_string():
    """
    Tests that a standard, well-formed EDI string is parsed correctly.
    """
    result = parse_edi(VALID_EDI_STRING)

    assert result.error is None
    assert len(result.segments) == 5
    
    # Check delimiters
    assert result.delimiters["element"] == '*'
    assert result.delimiters["segment"] == '~'

    # Check segment IDs
    assert result.segments[0].id == "ISA"
    assert result.segments[1].id == "GS"
    assert result.segments[2].id == "ST"
    assert result.segments[3].id == "SE"
    assert result.segments[4].id == "IEA"

    # Check a specific element value
    assert result.segments[0].elements[5].value == "SENDERID       "
    assert result.segments[1].elements[1].value == "SENDER"

def test_parse_edi_with_newline_delimiter():
    """
    Tests parsing when the segment delimiter is a newline character.
    """
    edi_with_newlines = VALID_EDI_STRING.replace('~', '\n')
    result = parse_edi(edi_with_newlines)

    assert result.error is None
    assert len(result.segments) == 5
    assert result.delimiters["segment"] == '\n'
    assert result.segments[2].id == "ST"

def test_parse_empty_string_returns_error():
    """
    Tests that an empty input string results in an error.
    """
    result = parse_edi("")
    assert result.error == "EDI string is empty."
    assert len(result.segments) == 0

def test_parse_no_valid_segments_returns_error():
    """
    Tests that a string without any valid segments results in an error.
    """
    result = parse_edi("this is not an edi file~")
    assert result.error == "No valid segments found after parsing."
    assert len(result.segments) == 0