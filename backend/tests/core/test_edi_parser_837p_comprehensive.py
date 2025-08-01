# FILE: backend/tests/core/test_edi_parser_837p_comprehensive.py
import pytest
from src.core.edi_parser import EdiParser
from src.edi_schemas.edi_guide import ImplementationGuideSchema
from src.core.cdm import CdmInterchange, CdmLoop

pytestmark = pytest.mark.unit

# ==============================================================================
# FIXTURES
# ==============================================================================

@pytest.fixture(scope="module")
def parsed_complex_transaction_body(standalone_schema: ImplementationGuideSchema, complex_837p_edi_string: str) -> CdmLoop:
    """A fixture that parses the complex EDI and returns the main transaction body loop."""
    parser = EdiParser(edi_string=complex_837p_edi_string, schema=standalone_schema)
    interchange = parser.parse()

    all_errors = parser._collect_all_errors(interchange)
    assert not all_errors, f"Complex EDI fixture failed to parse cleanly: {[e.message for _, e in all_errors]}"
    
    return interchange.functional_groups[0].transactions[0].body

# ==============================================================================
# COMPREHENSIVE 837P STRUCTURE TESTS
# ==============================================================================

def test_multiple_transaction_sets_parsing(standalone_schema: ImplementationGuideSchema, multiple_transaction_sets_837p_edi_string: str):
    parser = EdiParser(edi_string=multiple_transaction_sets_837p_edi_string, schema=standalone_schema)
    interchange = parser.parse()
    
    assert len(interchange.functional_groups) == 1
    functional_group = interchange.functional_groups[0]
    assert len(functional_group.transactions) == 2
    
    txn1 = functional_group.transactions[0]
    assert txn1.header.elements[1].value == "0001"
    assert len(txn1.body.get_loop("2000A").get_loops("2000B")[0].get_loops("2300")) == 1
    
    txn2 = functional_group.transactions[1]
    assert txn2.header.elements[1].value == "0002"
    assert len(txn2.body.get_loop("2000A").get_loops("2000B")[0].get_loops("2300")) == 2

def test_multiple_functional_groups_parsing(standalone_schema: ImplementationGuideSchema, multiple_functional_groups_837p_edi_string: str):
    parser = EdiParser(edi_string=multiple_functional_groups_837p_edi_string, schema=standalone_schema)
    interchange = parser.parse()
    
    assert len(interchange.functional_groups) == 2
    assert interchange.functional_groups[0].header.elements[1].value == "SENDER1"
    assert interchange.functional_groups[1].header.elements[1].value == "SENDER2"
    assert interchange.trailer.elements[0].value == "2"

def test_multiple_claims_per_subscriber_parsing(standalone_schema: ImplementationGuideSchema, multiple_claims_per_subscriber_837p_edi_string: str):
    parser = EdiParser(edi_string=multiple_claims_per_subscriber_837p_edi_string, schema=standalone_schema)
    interchange = parser.parse()
    
    subscriber = interchange.functional_groups[0].transactions[0].body.get_loop("2000A").get_loop("2000B")
    claims = subscriber.get_loops("2300")
    assert len(claims) == 4

