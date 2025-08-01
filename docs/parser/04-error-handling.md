# Error Handling & Validation

The EDI parser implements comprehensive error handling and validation designed to be **fault-tolerant** while providing detailed diagnostics. This document covers the error handling philosophy, validation types, error recovery strategies, and best practices.

## Error Handling Philosophy

### Continue-on-Error Strategy

The parser follows a **"Parse First, Validate Second"** approach:

1. **Structural Parsing**: Always attempts to parse the EDI structure, even with errors
2. **Error Collection**: Collects validation errors without halting processing
3. **Graceful Degradation**: Valid portions remain accessible despite errors elsewhere
4. **Comprehensive Reporting**: All errors reported with full context

**Benefits:**
- **Maximum Data Recovery**: Extract valid data even from partially corrupted files
- **Production Ready**: Handles real-world EDI with minor formatting issues
- **Detailed Diagnostics**: Comprehensive error reporting for data quality assessment
- **Transaction Isolation**: Errors in one transaction don't affect others

## Error Classification

### 1. **Structural Errors**

Errors in the fundamental EDI structure that prevent proper parsing.

**Types:**
- **Missing Required Loops**: Required loops like 1000A (Submitter) missing
- **Invalid Loop Hierarchy**: HL segments with invalid parent relationships
- **Malformed Segments**: Segments that can't be parsed due to format issues
- **Incomplete Transactions**: ST without matching SE, or truncated data

**Examples:**
```python
CdmValidationError(
    message="Required segment or loop '1000A' (SUBMITTER NAME) is missing from loop 'ST_LOOP'.",
    line_number=None,
    segment_id=None,
    element_xid=None,
    is_identifier_error=False
)

CdmValidationError(
    message="Transaction parsing incomplete. Could not process 26 remaining segments starting with 'PER'.",
    line_number=26,
    segment_id="PER",
    element_xid=None,
    is_identifier_error=False
)
```

### 2. **Data Validation Errors**

Errors in element values that violate schema constraints.

**Element-Level Validation:**
- **Length Errors**: Values too short or too long
- **Format Errors**: Values don't match expected format (e.g., dates, times)
- **Data Type Errors**: Values don't match expected data type (numeric, alphanumeric)
- **Code Set Errors**: Values not in allowable code sets

**Examples:**
```python
# Length validation error
CdmValidationError(
    message="Element 'BHT04': Value is shorter than min length 8.",
    line_number=25,
    segment_id="BHT",
    element_xid="BHT04",
    is_identifier_error=False
)

# Format validation error  
CdmValidationError(
    message="Element 'BHT04': Value does not match expected format 'CCYYMMDD'.",
    line_number=25,
    segment_id="BHT",
    element_xid="BHT04",
    is_identifier_error=False
)

# Code set validation error
CdmValidationError(
    message="Element 'SBR09': Value 'ZZ' is not in the allowable code set.",
    line_number=31,
    segment_id="SBR",
    element_xid="SBR09",
    is_identifier_error=True
)
```

### 3. **Business Rule Errors**

Errors in complex validation rules and syntax rules defined in the implementation guide.

**Syntax Rule Types:**
- **Conditional Requirements**: If element A is present, element B is required
- **Mutual Exclusivity**: Only one of several elements can be present
- **Value Dependencies**: Element B's value depends on element A's value
- **Cross-Segment Rules**: Rules spanning multiple segments or loops

**Examples:**
```python
# Conditional requirement rule
CdmValidationError(
    message="Syntax Rule P0102: If NM108 is present, then NM109 is required.",
    line_number=32,
    segment_id="NM1",
    element_xid="NM109",
    is_identifier_error=False
)

# Mutual exclusivity rule
CdmValidationError(
    message="Syntax Rule E0204: Only one of NM108 or NM109 may be present.",
    line_number=32,
    segment_id="NM1",
    element_xid="NM108",
    is_identifier_error=False
)
```

### 4. **Warning-Level Issues**

Non-critical issues that don't prevent processing but may indicate data quality problems.

**Types:**
- **Optional Data Missing**: Recommended but not required data absent
- **Unusual Values**: Values that are technically valid but uncommon
- **Deprecated Codes**: Valid codes that are deprecated or obsolete

## Error Context and Metadata

Each error includes comprehensive context for debugging and resolution:

