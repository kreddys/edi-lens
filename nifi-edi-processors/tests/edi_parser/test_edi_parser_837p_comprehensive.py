# FILE: backend/tests/core/test_edi_parser_837p_comprehensive.py
import pytest
from edi_parser import EdiParser
from edi_schema_models import ImplementationGuideSchema
from cdm import CdmInterchange, CdmLoop

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
    """Test basic parsing of multiple transaction sets with mixed valid/invalid transactions."""
    parser = EdiParser(edi_string=multiple_transaction_sets_837p_edi_string, schema=standalone_schema)
    interchange = parser.parse()

    # Parser should successfully process the entire file despite errors in some transactions
    assert len(interchange.functional_groups) == 1
    functional_group = interchange.functional_groups[0]
    assert len(functional_group.transactions) == 2

    # Transaction 1 should be valid and accessible
    txn1 = functional_group.transactions[0]
    assert txn1.header.elements[1].value == "0001"
    assert len(txn1.body.get_loop("2000A").get_loops("2000B")[0].get_loops("2300")) == 1

    # Transaction 2 should be accessible but contain structural errors due to missing required segments
    txn2 = functional_group.transactions[1]
    assert txn2.header.elements[1].value == "0002"
    # Transaction 2 doesn't have proper loop structure due to missing required segments

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
                                                        multiple_functional_groups_837p_edi_string: str,
                                                        multiple_claims_per_subscriber_837p_edi_string: str,
                                                        subscriber_vs_patient_837p_edi_string: str):
    """Test that comprehensive fixtures parse without errors (excluding those with intentional errors)."""
    fixtures = [
        ("multiple_functional_groups", multiple_functional_groups_837p_edi_string),
        ("multiple_claims_per_subscriber", multiple_claims_per_subscriber_837p_edi_string),
        ("subscriber_vs_patient", subscriber_vs_patient_837p_edi_string)
    ]
    # Note: multiple_transaction_sets fixture excluded as it now contains intentional errors for error handling tests

    for fixture_name, edi_string in fixtures:
        parser = EdiParser(edi_string=edi_string, schema=standalone_schema)
        interchange = parser.parse()

        all_errors = parser._collect_all_errors(interchange)
        assert len(all_errors) == 0, f"Fixture '{fixture_name}' has validation errors: {[e.message for _, e in all_errors]}"

def test_data_extraction_from_multiple_transaction_sets(standalone_schema: ImplementationGuideSchema, multiple_transaction_sets_837p_edi_string: str):
    """Test data extraction from valid transaction in a file with mixed valid/invalid transactions."""
    parser = EdiParser(edi_string=multiple_transaction_sets_837p_edi_string, schema=standalone_schema)
    interchange = parser.parse()

    transactions = interchange.functional_groups[0].transactions

    # Only test the valid transaction (transaction 1)
    valid_txn = transactions[0]
    assert valid_txn.body.get_loop("2000A") is not None

    billing_name = valid_txn.body.get_loop("2000A").get_loop("2010AA").get_segment("NM1").elements[2].value
    assert billing_name == "BILLING PROVIDER 1"

    # Extract claim amount from valid transaction
    claims = valid_txn.body.get_loop("2000A").get_loop("2000B").get_loops("2300")
    assert len(claims) == 1
    claim_amount = float(claims[0].get_segment("CLM").elements[1].value)
    assert claim_amount == 300.0

    # Verify that transaction 2 has errors (as expected)
    all_errors = parser._collect_all_errors(interchange)
    assert len(all_errors) > 0, "Transaction 2 should have validation errors"

def test_parser_correctly_counts_loops_in_complex_file(parsed_complex_transaction_body: CdmLoop):
    billing_provider_loop = parsed_complex_transaction_body.get_loop("2000A")
    assert billing_provider_loop is not None

    subscriber_loops = billing_provider_loop.get_loops("2000B")
    assert len(subscriber_loops) == 2

    assert len(subscriber_loops[0].get_loops("2300")) == 2

    # Subscriber 2 (Jane Smith) has 1 claim (from her dependent Ted Smith)
    assert len(subscriber_loops[1].get_loops("2300")) == 1

    # Check that subscriber 2 has a patient loop (dependent Ted Smith)
    patient_loops = subscriber_loops[1].get_loops("2000C")
    assert len(patient_loops) == 1

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

