# Quick Start Guide

This guide gets you up and running with the EDI parser in minutes. Follow these steps to parse your first EDI file and access the data.

## Prerequisites

Ensure you have the EDI-Lens backend environment set up:
- Python 3.12+
- Required dependencies installed (`poetry install`)
- Schema files available in `data/edi_schemas/`

## Basic Usage

### 1. **Simple Parse Example**

```python
from src.core.edi_parser import EdiParser
from src.core.schema_manager import SchemaManager

# Load schema
schema_manager = SchemaManager()
schema = schema_manager.get_schema("837.5010.X222.A1")

# Your EDI content
edi_content = """
ISA*00*          *00*          *ZZ*SENDER     *ZZ*RECEIVER   *240715*1200*^*00501*000000001*0*P*>~
GS*HC*SENDER*RECEIVER*20240715*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
BHT*0019*00*BATCH01*20240715*1200*CH~
NM1*41*2*BILLING PROVIDER*****46*SUBMITTER1~
PER*IC*CONTACT PERSON*TE*8005551212~
NM1*40*2*PAYER NAME*****46*RECEIVER1~
HL*1**20*1~
NM1*85*2*PROVIDER NAME*****XX*1234567890~
N3*123 MAIN ST~
N4*ANYTOWN*CA*90210~
REF*EI*123456789~
HL*2*1*22*0~
SBR*P*18*GROUP123******CI~
NM1*IL*1*DOE*JOHN****MI*MEMBER123~
NM1*PR*2*PAYER NAME*****PI*PAYER123~
CLM*CLAIM001*100***11>B>1*Y*A*Y*Y~
DTP*431*D8*20240715~
HI*BK>J021~
LX*1~
SV1*HC>99213*100*UN*1***1**Y~
DTP*472*D8*20240715~
SE*19*0001~
GE*1*1~
IEA*1*000000001~
""".strip()

# Parse the EDI
parser = EdiParser(edi_string=edi_content, schema=schema)
interchange = parser.parse()

# Check for errors
all_errors = parser._collect_all_errors(interchange)
if all_errors:
    print(f"Found {len(all_errors)} errors:")
    for location, error in all_errors:
        print(f"  - {location}: {error.message}")
else:
    print("✅ EDI parsed successfully with no errors!")

# Access the parsed data
transaction = interchange.functional_groups[0].transactions[0]
billing_provider = transaction.body.get_loop("2000A")
provider_name = billing_provider.get_loop("2010AA").get_segment("NM1").get_element(3)
print(f"Billing Provider: {provider_name}")
```

### 2. **Extract Key Information**

```python
def extract_basic_info(interchange):
    """Extract basic information from parsed EDI."""
    info = {
        "interchange_sender": interchange.header.get_element(6),
        "interchange_receiver": interchange.header.get_element(8), 
        "transactions": []
    }
    
    for fg in interchange.functional_groups:
        for txn in fg.transactions:
            txn_info = {
                "transaction_type": txn.header.get_element(1),
                "control_number": txn.header.get_element(2),
                "billing_providers": []
            }
            
            # Extract billing providers
            billing_providers = txn.body.get_loops("2000A")
            for provider in billing_providers:
                provider_loop = provider.get_loop("2010AA")
                if provider_loop:
                    nm1_segment = provider_loop.get_segment("NM1")
                    provider_info = {
                        "name": nm1_segment.get_element(3) if nm1_segment else "Unknown",
                        "id": nm1_segment.get_element(9) if nm1_segment else "Unknown",
                        "subscribers": []
                    }
                    
                    # Extract subscribers
                    subscribers = provider.get_loops("2000B")
                    for subscriber in subscribers:
                        sub_loop = subscriber.get_loop("2010BA")
                        if sub_loop:
                            sub_nm1 = sub_loop.get_segment("NM1")
                            subscriber_info = {
                                "name": f"{sub_nm1.get_element(4)} {sub_nm1.get_element(3)}" if sub_nm1 else "Unknown",
                                "member_id": sub_nm1.get_element(9) if sub_nm1 else "Unknown",
                                "claims_count": len(subscriber.get_loops("2300"))
                            }
                            provider_info["subscribers"].append(subscriber_info)
                    
                    txn_info["billing_providers"].append(provider_info)
            
            info["transactions"].append(txn_info)
    
    return info

# Usage
info = extract_basic_info(interchange)
print(f"Sender: {info['interchange_sender']}")
print(f"Receiver: {info['interchange_receiver']}")
print(f"Transactions: {len(info['transactions'])}")

for txn in info["transactions"]:
    print(f"  Transaction {txn['control_number']} ({txn['transaction_type']}):")
    for provider in txn["billing_providers"]:
        print(f"    Provider: {provider['name']} (ID: {provider['id']})")
        for subscriber in provider["subscribers"]:
            print(f"      Subscriber: {subscriber['name']} ({subscriber['claims_count']} claims)")
```

