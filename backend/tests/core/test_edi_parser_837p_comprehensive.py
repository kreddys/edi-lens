# FILE: backend/tests/core/test_edi_parser_837p_comprehensive.py
import pytest
from src.core.edi_parser import EdiParser
from src.edi_schemas.edi_guide import ImplementationGuideSchema

pytestmark = pytest.mark.unit

# ==============================================================================
# COMPREHENSIVE 837P STRUCTURE TESTS
# Tests covering all possible 837P scenarios and edge cases
# ==============================================================================

def test_multiple_transaction_sets_parsing(standalone_schema: ImplementationGuideSchema, multiple_transaction_sets_837p_edi_string: str):
    """
    Tests parsing of multiple transaction sets (ST-SE blocks) within a single functional group.
    Validates that each transaction set is parsed independently and correctly.
    """
    parser = EdiParser(edi_string=multiple_transaction_sets_837p_edi_string, schema=standalone_schema)
    interchange = parser.parse()
    
    # Verify overall structure
    assert len(interchange.functional_groups) == 1
    functional_group = interchange.functional_groups[0]
    assert len(functional_group.transactions) == 2
    
    # Verify first transaction set
    txn1 = functional_group.transactions[0]
    assert txn1.header.elements[1].value == "0001"  # ST02
    billing_providers_txn1 = txn1.body.get_loops("2000A")
    assert len(billing_providers_txn1) == 1
    subscribers_txn1 = billing_providers_txn1[0].get_loops("2000B")
    assert len(subscribers_txn1) == 1
    claims_txn1 = subscribers_txn1[0].get_loops("2300")
    assert len(claims_txn1) == 1
    assert claims_txn1[0].get_segment("CLM").elements[0].value == "TXN001_CLAIM1"
    
    # Verify second transaction set
    txn2 = functional_group.transactions[1]
    assert txn2.header.elements[1].value == "0002"  # ST02
    billing_providers_txn2 = txn2.body.get_loops("2000A")
    assert len(billing_providers_txn2) == 1
    subscribers_txn2 = billing_providers_txn2[0].get_loops("2000B")
    assert len(subscribers_txn2) == 1
    claims_txn2 = subscribers_txn2[0].get_loops("2300")
    assert len(claims_txn2) == 2  # Second transaction has 2 claims
    assert claims_txn2[0].get_segment("CLM").elements[0].value == "TXN002_CLAIM1"
    assert claims_txn2[1].get_segment("CLM").elements[0].value == "TXN002_CLAIM2"

def test_multiple_functional_groups_parsing(standalone_schema: ImplementationGuideSchema, multiple_functional_groups_837p_edi_string: str):
    """
    Tests parsing of multiple functional groups (GS-GE blocks) within a single interchange.
    Validates that each functional group maintains its own context and data.
    """
    parser = EdiParser(edi_string=multiple_functional_groups_837p_edi_string, schema=standalone_schema)
    interchange = parser.parse()
    
    # Verify overall structure
    assert len(interchange.functional_groups) == 2
    
    # Verify first functional group
    group1 = interchange.functional_groups[0]
    assert group1.header.elements[1].value == "SENDER1"  # GS02
    assert group1.header.elements[2].value == "RECEIVER1"  # GS03
    assert len(group1.transactions) == 1
    txn1 = group1.transactions[0]
    billing_provider1 = txn1.body.get_loop("2000A")
    assert billing_provider1.get_loop("2010AA").get_segment("NM1").elements[2].value == "CLINIC A"
    
    # Verify second functional group
    group2 = interchange.functional_groups[1]
    assert group2.header.elements[1].value == "SENDER2"  # GS02
    assert group2.header.elements[2].value == "RECEIVER2"  # GS03
    assert len(group2.transactions) == 1
    txn2 = group2.transactions[0]
    billing_provider2 = txn2.body.get_loop("2000A")
    assert billing_provider2.get_loop("2010AA").get_segment("NM1").elements[2].value == "CLINIC B"
    
    # Verify IEA count reflects multiple functional groups
    assert interchange.trailer.elements[0].value == "2"  # IEA01 should be 2

def test_multiple_claims_per_subscriber_parsing(standalone_schema: ImplementationGuideSchema, multiple_claims_per_subscriber_837p_edi_string: str):
    """
    Tests parsing of multiple claims for a single subscriber.
    Validates that all claims are properly parsed and associated with the correct subscriber.
    """
    parser = EdiParser(edi_string=multiple_claims_per_subscriber_837p_edi_string, schema=standalone_schema)
    interchange = parser.parse()
    
    transaction = interchange.functional_groups[0].transactions[0]
    billing_provider = transaction.body.get_loop("2000A")
    subscriber = billing_provider.get_loop("2000B")
    claims = subscriber.get_loops("2300")
    
    # Verify 4 claims for single subscriber
    assert len(claims) == 4
    
    # Verify claim details
    expected_claims = [
        ("ANDERSON_VISIT1", "20240701", 1),  # (claim_id, service_date, service_line_count)
        ("ANDERSON_VISIT2", "20240708", 3),
        ("ANDERSON_VISIT3", "20240715", 2),
        ("ANDERSON_VISIT4", "20240722", 1)
    ]
    
    for i, (expected_claim_id, expected_date, expected_lines) in enumerate(expected_claims):
        claim = claims[i]
        assert claim.get_segment("CLM").elements[0].value == expected_claim_id
        assert claim.get_segment("DTP").elements[2].value == expected_date
        service_lines = claim.get_loops("2400")
        assert len(service_lines) == expected_lines