```python
class CdmValidationError(BaseModel):
    message: str                    # Human-readable error description
    line_number: Optional[int]      # Line number in original EDI (1-based)
    segment_id: Optional[str]       # Segment where error occurred
    element_xid: Optional[str]      # Schema element identifier
    is_identifier_error: bool       # Critical identifier error flag
```

**Context Usage:**
```python
def format_error_report(error: CdmValidationError) -> str:
    location = []
    if error.line_number:
        location.append(f"Line {error.line_number}")
    if error.segment_id:
        location.append(f"Segment {error.segment_id}")
    if error.element_xid:
        location.append(f"Element {error.element_xid}")
    
    location_str = " - ".join(location) if location else "Unknown location"
    priority = "CRITICAL" if error.is_identifier_error else "ERROR"
    
    return f"[{priority}] {location_str}: {error.message}"
```

## Error Collection and Reporting

### Hierarchical Error Collection

Errors are attached to the most specific applicable level and can be collected hierarchically:

```python
def collect_all_errors(interchange: CdmInterchange) -> List[Tuple[str, CdmValidationError]]:
    """Collect all errors from entire interchange with location context."""
    errors = []
    
    # Interchange level
    for error in interchange.errors:
        errors.append(("Interchange", error))
    
    # Functional group level
    for fg_idx, fg in enumerate(interchange.functional_groups):
        for error in fg.errors:
            errors.append((f"Functional Group {fg_idx+1}", error))
        
        # Transaction level
        for txn_idx, txn in enumerate(fg.transactions):
            for error in txn.errors:
                errors.append((f"Transaction {txn_idx+1}", error))
            
            # Loop level (recursive)
            errors.extend(_collect_loop_errors(txn.body, f"Transaction {txn_idx+1}"))
    
    return errors

def _collect_loop_errors(loop: CdmLoop, context: str) -> List[Tuple[str, CdmValidationError]]:
    """Recursively collect errors from loop hierarchy."""
    errors = []
    
    # Loop errors
    for error in loop.errors:
        errors.append((f"{context} - Loop {loop.loop_id}", error))
    
    # Segment errors
    for segment in loop.segments:
        for error in segment.errors:
            location = f"{context} - Segment {segment.segment_id}"
            if segment.line_number:
                location += f" (Line {segment.line_number})"
            errors.append((location, error))
    
    # Nested loop errors
    for loop_type, loop_list in loop.loops.items():
        for idx, nested_loop in enumerate(loop_list):
            nested_context = f"{context} - {loop_type}[{idx}]"
            errors.extend(_collect_loop_errors(nested_loop, nested_context))
    
    return errors
```

### Error Reporting Formats

**Summary Report:**
```python
def generate_error_summary(interchange: CdmInterchange) -> dict:
    """Generate error summary statistics."""
    all_errors = collect_all_errors(interchange)
    
    return {
        "total_errors": len(all_errors),
        "critical_errors": sum(1 for _, e in all_errors if e.is_identifier_error),
        "error_by_type": {
            "structural": sum(1 for _, e in all_errors if "missing" in e.message.lower()),
            "data_validation": sum(1 for _, e in all_errors if "element" in e.message.lower()),
            "business_rules": sum(1 for _, e in all_errors if "syntax" in e.message.lower())
        },
        "transactions_with_errors": count_transactions_with_errors(interchange),
        "error_rate": calculate_error_rate(interchange, all_errors)
    }
```

**Detailed Report:**
```python
def generate_detailed_report(interchange: CdmInterchange) -> str:
    """Generate detailed error report for debugging."""
    all_errors = collect_all_errors(interchange)
    
    if not all_errors:
        return "✅ No errors found - EDI parsed successfully!"
    
    report = [
        f"🔍 EDI Validation Report - Found {len(all_errors)} errors\n",
        "=" * 60
    ]
    
    # Group errors by transaction
    errors_by_transaction = {}
    for location, error in all_errors:
        if "Transaction" in location:
            txn_id = location.split(" - ")[0]
            errors_by_transaction.setdefault(txn_id, []).append((location, error))
    
    for txn_id, txn_errors in errors_by_transaction.items():
        report.append(f"\n📄 {txn_id} ({len(txn_errors)} errors):")
        
        for location, error in txn_errors:
            priority = "🚨" if error.is_identifier_error else "⚠️"
            report.append(f"  {priority} {location}")
            report.append(f"     {error.message}")
            if error.line_number:
                report.append(f"     Line: {error.line_number}")
    
    return "\n".join(report)
```

## Error Recovery Strategies

