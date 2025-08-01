# Data Structures

The EDI parser uses a **Canonical Data Model (CDM)** to represent parsed EDI data in a consistent, hierarchical, and type-safe format. This document details all data structures and their relationships.

## CDM Hierarchy Overview

```
CdmInterchange                    # ISA-IEA Envelope
├── header: CdmSegment           # ISA segment
├── trailer: CdmSegment          # IEA segment  
├── functional_groups: []        # List of functional groups
│   └── CdmFunctionalGroup       # GS-GE Envelope
│       ├── header: CdmSegment   # GS segment
│       ├── trailer: CdmSegment  # GE segment
│       └── transactions: []     # List of transactions
│           └── CdmTransaction   # ST-SE Transaction
│               ├── header: CdmSegment    # ST segment
│               ├── trailer: CdmSegment   # SE segment
│               └── body: CdmLoop         # Transaction body
│                   ├── segments: []     # Direct segments
│                   └── loops: {}        # Nested loops
│                       └── CdmLoop      # Hierarchical loops
└── errors: []                   # Validation errors
```

## Core Data Models

### 1. **CdmValidationError**

Represents a validation error found during parsing with full context information.

```python
class CdmValidationError(BaseModel):
    message: str                    # Human-readable error description
    line_number: Optional[int]      # Line number in original EDI (1-based)
    segment_id: Optional[str]       # Segment ID where error occurred
    element_xid: Optional[str]      # Element identifier (e.g., "BHT04")
    is_identifier_error: bool       # Whether error affects key identifiers
```

**Examples:**
```python
# Element validation error
CdmValidationError(
    message="Element 'BHT04': Value is shorter than min length 8.",
    line_number=25,
    segment_id="BHT",
    element_xid="BHT04",
    is_identifier_error=False
)

# Missing required loop error  
CdmValidationError(
    message="Required segment or loop '1000A' (SUBMITTER NAME) is missing from loop 'ST_LOOP'.",
    line_number=None,
    segment_id=None,
    element_xid=None,
    is_identifier_error=False
)
```

### 2. **CdmElement**

Represents a single data element within a segment.

```python
class CdmElement(BaseModel):
    value: str      # Element value (may be empty string)
    position: int   # 1-based position within segment
```

**Example:**
```python
# From segment: NM1*85*2*BILLING PROVIDER*****XX*1234567890
CdmElement(value="85", position=1)      # Entity identifier code
CdmElement(value="2", position=2)       # Entity type qualifier  
CdmElement(value="BILLING PROVIDER", position=3)  # Name
CdmElement(value="", position=4)        # Empty first name
CdmElement(value="XX", position=8)      # ID code qualifier
CdmElement(value="1234567890", position=9)  # ID code
```

### 3. **CdmSegment**

Represents a single EDI segment with its elements and validation errors.

```python
class CdmSegment(BaseModel):
    segment_id: str                         # Segment identifier (e.g., "NM1")
    elements: List[CdmElement]              # List of elements in order
    line_number: int                        # Line number in original EDI
    raw_segment: str                        # Original segment string
    errors: List[CdmValidationError]        # Validation errors for this segment
    
    def get_element(self, position: int) -> Optional[str]:
        """Get element value by 1-based position."""
```

**Usage Examples:**
```python
# Access element values
segment.get_element(1)          # Returns "85"
segment.get_element(3)          # Returns "BILLING PROVIDER"
segment.get_element(10)         # Returns None (doesn't exist)

# Check for errors
if segment.errors:
    print(f"Segment {segment.segment_id} has {len(segment.errors)} errors")
    
# Access raw data for debugging
print(f"Original segment: {segment.raw_segment}")
print(f"Found on line: {segment.line_number}")
```

### 4. **CdmLoop**

Represents a hierarchical loop within a transaction, containing segments and nested loops.

```python
class CdmLoop(BaseModel):
    loop_id: str                            # Loop identifier (e.g., "2000A", "2300")
    segments: List[CdmSegment]              # Direct child segments
    loops: Dict[str, List[CdmLoop]]         # Nested child loops by type
    errors: List[CdmValidationError]        # Validation errors for this loop
    
    # Navigation methods
    def add_loop(self, loop: CdmLoop)
    def get_segment(self, segment_id: str) -> Optional[CdmSegment]
    def get_segments(self, segment_id: str) -> List[CdmSegment]
    def get_loop(self, loop_id: str) -> Optional[CdmLoop]
    def get_loops(self, loop_id: str) -> List[CdmLoop]
```