# ==============================================================================
# MULTIPLE BILLING PROVIDERS WITH MIXED CLAIM SCENARIOS TESTS
# ==============================================================================

def test_multiple_billing_providers_structure(standalone_schema: ImplementationGuideSchema, multiple_billing_providers_mixed_claims_837p_edi_string: str):
    """Test that multiple billing providers within a single transaction set are parsed correctly."""
    parser = EdiParser(edi_string=multiple_billing_providers_mixed_claims_837p_edi_string, schema=standalone_schema)
    interchange = parser.parse()

    all_errors = parser._collect_all_errors(interchange)
    assert not all_errors, f"Multiple billing providers fixture failed to parse cleanly: {[e.message for _, e in all_errors]}"

    transaction_body = interchange.functional_groups[0].transactions[0].body

    # Should have 2 billing providers (2000A loops)
    billing_provider_loops = transaction_body.get_loops("2000A")
    assert len(billing_provider_loops) == 2

    # Verify provider names
    provider1_name = billing_provider_loops[0].get_loop("2010AA").get_segment("NM1").get_element(3)
    provider2_name = billing_provider_loops[1].get_loop("2010AA").get_segment("NM1").get_element(3)
    assert provider1_name == "PRIMARY CARE CLINIC"
    assert provider2_name == "SPECIALTY CLINIC"

def test_mixed_claim_scenarios_subscriber_vs_patient_level(standalone_schema: ImplementationGuideSchema, multiple_billing_providers_mixed_claims_837p_edi_string: str):
    """Test various combinations of subscriber-level and patient-level claims."""
    parser = EdiParser(edi_string=multiple_billing_providers_mixed_claims_837p_edi_string, schema=standalone_schema)
    interchange = parser.parse()
    transaction_body = interchange.functional_groups[0].transactions[0].body

    billing_providers = transaction_body.get_loops("2000A")

    # BILLING PROVIDER 1 TESTS
    provider1_subscribers = billing_providers[0].get_loops("2000B")
    assert len(provider1_subscribers) == 2

    # Subscriber 1 (Sarah Wilson) - self as patient, 2 direct subscriber claims
    subscriber1 = provider1_subscribers[0]
    subscriber1_claims = subscriber1.get_loops("2300")
    assert len(subscriber1_claims) == 2
    subscriber1_patients = subscriber1.get_loops("2000C")
    assert len(subscriber1_patients) == 0  # No separate patient loop (self-patient)

    # Verify claim IDs for subscriber 1
    sub1_claim_ids = {claim.get_segment("CLM").get_element(1) for claim in subscriber1_claims}
    assert "WILSON_OFFICE1" in sub1_claim_ids
    assert "WILSON_OFFICE2" in sub1_claim_ids

    # Subscriber 2 (Maria Garcia) - 1 direct subscriber claim + 1 dependent patient claim
    subscriber2 = provider1_subscribers[1]
    subscriber2_claims = subscriber2.get_loops("2300")
    assert len(subscriber2_claims) == 2  # 1 direct + 1 from dependent
    subscriber2_patients = subscriber2.get_loops("2000C")
    assert len(subscriber2_patients) == 1  # 1 dependent patient

    # Verify claim IDs for subscriber 2
    sub2_claim_ids = {claim.get_segment("CLM").get_element(1) for claim in subscriber2_claims}
    assert "GARCIA_SELF" in sub2_claim_ids  # Direct subscriber claim
    assert "PEDRO_CHECKUP" in sub2_claim_ids  # Dependent's claim

    # BILLING PROVIDER 2 TESTS
    provider2_subscribers = billing_providers[1].get_loops("2000B")
    assert len(provider2_subscribers) == 2

    # Subscriber 3 (James Thompson) - NO direct claims, only dependent patient claims
    subscriber3 = provider2_subscribers[0]
    subscriber3_claims = subscriber3.get_loops("2300")
    assert len(subscriber3_claims) == 2  # All from dependent patient
    subscriber3_patients = subscriber3.get_loops("2000C")
    assert len(subscriber3_patients) == 1  # 1 dependent patient

    # Verify claim IDs for subscriber 3 (all should be from dependent Emily)
    sub3_claim_ids = {claim.get_segment("CLM").get_element(1) for claim in subscriber3_claims}
    assert "EMILY_EXAM1" in sub3_claim_ids
    assert "EMILY_EXAM2" in sub3_claim_ids

    # Subscriber 4 (Michael Davis) - self as patient, 1 direct subscriber claim
    subscriber4 = provider2_subscribers[1]
    subscriber4_claims = subscriber4.get_loops("2300")
    assert len(subscriber4_claims) == 1
    subscriber4_patients = subscriber4.get_loops("2000C")
    assert len(subscriber4_patients) == 0  # No separate patient loop (self-patient)

    # Verify claim ID for subscriber 4
    sub4_claim_ids = {claim.get_segment("CLM").get_element(1) for claim in subscriber4_claims}
    assert "DAVIS_CONSULT" in sub4_claim_ids