### 1. **Transaction-Level Isolation**

Each transaction is parsed independently, so errors in one don't affect others:

```python
def parse_functional_group(self, segments: List[str]) -> CdmFunctionalGroup:
    """Parse functional group with transaction-level error isolation."""
    functional_group = CdmFunctionalGroup(...)
    
    for transaction_segments in split_into_transactions(segments):
        try:
            transaction = self._parse_transaction(transaction_segments)
            functional_group.transactions.append(transaction)
        except CriticalParsingError as e:
            # Log critical error but continue with next transaction
            logger.error(f"Critical error in transaction: {e}")
            # Still add a minimal transaction structure for error reporting
            error_transaction = create_error_transaction(transaction_segments, e)
            functional_group.transactions.append(error_transaction)
    
    return functional_group
```

### 2. **Partial Data Access**

Valid portions of data remain accessible even when other parts have errors:

```python
def extract_valid_claims(transaction: CdmTransaction) -> List[CdmLoop]:
    """Extract only valid claims, skipping those with critical errors."""
    valid_claims = []
    
    billing_providers = transaction.body.get_loops("2000A")
    for provider in billing_providers:
        if provider.errors:
            logger.warning(f"Skipping provider with errors: {provider.errors}")
            continue
            
        subscribers = provider.get_loops("2000B")
        for subscriber in subscribers:
            claims = subscriber.get_loops("2300")
            for claim in claims:
                # Check if claim has critical errors
                has_critical_errors = any(
                    error.is_identifier_error 
                    for error in claim.errors
                )
                
                if not has_critical_errors:
                    valid_claims.append(claim)
                else:
                    logger.warning(f"Skipping claim with critical errors")
    
    return valid_claims
```

### 3. **Default Value Strategies**

Provide sensible defaults for missing or invalid data:

```python
def get_element_with_default(segment: CdmSegment, position: int, default: str = "") -> str:
    """Get element value with default for missing/invalid values."""
    if not segment:
        return default
    
    value = segment.get_element(position)
    if value is None or value == "":
        return default
    
    # Check if element has validation errors
    element_errors = [
        error for error in segment.errors 
        if error.element_xid and error.element_xid.endswith(f"{position:02d}")
    ]
    
    if element_errors:
        logger.warning(f"Using default for invalid element: {element_errors}")
        return default
    
    return value

# Usage
claim_amount = get_element_with_default(clm_segment, 2, "0.00")
diagnosis_code = get_element_with_default(hi_segment, 1, "UNKNOWN")
```

## Validation Configuration

### Validation Levels

The parser supports different validation strictness levels:

```python
class ValidationLevel(Enum):
    STRICT = "strict"           # All validation rules enforced
    STANDARD = "standard"       # Standard business rules (default)  
    LENIENT = "lenient"         # Only critical structural validation
    PARSE_ONLY = "parse_only"   # No validation, just parsing

def configure_validation(parser: EdiParser, level: ValidationLevel):
    """Configure parser validation level."""
    parser.validation_config = {
        "enforce_required_segments": level != ValidationLevel.PARSE_ONLY,
        "validate_element_formats": level in [ValidationLevel.STRICT, ValidationLevel.STANDARD],
        "enforce_code_sets": level == ValidationLevel.STRICT,
        "apply_syntax_rules": level in [ValidationLevel.STRICT, ValidationLevel.STANDARD],
        "warn_on_deprecated": level == ValidationLevel.STRICT
    }
```

### Custom Validation Rules

Add custom validation logic for specific business requirements:

```python
def add_custom_validator(parser: EdiParser, validator_func):
    """Add custom validation function to parser."""
    parser.custom_validators.append(validator_func)

def validate_claim_amounts(transaction: CdmTransaction) -> List[CdmValidationError]:
    """Custom validator: ensure claim amounts are reasonable."""
    errors = []
    
    claims = extract_all_claims(transaction)
    for claim in claims:
        clm_segment = claim.get_segment("CLM")
        if clm_segment:
            amount_str = clm_segment.get_element(2)
            try:
                amount = float(amount_str)
                if amount > 100000:  # $100K threshold
                    errors.append(CdmValidationError(
                        message=f"Claim amount ${amount:,.2f} exceeds reasonable threshold",
                        line_number=clm_segment.line_number,
                        segment_id="CLM",
                        element_xid="CLM02",
                        is_identifier_error=False
                    ))
            except ValueError:
                errors.append(CdmValidationError(
                    message=f"Invalid claim amount format: '{amount_str}'",
                    line_number=clm_segment.line_number,
                    segment_id="CLM", 
                    element_xid="CLM02",
                    is_identifier_error=True
                ))
    
    return errors

# Usage
add_custom_validator(parser, validate_claim_amounts)
```

