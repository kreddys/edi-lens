import pytest
from ta1_generator import TA1Generator
from ta1_defs import InterchangeError, TA1NoteCode
from cdm import CdmSegment, CdmElement

pytestmark = pytest.mark.unit

@pytest.fixture
def isa_header_ack_not_requested() -> CdmSegment:
    # --- THIS IS THE FIX ---
    # A realistic, fully populated mock ISA header with correct padding.
    elements_data = [
        'ISA', '00', '          ', '00', '          ', 'ZZ', 'SENDERID       ',
        'ZZ', 'RECEIVERID     ', '240718', '1200', '^', '00501', '000000001',
        '0', 'P', ':'
    ]
    elements = [
        # The first element is the segment ID, so it has no position.
        # Subsequent elements are 1-based.
        CdmElement(position=i, value=val) for i, val in enumerate(elements_data)
    ]
    # The CdmSegment.elements list does not include the segment ID itself.
    return CdmSegment(segment_id="ISA", elements=elements[1:], line_number=1, raw_segment="")
    # --- END OF FIX ---

@pytest.fixture
def isa_header_ack_requested(isa_header_ack_not_requested: CdmSegment) -> CdmSegment:
    # ISA14 is at position 14, which is index 13 in the `elements` list.
    isa_header_ack_not_requested.elements[13] = CdmElement(position=14, value='1')
    return isa_header_ack_not_requested

def test_generate_returns_none_when_no_errors_and_not_requested(isa_header_ack_not_requested):
    generator = TA1Generator()
    result = generator.generate(isa_header=isa_header_ack_not_requested, errors=[])
    assert result is None

def test_generate_accepted_ta1_when_requested(isa_header_ack_requested):
    generator = TA1Generator()
    result = generator.generate(isa_header=isa_header_ack_requested, errors=[])
    assert result is not None
    # Should contain complete EDI interchange (ISA + TA1 + IEA)
    assert "ISA*" in result
    assert "TA1*000000001*240718*1200*A*000" in result
    assert "IEA*" in result
    # Verify sender/receiver are swapped in response
    assert "*ZZ*RECEIVERID     *ZZ*SENDERID       *" in result

def test_generate_rejected_ta1_on_error(isa_header_ack_not_requested):
    generator = TA1Generator()
    errors = [InterchangeError(note_code=TA1NoteCode.ICN_MISMATCH_IN_HEADER_TRAILER)]
    result = generator.generate(isa_header=isa_header_ack_not_requested, errors=errors)
    assert result is not None
    # Should contain complete EDI interchange (ISA + TA1 + IEA)
    assert "ISA*" in result
    assert "TA1*000000001*240718*1200*R*001" in result
    assert "IEA*" in result
    # Verify sender/receiver are swapped in response
    assert "*ZZ*RECEIVERID     *ZZ*SENDERID       *" in result

def test_generate_rejected_ta1_uses_first_error_code(isa_header_ack_requested):
    generator = TA1Generator()
    errors = [
        InterchangeError(note_code=TA1NoteCode.INVALID_TEST_INDICATOR),
        InterchangeError(note_code=TA1NoteCode.ICN_MISMATCH_IN_HEADER_TRAILER)
    ]
    result = generator.generate(isa_header=isa_header_ack_requested, errors=errors)
    assert result is not None
    # Should contain complete EDI interchange (ISA + TA1 + IEA)
    assert "ISA*" in result
    assert "TA1*000000001*240718*1200*R*020" in result
    assert "IEA*" in result
    # Verify sender/receiver are swapped in response
    assert "*ZZ*RECEIVERID     *ZZ*SENDERID       *" in result