## Common Use Cases

### 1. **Validate EDI Quality**

```python
def validate_edi_quality(edi_content: str):
    """Validate EDI and provide quality report."""
    try:
        schema_manager = SchemaManager()
        schema = schema_manager.get_schema("837.5010.X222.A1")
        
        parser = EdiParser(edi_string=edi_content, schema=schema)
        interchange = parser.parse()
        
        all_errors = parser._collect_all_errors(interchange)
        critical_errors = [e for _, e in all_errors if e.is_identifier_error]
        
        report = {
            "status": "VALID" if not critical_errors else "INVALID",
            "total_errors": len(all_errors),
            "critical_errors": len(critical_errors),
            "warnings": len(all_errors) - len(critical_errors),
            "can_process": len(critical_errors) == 0,
            "transactions_count": sum(len(fg.transactions) for fg in interchange.functional_groups)
        }
        
        if all_errors:
            report["sample_errors"] = [
                {
                    "location": location,
                    "message": error.message,
                    "critical": error.is_identifier_error
                }
                for location, error in all_errors[:5]  # First 5 errors
            ]
        
        return report
        
    except Exception as e:
        return {
            "status": "ERROR",
            "error": str(e),
            "can_process": False
        }

# Usage
quality_report = validate_edi_quality(edi_content)
print(f"EDI Quality: {quality_report['status']}")
print(f"Errors: {quality_report['total_errors']} total, {quality_report['critical_errors']} critical")
print(f"Can Process: {quality_report['can_process']}")
```

### 2. **Extract All Claims**

