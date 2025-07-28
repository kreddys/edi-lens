# FILE: backend/tests/core/test_edi_parser_complex_structures.py
import pytest
from src.core.edi_parser import EdiParser
from src.edi_schemas.edi_guide import ImplementationGuideSchema
from src.core.cdm import CdmInterchange, CdmLoop

pytestmark = pytest.mark.unit

@pytest.fixture(scope="module")
def parsed_complex_transaction_body(standalone_schema: ImplementationGuideSchema, complex_837p_edi_string: str) -> CdmLoop:
    """A fixture that parses the complex EDI and returns the main transaction body loop."""
    parser = EdiParser(edi_string=complex_837p_edi_string, schema=standalone_schema)
    interchange = parser.parse()

    # Pre-test assertion: ensure the complex file parses without any errors
    all_errors = []
    # Simplified error collection for the single transaction
    transaction = interchange.functional_groups[0].transactions[0]
    all_errors.extend(transaction.errors)
    def collect_loop_errors(loop):
        errors = list(loop.errors)
        for s in loop.segments: errors.extend(s.errors)
        for _, loop_list in loop.loops.items():
            for l in loop_list: errors.extend(collect_loop_errors(l))
        return errors
    all_errors.extend(collect_loop_errors(transaction.body))
    
    assert not all_errors, f"Complex EDI fixture failed to parse cleanly: {[e.message for e in all_errors]}"
    
    # Return the body of the single transaction
    return interchange.functional_groups[0].transactions[0].body

def test_parser_correctly_counts_loops(parsed_complex_transaction_body: CdmLoop):
    """
    Tests high-level counts to ensure the parser correctly handles multiple loops
    within a single transaction.
    """
    billing_provider_loop = parsed_complex_transaction_body.get_loop("2000A")
    assert billing_provider_loop is not None

    # There should be two subscriber HL loops (2000B) under the billing provider
    subscriber_loops = billing_provider_loop.get_loops("2000B")
    assert len(subscriber_loops) == 2, "Parser did not find both subscriber (2000B) loops."

    # First subscriber should have 2 claims (2300 loops)
    assert len(subscriber_loops[0].get_loops("2300")) == 2, "Parser did not find both claims for the first subscriber."
    
    # Second subscriber should have 1 claim (2300 loop)
    assert len(subscriber_loops[1].get_loops("2300")) == 1, "Parser did not find the single claim for the second subscriber."

def test_parser_retrieves_deeply_nested_data(parsed_complex_transaction_body: CdmLoop):
    """
    Tests retrieving data from the second service line of the first claim for the first subscriber.
    """
    first_subscriber_loop = parsed_complex_transaction_body.get_loop("2000A").get_loops("2000B")[0]
    first_claim_loop = first_subscriber_loop.get_loops("2300")[0]
    
    assert len(first_claim_loop.get_loops("2400")) == 2, "Expected two service lines for the first claim."
    second_service_line = first_claim_loop.get_loops("2400")[1]
    
    sv1_segment = second_service_line.get_segment("SV1")
    assert sv1_segment is not None
    
    procedure_composite = sv1_segment.get_element(1)
    assert procedure_composite == "HC>99214"
    
    charge_amount = sv1_segment.get_element(2)
    assert charge_amount == "125"

def test_parser_handles_dependent_patient_loop(parsed_complex_transaction_body: CdmLoop):
    """
    Tests that the parser correctly identifies the dependent patient loop (2000C)
    and can extract the patient's relationship to the subscriber.
    """
    second_subscriber_loop = parsed_complex_transaction_body.get_loop("2000A").get_loops("2000B")[1]
    
    assert "2000C" in second_subscriber_loop.loops, "Patient loop (2000C) was not found under the second subscriber loop."
    
    patient_loop = second_subscriber_loop.get_loop("2000C")
    assert patient_loop is not None
    
    pat_segment = patient_loop.get_segment("PAT")
    assert pat_segment is not None
    
    relationship_code = pat_segment.get_element(1)
    assert relationship_code == "19"

def test_parser_maintains_hierarchical_integrity(parsed_complex_transaction_body: CdmLoop):
    """
    Verifies that claims for one subscriber do not incorrectly appear under another.
    """
    subscriber_loops = parsed_complex_transaction_body.get_loop("2000A").get_loops("2000B")
    
    # Get claim IDs from the first subscriber
    first_subscriber_claims = subscriber_loops[0].get_loops("2300")
    first_subscriber_claim_ids = {c.get_segment("CLM").get_element(1) for c in first_subscriber_claims}
    
    # Get claim IDs from the second subscriber
    second_subscriber_claims = subscriber_loops[1].get_loops("2300")
    second_subscriber_claim_ids = {c.get_segment("CLM").get_element(1) for c in second_subscriber_claims}
    
    assert "JOHNDOE_CLAIM1" in first_subscriber_claim_ids
    assert "JOHNDOE_CLAIM2" in first_subscriber_claim_ids
    assert "TEDSMITH_CLAIM1" in second_subscriber_claim_ids
    
    # Crucially, check for cross-contamination
    assert "TEDSMITH_CLAIM1" not in first_subscriber_claim_ids
    assert "JOHNDOE_CLAIM1" not in second_subscriber_claim_ids

def test_validator_fails_on_data_in_not_used_element(standalone_schema: ImplementationGuideSchema, complex_837p_edi_string: str):
    """
    Tests that an error is flagged if data is present in an element marked as "Not Used" (Usage: N).
    NM106 (Name Prefix) is defined as Not Used in the base schema.
    """
    invalid_nm1 = "NM1*41*2*PREMIER BILLING*MR**JR***46*SUBMITTER1~" # Adds MR to NM105 and JR to NM106
    
    invalid_edi = complex_837p_edi_string.replace(
        "NM1*41*2*PREMIER BILLING*****46*SUBMITTER1~",
        invalid_nm1
    )
    
    parser = EdiParser(edi_string=invalid_edi, schema=standalone_schema)
    interchange = parser.parse()    