**Loop Hierarchy Examples:**

**837P Transaction Structure:**
```python
# Transaction body is the root loop
transaction.body.loop_id == "ST_LOOP"

# Billing provider loop
billing_provider = transaction.body.get_loop("2000A")
billing_provider.loop_id == "2000A"

# Multiple subscribers under billing provider
subscribers = billing_provider.get_loops("2000B") 
# Returns list: [subscriber1, subscriber2, ...]

# Claims under subscriber
claims = subscribers[0].get_loops("2300")
# Returns list: [claim1, claim2, ...]

# Service lines under claim  
service_lines = claims[0].get_loops("2400")
# Returns list: [service1, service2, ...]
```

**Navigation Examples:**
```python
# Direct segment access
clm_segment = claim_loop.get_segment("CLM")
claim_id = clm_segment.get_element(1)
claim_amount = clm_segment.get_element(2)

# Multiple segments of same type
all_hi_segments = claim_loop.get_segments("HI")  # Health info segments

# Check if optional loop exists
pay_to_loop = billing_provider.get_loop("2010AB")  # May return None
if pay_to_loop:
    # Process pay-to provider information
    pass
```

### 5. **CdmTransaction**

Represents a complete transaction set (ST-SE block).

```python
class CdmTransaction(BaseModel):
    header: CdmSegment              # ST segment
    trailer: CdmSegment             # SE segment  
    body: CdmLoop                   # Transaction body loop (ST_LOOP)
    errors: List[CdmValidationError] # Transaction-level errors
```

**Usage Examples:**
```python
# Access transaction info
transaction_type = transaction.header.get_element(1)    # "837"
control_number = transaction.header.get_element(2)      # "0001"
version = transaction.header.get_element(3)             # "005010X222A1"

# Verify transaction integrity
segment_count = int(transaction.trailer.get_element(1))
expected_count = len(all_segments_in_transaction) + 2   # +2 for ST/SE
assert segment_count == expected_count

# Access transaction data
billing_provider = transaction.body.get_loop("2000A")
```

### 6. **CdmFunctionalGroup**

Represents a functional group (GS-GE block) containing related transactions.

```python
class CdmFunctionalGroup(BaseModel):
    header: CdmSegment              # GS segment
    trailer: CdmSegment             # GE segment
    transactions: List[CdmTransaction]  # List of transactions
    errors: List[CdmValidationError]    # Functional group errors
```

**Usage Examples:**
```python
# Access functional group info
functional_id = fg.header.get_element(1)        # "HC" (Healthcare)
sender_code = fg.header.get_element(2)          # Application sender code
receiver_code = fg.header.get_element(3)        # Application receiver code
group_date = fg.header.get_element(4)           # CCYYMMDD
group_time = fg.header.get_element(5)           # HHMM

# Process all transactions
for transaction in fg.transactions:
    if transaction.header.get_element(1) == "837":
        # Process 837 claim transaction
        process_claim_transaction(transaction)
```

### 7. **CdmInterchange**

Represents the complete EDI interchange (ISA-IEA envelope).

```python
class CdmInterchange(BaseModel):
    header: CdmSegment                      # ISA segment
    trailer: CdmSegment                     # IEA segment
    functional_groups: List[CdmFunctionalGroup]  # List of functional groups
    errors: List[CdmValidationError]        # Interchange-level errors
```

**Usage Examples:**
```python
# Access interchange info
sender_id = interchange.header.get_element(6)       # Sender ID
receiver_id = interchange.header.get_element(8)     # Receiver ID
control_number = interchange.header.get_element(13) # Control number
test_indicator = interchange.header.get_element(15) # P=Production, T=Test

# Process all functional groups and transactions
for fg in interchange.functional_groups:
    for transaction in fg.transactions:
        # Process each transaction
        process_transaction(transaction)
```

## Data Access Patterns

### 1. **Hierarchical Navigation**