def test_claim_count_validation_across_multiple_providers(standalone_schema: ImplementationGuideSchema, multiple_billing_providers_mixed_claims_837p_edi_string: str):
    """Test comprehensive claim counting across multiple billing providers."""
    parser = EdiParser(edi_string=multiple_billing_providers_mixed_claims_837p_edi_string, schema=standalone_schema)
    interchange = parser.parse()
    transaction_body = interchange.functional_groups[0].transactions[0].body

    billing_providers = transaction_body.get_loops("2000A")

    # Count claims per billing provider
    provider1_total_claims = 0
    provider2_total_claims = 0

    # Provider 1 claim counting
    for subscriber in billing_providers[0].get_loops("2000B"):
        provider1_total_claims += len(subscriber.get_loops("2300"))

    # Provider 2 claim counting
    for subscriber in billing_providers[1].get_loops("2000B"):
        provider2_total_claims += len(subscriber.get_loops("2300"))

    # Verify expected totals based on fixture design
    assert provider1_total_claims == 4  # Wilson(2) + Garcia(1+1)
    assert provider2_total_claims == 3  # Thompson(0+2) + Davis(1)

    # Grand total verification
    total_claims = provider1_total_claims + provider2_total_claims
    assert total_claims == 7

def test_service_line_counting_across_mixed_scenarios(standalone_schema: ImplementationGuideSchema, multiple_billing_providers_mixed_claims_837p_edi_string: str):
    """Test service line counting across different claim scenarios."""
    parser = EdiParser(edi_string=multiple_billing_providers_mixed_claims_837p_edi_string, schema=standalone_schema)
    interchange = parser.parse()
    transaction_body = interchange.functional_groups[0].transactions[0].body

    billing_providers = transaction_body.get_loops("2000A")
    total_service_lines = 0

    # Count service lines across all billing providers and subscribers
    for provider in billing_providers:
        for subscriber in provider.get_loops("2000B"):
            for claim in subscriber.get_loops("2300"):
                service_lines = claim.get_loops("2400")
                total_service_lines += len(service_lines)

    # Verify expected total: 8 service lines as documented in fixture
    # Wilson(1+1) + Garcia(1) + Pedro(1) + Emily(1+2) + Davis(1) = 8
    assert total_service_lines == 8

def test_hierarchical_integrity_across_multiple_providers(standalone_schema: ImplementationGuideSchema, multiple_billing_providers_mixed_claims_837p_edi_string: str):
    """Test that hierarchical relationships are maintained across multiple providers."""
    parser = EdiParser(edi_string=multiple_billing_providers_mixed_claims_837p_edi_string, schema=standalone_schema)
    interchange = parser.parse()
    transaction_body = interchange.functional_groups[0].transactions[0].body

    billing_providers = transaction_body.get_loops("2000A")

    # Collect all claim IDs across all providers
    all_claim_ids = set()
    provider_claim_mapping = {}

    for i, provider in enumerate(billing_providers):
        provider_claims = set()
        for subscriber in provider.get_loops("2000B"):
            for claim in subscriber.get_loops("2300"):
                claim_id = claim.get_segment("CLM").get_element(1)
                all_claim_ids.add(claim_id)
                provider_claims.add(claim_id)
        provider_claim_mapping[i] = provider_claims

    # Verify no claim ID overlap between providers
    provider1_claims = provider_claim_mapping[0]
    provider2_claims = provider_claim_mapping[1]
    overlap = provider1_claims.intersection(provider2_claims)
    assert len(overlap) == 0, f"Found overlapping claims between providers: {overlap}"

    # Verify expected claim distribution
    expected_provider1_claims = {"WILSON_OFFICE1", "WILSON_OFFICE2", "GARCIA_SELF", "PEDRO_CHECKUP"}
    expected_provider2_claims = {"EMILY_EXAM1", "EMILY_EXAM2", "DAVIS_CONSULT"}

    assert provider1_claims == expected_provider1_claims
    assert provider2_claims == expected_provider2_claims

    # Verify total unique claims
    assert len(all_claim_ids) == 7

