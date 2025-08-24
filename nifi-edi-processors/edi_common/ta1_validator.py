from typing import List
from datetime import datetime
from cdm import CdmInterchange
from ta1_defs import InterchangeError, TA1NoteCode

def validate_interchange_envelope(interchange: CdmInterchange, raw_edi_string: str) -> List[InterchangeError]:
    """
    Performs TA1-level validation on a fully parsed CdmInterchange object.
    This function is separate from the core parser logic.
    Returns a list of interchange-level errors.
    """
    errors: List[InterchangeError] = []

    def add_error(note_code: TA1NoteCode):
        if not any(e.note_code == note_code for e in errors):
            errors.append(InterchangeError(note_code=note_code))

    # Perform delimiter and structural checks first on the raw string.
    clean_edi = raw_edi_string.strip()
    if not (clean_edi.startswith('ISA') and len(clean_edi) >= 106):
        add_error(TA1NoteCode.INVALID_CONTROL_STRUCTURE)
        return errors # No point in continuing if the basic structure is wrong

    element_sep = clean_edi[3]
    segment_term = clean_edi[105]
    component_sep = clean_edi[104]

    if len(element_sep) != 1 or element_sep.isalnum() or element_sep in ('\r', '\n'):
        add_error(TA1NoteCode.INVALID_ELEMENT_SEPARATOR)
    if len(segment_term) != 1 or segment_term.isalnum():
        add_error(TA1NoteCode.INVALID_SEGMENT_TERMINATOR)
    if len(component_sep) != 1 or component_sep.isalnum():
        add_error(TA1NoteCode.INVALID_COMPONENT_SEPARATOR)

    # If delimiters are invalid, the parsed interchange object is unreliable for element checks.
    if errors:
        return errors

    # If we get here, delimiters are valid, so the parsed interchange object is mostly reliable.
    if not interchange.header.elements or not interchange.trailer.elements:
        add_error(TA1NoteCode.INVALID_CONTROL_STRUCTURE)
        return errors

    isa = interchange.header
    iea = interchange.trailer

    # TA105: 001 - ICN Mismatch
    if isa.get_element(13).strip() != iea.get_element(2).strip():
        add_error(TA1NoteCode.ICN_MISMATCH_IN_HEADER_TRAILER)

    # TA105: 002 & 003 are business logic, not pure syntax

    # TA105: 005 & 006: Invalid Sender ID Qualifier/ID
    if isa.get_element(5).strip() not in ["01", "14", "20", "27", "28", "29", "30", "33", "ZZ"]:
        add_error(TA1NoteCode.INVALID_SENDER_ID_QUALIFIER)
    if not isa.get_element(6) or not isa.get_element(6).strip():
        add_error(TA1NoteCode.INVALID_SENDER_ID)

    # TA105: 007 & 008: Invalid Receiver ID Qualifier/ID
    if isa.get_element(7).strip() not in ["01", "14", "20", "27", "28", "29", "30", "33", "ZZ"]:
        add_error(TA1NoteCode.INVALID_RECEIVER_ID_QUALIFIER)
    if not isa.get_element(8) or not isa.get_element(8).strip():
        add_error(TA1NoteCode.INVALID_RECEIVER_ID)

    # TA105: 010 & 011: Invalid Auth Info
    if isa.get_element(1).strip() not in ["00", "03"]:
        add_error(TA1NoteCode.INVALID_AUTH_QUALIFIER)
    if isa.get_element(1).strip() == "03" and (not isa.get_element(2) or not isa.get_element(2).strip()):
        add_error(TA1NoteCode.INVALID_AUTH_VALUE)
    if isa.get_element(1).strip() == "00" and isa.get_element(2).strip():
        add_error(TA1NoteCode.INVALID_AUTH_VALUE)

    # TA105: 012 & 013: Invalid Security Info
    if isa.get_element(3).strip() not in ["00", "01"]:
        add_error(TA1NoteCode.INVALID_SECURITY_QUALIFIER)
    if isa.get_element(3).strip() == "01" and (not isa.get_element(4) or not isa.get_element(4).strip()):
        add_error(TA1NoteCode.INVALID_SECURITY_VALUE)
    if isa.get_element(3).strip() == "00" and isa.get_element(4).strip():
        add_error(TA1NoteCode.INVALID_SECURITY_VALUE)

    # TA105: 014 & 015: Invalid Date/Time Format
    try: datetime.strptime(isa.get_element(9), '%y%m%d')
    except (ValueError, TypeError): add_error(TA1NoteCode.INVALID_INTERCHANGE_DATE)
    try: datetime.strptime(isa.get_element(10), '%H%M')
    except (ValueError, TypeError): add_error(TA1NoteCode.INVALID_INTERCHANGE_TIME)

    # TA105: 016 & 017: Invalid Standards/Version ID
    if isa.get_element(11) != "^":
        add_error(TA1NoteCode.INVALID_INTERCHANGE_STANDARDS_ID)
    version_id = isa.get_element(12)
    # Version ID should be exactly 5 digits with no spaces
    if not version_id or len(version_id) != 5 or not version_id.isdigit():
        add_error(TA1NoteCode.INVALID_INTERCHANGE_VERSION_ID)

    # TA105: 018: Invalid ICN
    if not isa.get_element(13) or not isa.get_element(13).strip().isdigit() or len(isa.get_element(13).strip()) != 9:
        add_error(TA1NoteCode.INVALID_INTERCHANGE_CONTROL_NUMBER)

    # TA105: 019: Invalid Ack Requested
    if isa.get_element(14) not in ['0', '1']:
         add_error(TA1NoteCode.INVALID_ACKNOWLEDGMENT_REQUESTED)

    # TA105: 020: Invalid Test Indicator
    if isa.get_element(15) not in ['T', 'P']:
         add_error(TA1NoteCode.INVALID_TEST_INDICATOR)

    # TA105: 021: Group Count Mismatch
    try:
        gs_count = len(interchange.functional_groups)
        iea01_count = int(iea.get_element(1))
        if gs_count != iea01_count:
            add_error(TA1NoteCode.INVALID_GROUP_COUNT)
    except (ValueError, TypeError):
        add_error(TA1NoteCode.INVALID_GROUP_COUNT)

    return errors