def test_subscriber_vs_patient_scenarios(standalone_schema: ImplementationGuideSchema, subscriber_vs_patient_837p_edi_string: str):
    """
    Tests parsing of both subscriber-as-patient and dependent patient scenarios.
    Validates proper handling of HL03=22 (subscriber) vs HL03=23 (dependent) hierarchies.
    """
    parser = EdiParser(edi_string=subscriber_vs_patient_837p_edi_string, schema=standalone_schema)
    interchange = parser.parse()
    
    transaction = interchange.functional_groups[0].transactions[0]
    billing_provider = transaction.body.get_loop("2000A")
    subscribers = billing_provider.get_loops("2000B")
    
    # Verify 2 subscribers
    assert len(subscribers) == 2
    
    # Verify first subscriber (self-insured, HL03=22, HL04=0)
    subscriber1 = subscribers[0]
    hl1_segment = subscriber1.get_segment("HL")
    assert hl1_segment.elements[2].value == "22"  # HL03 = subscriber
    assert hl1_segment.elements[3].value == "0"   # HL04 = no dependents
    
    subscriber1_claims = subscriber1.get_loops("2300")
    assert len(subscriber1_claims) == 1
    assert subscriber1_claims[0].get_segment("CLM").elements[0].value == "SELF_CLAIM1"
    
    # Verify second subscriber (has dependent, HL03=22, HL04=1)
    subscriber2 = subscribers[1]
    hl2_segment = subscriber2.get_segment("HL")
    assert hl2_segment.elements[2].value == "22"  # HL03 = subscriber
    assert hl2_segment.elements[3].value == "1"   # HL04 = has dependents
    
    subscriber2_claims = subscriber2.get_loops("2300")
    assert len(subscriber2_claims) == 1
    assert subscriber2_claims[0].get_segment("CLM").elements[0].value == "SUB_CLAIM1"
    
    # Verify dependent patient (HL03=23)
    dependent_patients = subscriber2.get_loops("2000C")
    assert len(dependent_patients) == 1
    dependent = dependent_patients[0]
    hl_dependent_segment = dependent.get_segment("HL")
    assert hl_dependent_segment.elements[2].value == "23"  # HL03 = dependent patient
    assert hl_dependent_segment.elements[3].value == "0"   # HL04 = no further dependents
    
    # Verify dependent has PAT segment
    assert dependent.get_segment("PAT") is not None
    dependent_claims = dependent.get_loops("2300")
    assert len(dependent_claims) == 1
    assert dependent_claims[0].get_segment("CLM").elements[0].value == "DEP_CLAIM1"

# ==============================================================================
# COMPREHENSIVE VALIDATION TESTS
# Tests that ensure all scenarios validate correctly against the schema
# ==============================================================================

def test_all_comprehensive_fixtures_parse_without_errors(standalone_schema: ImplementationGuideSchema, 
                                                        multiple_transaction_sets_837p_edi_string: str,
                                                        multiple_functional_groups_837p_edi_string: str,
                                                        multiple_claims_per_subscriber_837p_edi_string: str,
                                                        subscriber_vs_patient_837p_edi_string: str):
    """
    Tests that all comprehensive test fixtures parse without structural or validation errors.
    This is a critical test to ensure all our complex scenarios are schema-compliant.
    """
    fixtures = [
        ("multiple_transaction_sets", multiple_transaction_sets_837p_edi_string),
        ("multiple_functional_groups", multiple_functional_groups_837p_edi_string),
        ("multiple_claims_per_subscriber", multiple_claims_per_subscriber_837p_edi_string),
        ("subscriber_vs_patient", subscriber_vs_patient_837p_edi_string)
    ]
    
    def collect_all_errors(loop):
        errors = list(loop.errors)
        for sub_loops in loop.loops.values():
            for sub_loop in sub_loops:
                errors.extend(collect_all_errors(sub_loop))
        for segment in loop.segments:
            errors.extend(segment.errors)
        return errors
    
    for fixture_name, edi_string in fixtures:
        parser = EdiParser(edi_string=edi_string, schema=standalone_schema)
        interchange = parser.parse()
        
        # Collect all errors from the entire interchange
        all_errors = []
        for error in interchange.errors:
            all_errors.append(error)
        
        for group in interchange.functional_groups:
            for error in group.errors:
                all_errors.append(error)
            for transaction in group.transactions:
                for error in transaction.errors:
                    all_errors.append(error)
                all_errors.extend(collect_all_errors(transaction.body))
        
        assert len(all_errors) == 0, f"Fixture '{fixture_name}' has validation errors: {[e.message for e in all_errors]}"