# ==============================================================================
# ERROR HANDLING AND ISOLATION TESTS
# ==============================================================================

def test_parser_continues_processing_despite_transaction_errors(standalone_schema: ImplementationGuideSchema, multiple_transaction_sets_837p_edi_string: str):
    """Test that parser continues processing all transactions even when some contain errors."""
    parser = EdiParser(edi_string=multiple_transaction_sets_837p_edi_string, schema=standalone_schema)
    interchange = parser.parse()

    # Parser should complete processing the entire file
    assert len(interchange.functional_groups) == 1
    functional_group = interchange.functional_groups[0]
    assert len(functional_group.transactions) == 2

    # Both transactions should be structurally accessible
    txn1 = functional_group.transactions[0]
    txn2 = functional_group.transactions[1]

    assert txn1.header.elements[1].value == "0001"
    assert txn2.header.elements[1].value == "0002"

    # Transaction 1 (valid) should have its loops accessible
    assert txn1.body.get_loop("2000A") is not None

    # Transaction 2 (invalid) may not have proper loop structure due to missing required segments
    # but should still be accessible for error analysis

def test_error_isolation_between_transactions(standalone_schema: ImplementationGuideSchema, multiple_transaction_sets_837p_edi_string: str):
    """Test that errors in one transaction don't affect parsing of other transactions."""
    parser = EdiParser(edi_string=multiple_transaction_sets_837p_edi_string, schema=standalone_schema)
    interchange = parser.parse()

    txn1 = interchange.functional_groups[0].transactions[0]
    txn2 = interchange.functional_groups[0].transactions[1]

    # Collect errors for each transaction
    def collect_transaction_errors(transaction):
        errors = list(transaction.errors)

        def collect_loop_errors(loop):
            loop_errors = list(loop.errors)
            for sub_loops in loop.loops.values():
                for sub_loop in sub_loops:
                    loop_errors.extend(collect_loop_errors(sub_loop))
            for segment in loop.segments:
                loop_errors.extend(segment.errors)
            return loop_errors

        errors.extend(collect_loop_errors(transaction.body))
        return errors

    txn1_errors = collect_transaction_errors(txn1)
    txn2_errors = collect_transaction_errors(txn2)

    # Transaction 1 should have no errors (it's valid)
    assert len(txn1_errors) == 0, f"Transaction 1 should be error-free but found: {[e.message for e in txn1_errors]}"

    # Transaction 2 should have errors (we introduced several)
    assert len(txn2_errors) > 0, "Transaction 2 should have validation errors"

    # Verify specific expected errors in transaction 2
    error_messages = [e.message for e in txn2_errors]

    # Should have missing required loop error
    assert any("1000A" in msg and "missing" in msg.lower() for msg in error_messages), "Missing 1000A loop error not found"

    # Should have date length error
    assert any("BHT04" in msg and ("shorter than min length" in msg or "length" in msg) for msg in error_messages), "Date length error not found"