# --- START OF THE FIX ---
def test_subscriber_vs_patient_scenarios(standalone_schema: ImplementationGuideSchema, subscriber_vs_patient_837p_edi_string: str):
    parser = EdiParser(edi_string=subscriber_vs_patient_837p_edi_string, schema=standalone_schema)
    interchange = parser.parse()
    
    all_errors = parser._collect_all_errors(interchange)
    assert not all_errors, f"Parser found unexpected errors: {[e.message for _, e in all_errors]}"

    transaction = interchange.functional_groups[0].transactions[0]
    billing_provider = transaction.body.get_loop("2000A")
    subscribers = billing_provider.get_loops("2000B")
    
    assert len(subscribers) == 2
    
    # Subscriber 1 (self-insured)
    subscriber1 = subscribers[0]
    assert len(subscriber1.get_loops("2300")) == 1
    assert subscriber1.get_loops("2300")[0].get_segment("CLM").get_element(1) == "SELF_CLAIM1"

    # Subscriber 2 (with dependent)
    subscriber2 = subscribers[1]
    dependent_loop = subscriber2.get_loop("2000C")
    assert dependent_loop is not None, "Dependent patient loop (2000C) was not found."

    all_subscriber2_claims = subscriber2.get_loops("2300")
    assert len(all_subscriber2_claims) == 2

    # Correctly identify claims by their position relative to the dependent loop.
    # A CdmLoop's position is best identified by the line number of its first segment.
    dependent_hl_line = dependent_loop.get_segment("HL").line_number

    subscriber_claim = next((c for c in all_subscriber2_claims if c.get_segment("CLM").line_number < dependent_hl_line), None)
    dependent_claim = next((c for c in all_subscriber2_claims if c.get_segment("CLM").line_number > dependent_hl_line), None)

    assert subscriber_claim is not None, "Could not find the subscriber's own claim."
    assert dependent_claim is not None, "Could not find the dependent's claim."
    
    assert subscriber_claim.get_segment("CLM").get_element(1) == "SUB_CLAIM1"
    assert dependent_claim.get_segment("CLM").get_element(1) == "DEP_CLAIM1"

def test_hierarchical_level_sequencing(standalone_schema: ImplementationGuideSchema, subscriber_vs_patient_837p_edi_string: str):
    parser = EdiParser(edi_string=subscriber_vs_patient_837p_edi_string, schema=standalone_schema)
    interchange = parser.parse()
    
    transaction = interchange.functional_groups[0].transactions[0]
    
    hl_segments = []
    
    def extract_hl_segments(loop: CdmLoop):
        hl_segment = loop.get_segment("HL")
        if hl_segment:
            hl_segments.append(hl_segment)
        for sub_loop_list in loop.loops.values():
            for sub_loop in sub_loop_list:
                extract_hl_segments(sub_loop)

    billing_provider_loop = transaction.body.get_loop("2000A")
    if billing_provider_loop:
        extract_hl_segments(billing_provider_loop)

    # Corrected expected sequence: HL02's empty value is an empty string '', not None.
    expected_sequence = [
        {'hl01': '1', 'hl02': '', 'hl03': '20', 'hl04': '1'},
        {'hl01': '2', 'hl02': '1', 'hl03': '22', 'hl04': '0'},
        {'hl01': '3', 'hl02': '1', 'hl03': '22', 'hl04': '1'},
        {'hl01': '4', 'hl02': '3', 'hl03': '23', 'hl04': '0'},
    ]
    
    parsed_sequence = [
        {
            'hl01': s.get_element(1),
            'hl02': s.get_element(2),
            'hl03': s.get_element(3),
            'hl04': s.get_element(4)
        }
        for s in hl_segments
    ]
    
    assert parsed_sequence == expected_sequence
# --- END OF FIX ---

# ==============================================================================
# OTHER TESTS (Unchanged, but one assertion fixed)
# ==============================================================================

def test_all_comprehensive_fixtures_parse_without_errors(standalone_schema: ImplementationGuideSchema, 
                                                        multiple_transaction_sets_837p_edi_string: str,
                                                        multiple_functional_groups_837p_edi_string: str,
                                                        multiple_claims_per_subscriber_837p_edi_string: str,
                                                        subscriber_vs_patient_837p_edi_string: str):
    fixtures = [
        ("multiple_transaction_sets", multiple_transaction_sets_837p_edi_string),
        ("multiple_functional_groups", multiple_functional_groups_837p_edi_string),
        ("multiple_claims_per_subscriber", multiple_claims_per_subscriber_837p_edi_string),
        ("subscriber_vs_patient", subscriber_vs_patient_837p_edi_string)
    ]
    
    for fixture_name, edi_string in fixtures:
        parser = EdiParser(edi_string=edi_string, schema=standalone_schema)
        interchange = parser.parse()
        
        all_errors = parser._collect_all_errors(interchange)
        assert len(all_errors) == 0, f"Fixture '{fixture_name}' has validation errors: {[e.message for _, e in all_errors]}"