```python
def extract_all_claims(interchange):
    """Extract all claims with details from the EDI."""
    claims = []
    
    for fg in interchange.functional_groups:
        for txn in fg.transactions:
            billing_providers = txn.body.get_loops("2000A")
            
            for provider in billing_providers:
                # Get provider info
                provider_info = provider.get_loop("2010AA")
                provider_name = provider_info.get_segment("NM1").get_element(3) if provider_info else "Unknown"
                
                subscribers = provider.get_loops("2000B")
                for subscriber in subscribers:
                    # Get subscriber info
                    sub_info = subscriber.get_loop("2010BA")
                    if sub_info:
                        sub_nm1 = sub_info.get_segment("NM1")
                        subscriber_name = f"{sub_nm1.get_element(4)} {sub_nm1.get_element(3)}" if sub_nm1 else "Unknown"
                        member_id = sub_nm1.get_element(9) if sub_nm1 else "Unknown"
                        
                        # Extract subscriber claims
                        subscriber_claims = subscriber.get_loops("2300")
                        for claim in subscriber_claims:
                            claim_data = extract_claim_data(claim, provider_name, subscriber_name, member_id, "Subscriber")
                            claims.append(claim_data)
                        
                        # Extract patient claims (dependents)
                        patients = subscriber.get_loops("2000C")
                        for patient in patients:
                            # Get patient info
                            patient_nm1 = patient.get_segment("NM1")
                            patient_name = f"{patient_nm1.get_element(4)} {patient_nm1.get_element(3)}" if patient_nm1 else "Unknown Patient"
                            
                            patient_claims = patient.get_loops("2300")
                            for claim in patient_claims:
                                claim_data = extract_claim_data(claim, provider_name, patient_name, member_id, "Patient")
                                claims.append(claim_data)
    
    return claims

def extract_claim_data(claim_loop, provider_name, patient_name, member_id, patient_type):
    """Extract data from a single claim loop."""
    clm_segment = claim_loop.get_segment("CLM")
    
    claim_data = {
        "provider_name": provider_name,
        "patient_name": patient_name,
        "member_id": member_id,
        "patient_type": patient_type,
        "claim_id": clm_segment.get_element(1) if clm_segment else "Unknown",
        "claim_amount": float(clm_segment.get_element(2)) if clm_segment and clm_segment.get_element(2) else 0.0,
        "service_lines": [],
        "diagnoses": []
    }
    
    # Extract service lines
    service_lines = claim_loop.get_loops("2400")
    for service_line in service_lines:
        sv1_segment = service_line.get_segment("SV1")
        if sv1_segment:
            service_data = {
                "procedure_code": sv1_segment.get_element(1),
                "charge_amount": float(sv1_segment.get_element(2)) if sv1_segment.get_element(2) else 0.0,
                "units": sv1_segment.get_element(4) if sv1_segment.get_element(4) else "1"
            }
            claim_data["service_lines"].append(service_data)
    
    # Extract diagnoses
    hi_segments = claim_loop.get_segments("HI")
    for hi_segment in hi_segments:
        diagnosis = hi_segment.get_element(1)
        if diagnosis:
            claim_data["diagnoses"].append(diagnosis)
    
    return claim_data

# Usage
claims = extract_all_claims(interchange)
print(f"Found {len(claims)} total claims")

for claim in claims:
    print(f"Claim {claim['claim_id']}: ${claim['claim_amount']:.2f}")
    print(f"  Provider: {claim['provider_name']}")
    print(f"  Patient: {claim['patient_name']} ({claim['patient_type']})")
    print(f"  Service Lines: {len(claim['service_lines'])}")
    print(f"  Diagnoses: {claim['diagnoses']}")
```

### 3. **Handle Multiple Transactions**