```python
# Top-down navigation
interchange = parser.parse()
functional_group = interchange.functional_groups[0]
transaction = functional_group.transactions[0]
billing_provider = transaction.body.get_loop("2000A")
subscribers = billing_provider.get_loops("2000B")
claims = subscribers[0].get_loops("2300")
service_lines = claims[0].get_loops("2400")

# Direct access with error handling
def get_provider_name(transaction):
    billing_provider = transaction.body.get_loop("2000A")
    if not billing_provider:
        return None
        
    provider_info = billing_provider.get_loop("2010AA")
    if not provider_info:
        return None
        
    nm1_segment = provider_info.get_segment("NM1")
    if not nm1_segment:
        return None
        
    return nm1_segment.get_element(3)  # Organization name
```

### 2. **Error-Safe Access**

```python
def safe_get_element(segment, position, default=None):
    """Safely get element value with default."""
    if not segment:
        return default
    value = segment.get_element(position)
    return value if value else default

def safe_get_loop_segment(loop, loop_id, segment_id):
    """Safely navigate to nested segment."""
    if not loop:
        return None
    child_loop = loop.get_loop(loop_id)
    if not child_loop:
        return None
    return child_loop.get_segment(segment_id)

# Usage
provider_name = safe_get_element(
    safe_get_loop_segment(transaction.body, "2000A", "2010AA", "NM1"),
    3,
    "Unknown Provider"
)
```

### 3. **Batch Processing**

```python
def extract_all_claims(interchange):
    """Extract all claims from all transactions in interchange."""
    claims = []
    
    for fg in interchange.functional_groups:
        for transaction in fg.transactions:
            billing_providers = transaction.body.get_loops("2000A")
            for provider in billing_providers:
                subscribers = provider.get_loops("2000B")
                for subscriber in subscribers:
                    subscriber_claims = subscriber.get_loops("2300")
                    claims.extend(subscriber_claims)
                    
                    # Also check for patient-level claims
                    patients = subscriber.get_loops("2000C")
                    for patient in patients:
                        patient_claims = patient.get_loops("2300")
                        claims.extend(patient_claims)
    
    return claims
```

## Error Handling in Data Structures

### Error Propagation

Errors are attached to the most specific applicable level:

```python
# Element-level error (attached to segment)
segment.errors = [
    CdmValidationError(
        message="Element 'NM103': Value exceeds max length 60.",
        element_xid="NM103"
    )
]

# Segment-level error (attached to loop)
loop.errors = [
    CdmValidationError(
        message="Required segment 'REF' is missing from loop '2010AA'."
    )
]

# Loop-level error (attached to parent loop/transaction)
transaction.errors = [
    CdmValidationError(
        message="Required loop '1000A' is missing from transaction."
    )
]
```

### Error Collection

```python
def collect_all_errors(cdm_object):
    """Recursively collect all errors from CDM hierarchy."""
    errors = []
    
    # Add direct errors
    if hasattr(cdm_object, 'errors'):
        errors.extend([(cdm_object, error) for error in cdm_object.errors])
    
    # Recursively collect from children
    if isinstance(cdm_object, CdmInterchange):
        for fg in cdm_object.functional_groups:
            errors.extend(collect_all_errors(fg))
            
    elif isinstance(cdm_object, CdmFunctionalGroup):
        for txn in cdm_object.transactions:
            errors.extend(collect_all_errors(txn))
            
    elif isinstance(cdm_object, CdmTransaction):
        errors.extend(collect_all_errors(cdm_object.body))
        
    elif isinstance(cdm_object, CdmLoop):
        for segment in cdm_object.segments:
            errors.extend(collect_all_errors(segment))
        for loop_list in cdm_object.loops.values():
            for loop in loop_list:
                errors.extend(collect_all_errors(loop))
    
    return errors
```

## Performance Considerations

### Memory Usage

- **Lazy Loading**: Loops created only when accessed
- **Reference Sharing**: Schema objects shared across instances
- **String Interning**: Common values like segment IDs are interned

### Access Patterns

- **Dictionary Lookups**: Loop access is O(1) via dictionary keys
- **List Operations**: Segment access within loops is O(n) but typically small
- **Caching**: Frequently accessed paths can be cached at application level

## Next Steps

- **[Error Handling](./04-error-handling.md)**: Comprehensive error handling strategies
- **[Usage Examples](./06-usage-examples.md)**: Practical data access examples  
- **[API Reference](./12-api-reference.md)**: Complete method documentation