## Best Practices

### 1. **Error Handling in Production**

```python
def process_edi_file_safely(edi_content: str, schema: ImplementationGuideSchema):
    """Production-ready EDI processing with comprehensive error handling."""
    try:
        # Parse EDI
        parser = EdiParser(edi_string=edi_content, schema=schema)
        interchange = parser.parse()
        
        # Collect and analyze errors
        all_errors = parser._collect_all_errors(interchange)
        critical_errors = [e for _, e in all_errors if e.is_identifier_error]
        
        # Log error summary
        logger.info(f"Parsed EDI: {len(all_errors)} total errors, {len(critical_errors)} critical")
        
        # Decide on processing strategy
        if not critical_errors:
            # Process normally
            return process_valid_interchange(interchange)
        elif len(critical_errors) < len(all_errors) * 0.1:  # <10% critical errors
            # Process with caution
            logger.warning("Processing EDI with some critical errors")
            return process_interchange_with_errors(interchange, critical_errors)
        else:
            # Too many critical errors - reject
            logger.error("Too many critical errors - rejecting EDI")
            raise ValidationError(f"EDI rejected: {len(critical_errors)} critical errors")
            
    except Exception as e:
        logger.error(f"Failed to parse EDI: {e}")
        raise
```

### 2. **Error Reporting to Users**

```python
def create_user_friendly_error_report(errors: List[Tuple[str, CdmValidationError]]) -> dict:
    """Create user-friendly error report for business users."""
    report = {
        "summary": {
            "total_errors": len(errors),
            "critical_errors": sum(1 for _, e in errors if e.is_identifier_error),
            "can_process": all(not e.is_identifier_error for _, e in errors)
        },
        "errors_by_category": {},
        "recommendations": []
    }
    
    # Categorize errors
    categories = {
        "Missing Information": lambda e: "missing" in e.message.lower(),
        "Invalid Formats": lambda e: "format" in e.message.lower() or "length" in e.message.lower(),
        "Invalid Codes": lambda e: "code set" in e.message.lower(),
        "Business Rule Violations": lambda e: "syntax rule" in e.message.lower()
    }
    
    for category, check_func in categories.items():
        category_errors = [(loc, err) for loc, err in errors if check_func(err)]
        if category_errors:
            report["errors_by_category"][category] = [
                {
                    "location": loc,
                    "message": err.message,
                    "line": err.line_number,
                    "critical": err.is_identifier_error
                }
                for loc, err in category_errors
            ]
    
    # Add recommendations
    if report["summary"]["critical_errors"] == 0:
        report["recommendations"].append("File can be processed with warnings.")
    else:
        report["recommendations"].append("Critical errors must be fixed before processing.")
        report["recommendations"].append("Contact your EDI coordinator for assistance.")
    
    return report
```

### 3. **Performance Monitoring**

```python
def monitor_parsing_performance(edi_content: str) -> dict:
    """Monitor parsing performance and error rates."""
    import time
    
    start_time = time.time()
    
    try:
        parser = EdiParser(edi_string=edi_content, schema=schema)
        interchange = parser.parse()
        
        parse_time = time.time() - start_time
        all_errors = parser._collect_all_errors(interchange)
        
        # Calculate metrics
        total_segments = count_total_segments(interchange)
        error_rate = len(all_errors) / total_segments if total_segments > 0 else 0
        
        return {
            "parse_time_seconds": parse_time,
            "total_segments": total_segments,
            "segments_per_second": total_segments / parse_time if parse_time > 0 else 0,
            "total_errors": len(all_errors),
            "error_rate": error_rate,
            "critical_error_rate": sum(1 for _, e in all_errors if e.is_identifier_error) / total_segments
        }
        
    except Exception as e:
        return {
            "parse_time_seconds": time.time() - start_time,
            "error": str(e),
            "success": False
        }
```

## Next Steps

- **[Quick Start Guide](./05-quick-start.md)**: Getting started with error handling
- **[Usage Examples](./06-usage-examples.md)**: Practical error handling examples
- **[Troubleshooting](./08-troubleshooting.md)**: Common error scenarios and solutions