```python
def process_multiple_transactions(edi_content: str):
    """Process EDI with multiple transactions, handling errors gracefully."""
    schema_manager = SchemaManager()
    schema = schema_manager.get_schema("837.5010.X222.A1")
    
    parser = EdiParser(edi_string=edi_content, schema=schema)
    interchange = parser.parse()
    
    results = {
        "total_transactions": 0,
        "successful_transactions": 0,
        "failed_transactions": 0,
        "transaction_results": []
    }
    
    for fg_idx, fg in enumerate(interchange.functional_groups):
        for txn_idx, txn in enumerate(fg.transactions):
            results["total_transactions"] += 1
            
            # Collect errors for this transaction
            txn_errors = []
            
            # Transaction-level errors
            txn_errors.extend([(f"Transaction {txn_idx+1}", error) for error in txn.errors])
            
            # Loop and segment errors
            def collect_loop_errors(loop, context):
                errors = []
                for error in loop.errors:
                    errors.append((context, error))
                for segment in loop.segments:
                    for error in segment.errors:
                        errors.append((f"{context} - {segment.segment_id}", error))
                for loop_type, loop_list in loop.loops.items():
                    for idx, nested_loop in enumerate(loop_list):
                        nested_context = f"{context} - {loop_type}[{idx}]"
                        errors.extend(collect_loop_errors(nested_loop, nested_context))
                return errors
            
            txn_errors.extend(collect_loop_errors(txn.body, f"Transaction {txn_idx+1}"))
            
            # Check if transaction is processable
            critical_errors = [e for _, e in txn_errors if e.is_identifier_error]
            is_processable = len(critical_errors) == 0
            
            txn_result = {
                "transaction_id": txn.header.get_element(2),
                "control_number": txn.header.get_element(2),
                "is_processable": is_processable,
                "total_errors": len(txn_errors),
                "critical_errors": len(critical_errors),
                "data": None
            }
            
            if is_processable:
                results["successful_transactions"] += 1
                # Extract data from successful transaction
                try:
                    txn_result["data"] = extract_transaction_summary(txn)
                except Exception as e:
                    txn_result["data_extraction_error"] = str(e)
            else:
                results["failed_transactions"] += 1
                txn_result["error_summary"] = [
                    {"location": loc, "message": err.message} 
                    for loc, err in critical_errors[:3]  # First 3 critical errors
                ]
            
            results["transaction_results"].append(txn_result)
    
    return results

def extract_transaction_summary(transaction):
    """Extract summary data from a transaction."""
    summary = {
        "billing_providers": 0,
        "subscribers": 0,
        "patients": 0,
        "claims": 0,
        "total_amount": 0.0
    }
    
    billing_providers = transaction.body.get_loops("2000A")
    summary["billing_providers"] = len(billing_providers)
    
    for provider in billing_providers:
        subscribers = provider.get_loops("2000B")
        summary["subscribers"] += len(subscribers)
        
        for subscriber in subscribers:
            # Count subscriber claims
            subscriber_claims = subscriber.get_loops("2300")
            summary["claims"] += len(subscriber_claims)
            
            for claim in subscriber_claims:
                clm_segment = claim.get_segment("CLM")
                if clm_segment and clm_segment.get_element(2):
                    try:
                        amount = float(clm_segment.get_element(2))
                        summary["total_amount"] += amount
                    except ValueError:
                        pass
            
            # Count patient claims
            patients = subscriber.get_loops("2000C")
            summary["patients"] += len(patients)
            
            for patient in patients:
                patient_claims = patient.get_loops("2300")
                summary["claims"] += len(patient_claims)
                
                for claim in patient_claims:
                    clm_segment = claim.get_segment("CLM")
                    if clm_segment and clm_segment.get_element(2):
                        try:
                            amount = float(clm_segment.get_element(2))
                            summary["total_amount"] += amount
                        except ValueError:
                            pass
    
    return summary

# Usage
results = process_multiple_transactions(edi_content)
print(f"Processed {results['total_transactions']} transactions")
print(f"Successful: {results['successful_transactions']}")
print(f"Failed: {results['failed_transactions']}")

for result in results["transaction_results"]:
    status = "✅" if result["is_processable"] else "❌"
    print(f"{status} Transaction {result['control_number']}: {result['total_errors']} errors")
    if result["data"]:
        data = result["data"]
        print(f"   {data['claims']} claims, ${data['total_amount']:.2f} total")
```

## Error Handling Tips

### Quick Error Check
```python
# Quick way to check if EDI is processable
def is_edi_processable(edi_content: str) -> bool:
    try:
        schema_manager = SchemaManager()
        schema = schema_manager.get_schema("837.5010.X222.A1")
        parser = EdiParser(edi_string=edi_content, schema=schema)
        interchange = parser.parse()
        
        all_errors = parser._collect_all_errors(interchange)
        critical_errors = [e for _, e in all_errors if e.is_identifier_error]
        
        return len(critical_errors) == 0
    except:
        return False
```

### Safe Data Access
```python
def safe_get_element(segment, position, default=""):
    """Safely get element value with fallback."""
    if not segment:
        return default
    value = segment.get_element(position)
    return value if value else default

def safe_get_nested_segment(root_loop, *path):
    """Safely navigate nested loop structure."""
    current = root_loop
    for step in path:
        if not current:
            return None
        if isinstance(step, str) and step.startswith("loop:"):
            loop_id = step[5:]  # Remove "loop:" prefix
            current = current.get_loop(loop_id)
        elif isinstance(step, str) and step.startswith("segment:"):
            segment_id = step[8:]  # Remove "segment:" prefix
            current = current.get_segment(segment_id)
        else:
            current = None
    return current

# Usage
clm_segment = safe_get_nested_segment(
    transaction.body, 
    "loop:2000A", 
    "loop:2000B", 
    "loop:2300", 
    "segment:CLM"
)
claim_amount = safe_get_element(clm_segment, 2, "0.00")
```

## Next Steps

- **[Usage Examples](./06-usage-examples.md)**: More detailed examples and use cases
- **[Error Handling](./04-error-handling.md)**: Comprehensive error handling strategies
- **[Data Structures](./03-data-structures.md)**: Deep dive into the CDM structure
- **[API Reference](./12-api-reference.md)**: Complete API documentation