# ==============================================================================
# DATA EXTRACTION AND ACCESS TESTS
# Tests that verify correct data can be extracted from complex structures
# ==============================================================================

def test_data_extraction_from_multiple_transaction_sets(standalone_schema: ImplementationGuideSchema, multiple_transaction_sets_837p_edi_string: str):
    """
    Tests extracting specific data elements from multiple transaction sets.
    Validates that data can be accessed correctly across different transactions.
    """
    parser = EdiParser(edi_string=multiple_transaction_sets_837p_edi_string, schema=standalone_schema)
    interchange = parser.parse()
    
    # Extract data from both transaction sets
    transactions = interchange.functional_groups[0].transactions
    
    # Extract billing provider names from both transactions
    billing_names = []
    for txn in transactions:
        provider_loop = txn.body.get_loop("2000A")
        provider_name_loop = provider_loop.get_loop("2010AA")
        provider_name = provider_name_loop.get_segment("NM1").elements[2].value
        billing_names.append(provider_name)
    
    assert billing_names == ["BILLING PROVIDER 1", "BILLING PROVIDER 2"]
    
    # Extract total claim amounts across all transactions
    total_amounts = []
    for txn in transactions:
        provider_loop = txn.body.get_loop("2000A")
        subscriber_loop = provider_loop.get_loop("2000B")
        claims = subscriber_loop.get_loops("2300")
        for claim in claims:
            amount = claim.get_segment("CLM").elements[1].value
            total_amounts.append(float(amount))
    
    expected_amounts = [300.0, 450.0, 175.0]  # From the fixture
    assert total_amounts == expected_amounts


# ==============================================================================
# EDGE CASE AND BOUNDARY TESTS
# Tests that verify parser handles edge cases and boundary conditions
# ==============================================================================

def test_maximum_claims_per_subscriber_boundary(standalone_schema: ImplementationGuideSchema, multiple_claims_per_subscriber_837p_edi_string: str):
    """
    Tests that the parser can handle multiple claims per subscriber without performance issues.
    This fixture has 4 claims with varying service line counts (7 total service lines).
    """
    parser = EdiParser(edi_string=multiple_claims_per_subscriber_837p_edi_string, schema=standalone_schema)
    interchange = parser.parse()
    
    transaction = interchange.functional_groups[0].transactions[0]
    billing_provider = transaction.body.get_loop("2000A")
    subscriber = billing_provider.get_loop("2000B")
    claims = subscriber.get_loops("2300")
    
    # Count total service lines across all claims
    total_service_lines = 0
    for claim in claims:
        service_lines = claim.get_loops("2400")
        total_service_lines += len(service_lines)
    
    assert total_service_lines == 7
    
    # Verify service line numbering (LX segments)
    for claim in claims:
        service_lines = claim.get_loops("2400")
        for i, service_line in enumerate(service_lines, 1):
            lx_segment = service_line.get_segment("LX")
            assert lx_segment.elements[0].value == str(i)

def test_hierarchical_level_sequencing(standalone_schema: ImplementationGuideSchema, subscriber_vs_patient_837p_edi_string: str):
    """
    Tests that HL (Hierarchical Level) segments maintain proper sequencing across subscriber/patient scenarios.
    """
    parser = EdiParser(edi_string=subscriber_vs_patient_837p_edi_string, schema=standalone_schema)
    interchange = parser.parse()
    
    transaction = interchange.functional_groups[0].transactions[0]
    
    # Extract all HL segments in order
    hl_segments = []
    
    def extract_hl_segments(loop):
        for segment in loop.segments:
            if segment.segment_id == "HL":
                hl_segments.append({
                    'hl01': segment.elements[0].value,  # HL number
                    'hl02': segment.elements[1].value if len(segment.elements) > 1 and segment.elements[1].value else None,  # Parent HL
                    'hl03': segment.elements[2].value,  # HL level code
                    'hl04': segment.elements[3].value if len(segment.elements) > 3 else None   # Child code
                })
        
        for sub_loops in loop.loops.values():
            for sub_loop in sub_loops:
                extract_hl_segments(sub_loop)
    
    extract_hl_segments(transaction.body)
    
    # Verify HL sequence for subscriber vs patient scenario
    expected_sequence = [
        {'hl01': '1', 'hl02': None, 'hl03': '20', 'hl04': '1'},      # Billing provider
        {'hl01': '2', 'hl02': '1', 'hl03': '22', 'hl04': '0'},       # First subscriber (no dependents)
        {'hl01': '3', 'hl02': '1', 'hl03': '22', 'hl04': '1'},       # Second subscriber (has dependents)
        {'hl01': '4', 'hl02': '3', 'hl03': '23', 'hl04': '0'},       # Dependent patient
    ]
    
    assert hl_segments == expected_sequence