def test_valid_transaction_parsing_despite_errors_in_others(standalone_schema: ImplementationGuideSchema, multiple_transaction_sets_837p_edi_string: str):
    """Test that valid transactions are fully accessible and usable despite errors in other transactions."""
    parser = EdiParser(edi_string=multiple_transaction_sets_837p_edi_string, schema=standalone_schema)
    interchange = parser.parse()

    # Focus on the valid transaction (transaction 1)
    valid_txn = interchange.functional_groups[0].transactions[0]

    # Should be able to access all levels of the hierarchy
    billing_provider = valid_txn.body.get_loop("2000A")
    assert billing_provider is not None

    # Should be able to access billing provider details
    provider_name = billing_provider.get_loop("2010AA").get_segment("NM1").get_element(3)
    assert provider_name == "BILLING PROVIDER 1"

    # Should be able to access subscriber information
    subscribers = billing_provider.get_loops("2000B")
    assert len(subscribers) == 1
    subscriber = subscribers[0]

    subscriber_name = subscriber.get_loop("2010BA").get_segment("NM1").get_element(3)
    assert subscriber_name == "SMITH"

    # Should be able to access claims
    claims = subscriber.get_loops("2300")
    assert len(claims) == 1
    claim = claims[0]

    claim_id = claim.get_segment("CLM").get_element(1)
    assert claim_id == "TXN001_CLAIM1"

    # Should be able to access service lines
    service_lines = claim.get_loops("2400")
    assert len(service_lines) == 1

    service_code = service_lines[0].get_segment("SV1").get_element(1)
    assert service_code == "HC>99213"

def test_comprehensive_error_reporting_across_transactions(standalone_schema: ImplementationGuideSchema, multiple_transaction_sets_837p_edi_string: str):
    """Test that all errors across all transactions are properly collected and reported."""
    parser = EdiParser(edi_string=multiple_transaction_sets_837p_edi_string, schema=standalone_schema)
    interchange = parser.parse()

    # Use the parser's error collection method
    all_errors = parser._collect_all_errors(interchange)

    # Should have errors (from transaction 2)
    assert len(all_errors) > 0, "Should have collected errors from invalid transaction"

    # Group errors by transaction
    errors_by_transaction = {}
    for location, error in all_errors:
        # Extract transaction info from location if available
        if hasattr(location, 'loop_id') and location.loop_id == 'ST_LOOP':
            # This is a transaction-level error
            txn_info = "transaction"
        errors_by_transaction.setdefault("all", []).append((location, error))

    # Verify we have the expected types of errors
    error_messages = [error.message for _, error in all_errors]

    # Should include missing required loop error
    missing_loop_errors = [msg for msg in error_messages if "1000A" in msg and "missing" in msg.lower()]
    assert len(missing_loop_errors) > 0, f"Missing 1000A loop error not found in: {error_messages}"

    # Should include validation errors for invalid data
    validation_errors = [msg for msg in error_messages if any(keyword in msg.lower() for keyword in ["length", "invalid", "code"])]
    assert len(validation_errors) > 0, f"Data validation errors not found in: {error_messages}"

    # Verify that errors don't prevent access to valid data
    valid_txn = interchange.functional_groups[0].transactions[0]
    assert valid_txn.body.get_loop("2000A") is not None, "Valid transaction should still be accessible despite errors in other transactions"

def test_transaction_structural_integrity_with_mixed_errors(standalone_schema: ImplementationGuideSchema, multiple_transaction_sets_837p_edi_string: str):
    """Test that both valid and invalid transactions maintain their structural integrity."""
    parser = EdiParser(edi_string=multiple_transaction_sets_837p_edi_string, schema=standalone_schema)
    interchange = parser.parse()

    transactions = interchange.functional_groups[0].transactions

    # Both transactions should maintain their basic structure
    for i, txn in enumerate(transactions):
        # Each transaction should have a header and trailer
        assert txn.header is not None, f"Transaction {i+1} should have a header"
        assert txn.trailer is not None, f"Transaction {i+1} should have a trailer"

        # Each transaction should have a body
        assert txn.body is not None, f"Transaction {i+1} should have a body"

        # Only valid transactions will have proper loop structure
        if i == 0:  # Transaction 1 is valid
            assert txn.body.get_loop("2000A") is not None, f"Transaction {i+1} should have billing provider loop"
        # Transaction 2 is invalid and may not have proper loop structure due to missing required segments

        # Control numbers should be correct
        expected_control_number = f"000{i+1}"
        actual_control_number = txn.header.get_element(2)
        assert actual_control_number == expected_control_number, f"Transaction {i+1} control number mismatch"

    # Verify claim counts for valid transaction
    txn1_claims = transactions[0].body.get_loop("2000A").get_loops("2000B")[0].get_loops("2300")
    assert len(txn1_claims) == 1, "Transaction 1 should have 1 claim"

    # Transaction 2 doesn't have proper structure due to missing required segments,
    # but we can verify the parser identified the structural errors correctly