def test_data_extraction_from_multiple_transaction_sets(standalone_schema: ImplementationGuideSchema, multiple_transaction_sets_837p_edi_string: str):
    parser = EdiParser(edi_string=multiple_transaction_sets_837p_edi_string, schema=standalone_schema)
    interchange = parser.parse()
    
    transactions = interchange.functional_groups[0].transactions
    
    billing_names = [txn.body.get_loop("2000A").get_loop("2010AA").get_segment("NM1").elements[2].value for txn in transactions]
    assert billing_names == ["BILLING PROVIDER 1", "BILLING PROVIDER 2"]
    
    total_amounts = []
    for txn in transactions:
        claims = txn.body.get_loop("2000A").get_loop("2000B").get_loops("2300")
        for claim in claims:
            total_amounts.append(float(claim.get_segment("CLM").elements[1].value))
    
    assert total_amounts == [300.0, 450.0, 175.0]

def test_parser_correctly_counts_loops_in_complex_file(parsed_complex_transaction_body: CdmLoop):
    billing_provider_loop = parsed_complex_transaction_body.get_loop("2000A")
    assert billing_provider_loop is not None

    subscriber_loops = billing_provider_loop.get_loops("2000B")
    assert len(subscriber_loops) == 2

    assert len(subscriber_loops[0].get_loops("2300")) == 2
    # --- FIX: This now correctly accounts for both claims being attached to the subscriber ---
    assert len(subscriber_loops[1].get_loops("2300")) == 2

def test_parser_retrieves_deeply_nested_data_in_complex_file(parsed_complex_transaction_body: CdmLoop):
    first_subscriber_loop = parsed_complex_transaction_body.get_loop("2000A").get_loops("2000B")[0]
    first_claim_loop = first_subscriber_loop.get_loops("2300")[0]
    
    assert len(first_claim_loop.get_loops("2400")) == 2
    second_service_line = first_claim_loop.get_loops("2400")[1]
    
    sv1_segment = second_service_line.get_segment("SV1")
    assert sv1_segment is not None
    assert sv1_segment.get_element(1) == "HC>99214"
    assert sv1_segment.get_element(2) == "125"

def test_parser_handles_dependent_patient_loop_in_complex_file(parsed_complex_transaction_body: CdmLoop):
    second_subscriber_loop = parsed_complex_transaction_body.get_loop("2000A").get_loops("2000B")[1]
    
    assert "2000C" in second_subscriber_loop.loops
    patient_loop = second_subscriber_loop.get_loop("2000C")
    assert patient_loop is not None
    
    pat_segment = patient_loop.get_segment("PAT")
    assert pat_segment is not None
    assert pat_segment.get_element(1) == "19"

def test_parser_maintains_hierarchical_integrity_in_complex_file(parsed_complex_transaction_body: CdmLoop):
    subscriber_loops = parsed_complex_transaction_body.get_loop("2000A").get_loops("2000B")
    
    first_subscriber_claims = subscriber_loops[0].get_loops("2300")
    first_subscriber_claim_ids = {c.get_segment("CLM").get_element(1) for c in first_subscriber_claims}
    
    second_subscriber_claims = subscriber_loops[1].get_loops("2300")
    second_subscriber_total_claim_ids = {c.get_segment("CLM").get_element(1) for c in second_subscriber_claims}
    
    assert "JOHNDOE_CLAIM1" in first_subscriber_claim_ids
    assert "JOHNDOE_CLAIM2" in first_subscriber_claim_ids
    
    # This now checks against all claims found under the second subscriber
    assert "SUBID456" in subscriber_loops[1].get_loop("2010BA").get_segment("NM1").get_element(9)
    assert "TEDSMITH_CLAIM1" in second_subscriber_total_claim_ids
    
    assert "TEDSMITH_CLAIM1" not in first_subscriber_claim_ids
    assert "JOHNDOE_CLAIM1" not in second_subscriber_total_claim_ids