# FILE: backend/tests/core/test_edi_parser_complex_structures.py
import pytest
from src.core.edi_parser import EdiParser
from src.edi_schemas.edi_guide import ImplementationGuideSchema
from src.core.cdm import CdmInterchange

pytestmark = pytest.mark.unit

@pytest.fixture(scope="module")
def parsed_complex_interchange(standalone_schema: ImplementationGuideSchema, complex_837p_edi_string: str) -> CdmInterchange:
    """A fixture that parses the complex EDI string once for all tests in this module."""
    parser = EdiParser(edi_string=complex_837p_edi_string, schema=standalone_schema)
    interchange = parser.parse()

    # Pre-test assertion: ensure the complex file parses without any errors
    all_errors = []
    for group in interchange.functional_groups:
        for transaction in group.transactions:
            all_errors.extend(transaction.errors)
    assert not all_errors, f"Complex EDI fixture failed to parse cleanly: {[e.message for e in all_errors]}"
    
    return interchange

def test_parser_correctly_counts_loops(parsed_complex_interchange: CdmInterchange):
    """
    Tests high-level counts to ensure the parser correctly handles multiple loops.
    """
    transactions = parsed_complex_interchange.functional_groups[0].transactions
    
    # The file contains three CLM segments, so there should be three transactions.
    assert len(transactions) == 3, "Parser did not identify all three claims as separate transactions."
    
    # Count all service lines (2400 loops) across all claims.
    total_service_lines = 0
    for txn in transactions:
        claim_loop = txn.body.get_loop("2000A").get_loop("2000B").get_loop("2300")
        total_service_lines += len(claim_loop.get_loops("2400"))
        
    assert total_service_lines == 4, "Parser did not correctly count all service lines across all claims."

    # Count all patient loops (2000C loops)
    total_patient_loops = 0
    for txn in transactions:
        subscriber_loop = txn.body.get_loop("2000A").get_loop("2000B")
        total_patient_loops += len(subscriber_loop.get_loops("2000C"))

    assert total_patient_loops == 1, "Parser did not correctly identify the single dependent patient loop."

def test_parser_retrieves_deeply_nested_data(parsed_complex_interchange: CdmInterchange):
    """
    Tests the ability to navigate the parsed CDM and retrieve data from a specific,
    deeply nested location (second service line of the first claim).
    """
    # Navigate to the first transaction (John Doe's claims)
    transaction = parsed_complex_interchange.functional_groups[0].transactions[0]
    
    # Navigate to the second service line of the first claim
    claim_loop = transaction.body.get_loop("2000A").get_loop("2000B").get_loop("2300")
    second_service_line = claim_loop.get_loops("2400")[1] # 0-indexed list
    
    sv1_segment = second_service_line.get_segment("SV1")
    assert sv1_segment is not None
    
    # Assert the procedure code and charge amount are correct for that specific line
    procedure_composite = sv1_segment.get_element(1)
    assert procedure_composite == "HC>99214"
    
    charge_amount = sv1_segment.get_element(2)
    assert charge_amount == "125"

def test_parser_handles_dependent_patient_loop(parsed_complex_interchange: CdmInterchange):
    """
    Tests that the parser correctly identifies the dependent patient loop (2000C)
    and can extract the patient's relationship to the subscriber.
    """
    # Navigate to the third transaction (Ted Smith's claim, who is a dependent)
    transaction = parsed_complex_interchange.functional_groups[0].transactions[2]
    
    subscriber_loop = transaction.body.get_loop("2000A").get_loop("2000B")
    
    # Assert that this subscriber loop contains a patient loop
    assert "2000C" in subscriber_loop.loops, "Patient loop (2000C) was not found under the subscriber loop."
    
    patient_loop = subscriber_loop.get_loop("2000C")
    assert patient_loop is not None
    
    pat_segment = patient_loop.get_segment("PAT")
    assert pat_segment is not None
    
    # PAT01 defines the relationship. '19' is for 'Child'.
    relationship_code = pat_segment.get_element(1)
    assert relationship_code == "19"