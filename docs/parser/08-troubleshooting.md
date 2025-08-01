# Troubleshooting Guide

This guide covers common issues you might encounter when using the EDI parser, along with solutions and workarounds.

## Common Error Scenarios

### 1. **Missing Required Loops**

**Error Message:**
```
Required segment or loop '1000A' (SUBMITTER NAME) is missing from loop 'ST_LOOP'.
```

**Cause:** The EDI is missing a required loop as defined by the implementation guide.

**Solutions:**

**A. Check EDI Structure**
```python
# Debug missing loop issue
def diagnose_missing_loop(edi_content: str, missing_loop_id: str):
    """Help diagnose why a required loop is missing."""
    lines = edi_content.strip().split('\n')
    
    print(f"🔍 Diagnosing missing loop: {missing_loop_id}")
    print("=" * 50)
    
    # Look for segments that should be in this loop
    loop_segments = {
        "1000A": ["NM1*41"],  # Submitter
        "1000B": ["NM1*40"],  # Receiver  
        "2000A": ["HL*", "NM1*85"],  # Billing provider
        "2000B": ["HL*", "SBR*"],    # Subscriber
        "2300": ["CLM*"]             # Claim
    }
    
    expected_segments = loop_segments.get(missing_loop_id, [])
    
    print(f"Expected segments for {missing_loop_id}: {expected_segments}")
    print("\nSearching EDI content:")
    
    found_segments = []
    for i, line in enumerate(lines, 1):
        for expected in expected_segments:
            if line.startswith(expected):
                found_segments.append((i, line))
                print(f"  Line {i}: {line[:50]}...")
    
    if not found_segments:
        print(f"❌ No segments found for {missing_loop_id}")
        print("💡 Suggestion: Check if EDI is truncated or missing data")
    else:
        print(f"✅ Found {len(found_segments)} relevant segments")
        print("💡 Suggestion: Segments exist but may be in wrong order or context")

# Usage
diagnose_missing_loop(edi_content, "1000A")
```

**B. Use Lenient Validation**
```python
# Continue processing despite missing loops
def parse_with_lenient_validation(edi_content: str):
    """Parse EDI with reduced validation for incomplete files."""
    schema_manager = SchemaManager()
    schema = schema_manager.get_schema("837.5010.X222.A1")
    
    # Parse normally first
    parser = EdiParser(edi_string=edi_content, schema=schema)
    interchange = parser.parse()
    
    all_errors = parser._collect_all_errors(interchange)
    missing_loop_errors = [
        error for _, error in all_errors 
        if "missing" in error.message.lower() and "loop" in error.message.lower()
    ]
    
    if missing_loop_errors:
        print(f"⚠️ Found {len(missing_loop_errors)} missing loop errors:")
        for _, error in missing_loop_errors:
            print(f"  - {error.message}")
        
        print("\n💡 Processing available data despite missing loops...")
        
        # Extract what data is available
        return extract_available_data(interchange)
    
    return interchange

def extract_available_data(interchange):
    """Extract whatever data is available from incomplete EDI."""
    available_data = {
        "interchange_info": {
            "sender": interchange.header.get_element(6),
            "receiver": interchange.header.get_element(8),
            "control_number": interchange.header.get_element(13)
        },
        "transactions": []
    }
    
    for fg in interchange.functional_groups:
        for txn in fg.transactions:
            txn_data = {
                "control_number": txn.header.get_element(2),
                "available_loops": list(txn.body.loops.keys()),
                "segment_count": len(txn.body.segments)
            }
            
            # Try to extract whatever we can
            if "2000A" in txn.body.loops:
                billing_providers = txn.body.get_loops("2000A")
                txn_data["billing_providers_count"] = len(billing_providers)
            
            if "2000B" in txn.body.loops:
                # Count subscribers across all billing providers
                total_subscribers = 0
                for provider in txn.body.get_loops("2000A"):
                    total_subscribers += len(provider.get_loops("2000B"))
                txn_data["subscribers_count"] = total_subscribers
            
            available_data["transactions"].append(txn_data)
    
    return available_data
```

### 2. **Element Validation Errors**

**Error Messages:**
```
Element 'BHT04': Value is shorter than min length 8.
Element 'BHT04': Value does not match expected format 'CCYYMMDD'.
```

**Cause:** Element values don't meet schema requirements for length, format, or data type.

**Solutions:**

**A. Diagnose Element Issues**
```python
def diagnose_element_errors(edi_content: str):
    """Diagnose and suggest fixes for element validation errors."""
    schema_manager = SchemaManager()
    schema = schema_manager.get_schema("837.5010.X222.A1")
    
    parser = EdiParser(edi_string=edi_content, schema=schema)
    interchange = parser.parse()
    
    all_errors = parser._collect_all_errors(interchange)
    element_errors = [
        (location, error) for location, error in all_errors 
        if error.element_xid is not None
    ]
    
    if not element_errors:
        print("✅ No element validation errors found")
        return
    
    print(f"🔍 Found {len(element_errors)} element validation errors:")
    print("=" * 60)
    
    # Group errors by element
    errors_by_element = {}
    for location, error in element_errors:
        element_id = error.element_xid
        if element_id not in errors_by_element:
            errors_by_element[element_id] = []
        errors_by_element[element_id].append((location, error))
    
    for element_id, element_errors in errors_by_element.items():
        print(f"\n📍 Element {element_id}:")
        
        for location, error in element_errors:
            print(f"  ❌ {error.message}")
            print(f"     Location: {location}")
            if error.line_number:
                print(f"     Line: {error.line_number}")
        
        # Provide suggestions
        suggestions = get_element_fix_suggestions(element_id, element_errors)
        if suggestions:
            print(f"  💡 Suggestions:")
            for suggestion in suggestions:
                print(f"     • {suggestion}")

def get_element_fix_suggestions(element_id: str, errors):
    """Get fix suggestions for specific element errors."""
    suggestions = []
    
    error_messages = [error.message for _, error in errors]
    
    if any("shorter than min length" in msg for msg in error_messages):
        if element_id == "BHT04":
            suggestions.append("BHT04 should be 8-digit date (CCYYMMDD), e.g., '20240715'")
        else:
            suggestions.append(f"Check {element_id} minimum length requirements in schema")
    
    if any("longer than max length" in msg for msg in error_messages):
        suggestions.append(f"Truncate {element_id} value to meet maximum length")
    
    if any("format" in msg.lower() for msg in error_messages):
        if "CCYYMMDD" in " ".join(error_messages):
            suggestions.append("Use 8-digit date format: YYYYMMDD (e.g., 20240715)")
        elif "HHMM" in " ".join(error_messages):
            suggestions.append("Use 4-digit time format: HHMM (e.g., 1430 for 2:30 PM)")
    
    if any("code set" in msg.lower() for msg in error_messages):
        suggestions.append(f"Check valid code values for {element_id} in implementation guide")
        suggestions.append("Common valid codes may include specific predefined values")
    
    return suggestions
```

**B. Fix Common Element Issues**
```python
def fix_common_element_issues(edi_content: str) -> str:
    """Automatically fix common element validation issues."""
    lines = edi_content.strip().split('\n')
    fixed_lines = []
    
    for line in lines:
        original_line = line
        
        # Fix BHT segment date format issues
        if line.startswith('BHT*'):
            parts = line.split('*')
            if len(parts) >= 5:  # BHT04 is position 4 (0-indexed)
                date_value = parts[4]
                # Fix shortened dates
                if len(date_value) == 6 and date_value.isdigit():
                    # Assume 20XX for 6-digit dates
                    parts[4] = '20' + date_value
                    line = '*'.join(parts)
                    print(f"🔧 Fixed BHT04 date: '{date_value}' → '{parts[4]}'")
        
        # Fix other common issues
        # Add more fixes as needed...
        
        fixed_lines.append(line)
    
    return '\n'.join(fixed_lines)

# Usage
fixed_edi = fix_common_element_issues(edi_content)
```

### 3. **Transaction Parsing Incomplete**

**Error Message:**
```
Transaction parsing incomplete. Could not process 26 remaining segments starting with 'PER'.
```

**Cause:** Parser encountered segments that don't fit the expected schema structure.

**Solutions:**

**A. Analyze Unparsed Segments**
```python
def analyze_unparsed_segments(edi_content: str):
    """Analyze why certain segments weren't parsed."""
    schema_manager = SchemaManager()
    schema = schema_manager.get_schema("837.5010.X222.A1")
    
    parser = EdiParser(edi_string=edi_content, schema=schema)
    interchange = parser.parse()
    
    all_errors = parser._collect_all_errors(interchange)
    incomplete_errors = [
        error for _, error in all_errors 
        if "parsing incomplete" in error.message.lower()
    ]
    
    if not incomplete_errors:
        print("✅ All segments parsed successfully")
        return
    
    for error in incomplete_errors:
        print(f"🔧 Parsing incomplete error:")
        print(f"   Message: {error.message}")
        if error.line_number:
            print(f"   Starting at line: {error.line_number}")
            
            # Show the problematic segments
            lines = edi_content.strip().split('\n')
            start_line = error.line_number - 1  # Convert to 0-based
            
            print(f"   Unparsed segments:")
            for i in range(start_line, min(start_line + 5, len(lines))):
                print(f"     Line {i+1}: {lines[i]}")
            
            # Analyze the segment types
            unparsed_segments = lines[start_line:]
            segment_types = [line.split('*')[0] for line in unparsed_segments if '*' in line]
            segment_count = {}
            for seg_type in segment_types:
                segment_count[seg_type] = segment_count.get(seg_type, 0) + 1
            
            print(f"   Segment types in unparsed portion:")
            for seg_type, count in segment_count.items():
                print(f"     {seg_type}: {count} occurrences")
            
            # Provide suggestions
            print(f"   💡 Possible causes:")
            print(f"     • Missing required preceding loop (e.g., 1000A submitter)")
            print(f"     • Segments in wrong order")
            print(f"     • Schema doesn't recognize this segment combination")
            print(f"     • HL hierarchy issues")

# Usage
analyze_unparsed_segments(edi_content)
```

**B. Extract Raw Segments**
```python
def extract_raw_segments_info(edi_content: str):
    """Extract information from raw segments when parsing fails."""
    lines = edi_content.strip().split('\n')
    
    # Find transaction boundaries
    transactions = []
    current_transaction = []
    
    for line in lines:
        if line.startswith('ST*'):
            if current_transaction:
                transactions.append(current_transaction)
            current_transaction = [line]
        elif line.startswith('SE*'):
            current_transaction.append(line)
            transactions.append(current_transaction)
            current_transaction = []
        elif current_transaction:
            current_transaction.append(line)
    
    print(f"Found {len(transactions)} transactions in raw EDI")
    
    for i, txn_lines in enumerate(transactions, 1):
        print(f"\n📄 Transaction {i}:")
        
        # Count segment types
        segment_counts = {}
        hl_segments = []
        
        for line in txn_lines:
            if '*' in line:
                seg_type = line.split('*')[0]
                segment_counts[seg_type] = segment_counts.get(seg_type, 0) + 1
                
                if seg_type == 'HL':
                    parts = line.split('*')
                    if len(parts) >= 4:
                        hl_id = parts[1]
                        parent_id = parts[2] if parts[2] else None
                        level_code = parts[3]
                        hl_segments.append({
                            'id': hl_id,
                            'parent': parent_id,
                            'level': level_code,
                            'line': line
                        })
        
        print(f"   Segments: {dict(sorted(segment_counts.items()))}")
        
        if hl_segments:
            print(f"   HL Hierarchy:")
            for hl in hl_segments:
                level_name = {
                    '20': 'Billing Provider',
                    '22': 'Subscriber', 
                    '23': 'Patient'
                }.get(hl['level'], f"Level {hl['level']}")
                
                parent_info = f" (parent: {hl['parent']})" if hl['parent'] else " (root)"
                print(f"     HL {hl['id']}: {level_name}{parent_info}")
    
    return transactions

# Usage
raw_transactions = extract_raw_segments_info(edi_content)
```

### 4. **Schema Loading Issues**

**Error Message:**
```
Schema not found: 837.5010.X222.A1
```

**Cause:** The specified schema file is not available or path is incorrect.

**Solutions:**

**A. Check Available Schemas**
```python
def check_available_schemas():
    """Check what schemas are available."""
    import os
    from pathlib import Path
    
    schema_paths = [
        "backend/data/edi_schemas/",
        "data/edi_schemas/",
        "backend/data/base_schemas/"
    ]
    
    print("🔍 Checking for available schemas:")
    print("=" * 40)
    
    for schema_path in schema_paths:
        path = Path(schema_path)
        if path.exists():
            print(f"📁 {schema_path}:")
            for file in path.glob("*.json"):
                print(f"   ✅ {file.name}")
        else:
            print(f"📁 {schema_path}: ❌ Not found")
    
    # Check schema manager
    try:
        schema_manager = SchemaManager()
        print(f"\n🔧 Schema Manager Status:")
        print(f"   Initialized: ✅")
        
        # Try to load common schema
        try:
            schema = schema_manager.get_schema("837.5010.X222.A1")
            print(f"   837P Schema: ✅ Loaded successfully")
        except Exception as e:
            print(f"   837P Schema: ❌ {str(e)}")
            
    except Exception as e:
        print(f"   Schema Manager: ❌ {str(e)}")

# Usage
check_available_schemas()
```

**B. Manual Schema Loading**
```python
def load_schema_manually(schema_file_path: str):
    """Manually load schema from file path."""
    import json
    from pathlib import Path
    
    try:
        schema_path = Path(schema_file_path)
        if not schema_path.exists():
            print(f"❌ Schema file not found: {schema_path}")
            return None
        
        with open(schema_path, 'r') as f:
            schema_data = json.load(f)
        
        # Create schema object
        from src.edi_schemas.edi_guide import ImplementationGuideSchema
        schema = ImplementationGuideSchema(**schema_data)
        
        print(f"✅ Manually loaded schema from: {schema_path}")
        print(f"   Transaction Type: {schema.transactionSetIdentifierCode}")
        print(f"   Version: {schema.implementationConventionReference}")
        
        return schema
        
    except Exception as e:
        print(f"❌ Failed to load schema: {str(e)}")
        return None

# Usage - try different paths
schema_paths = [
    "backend/data/edi_schemas/837.5010.X222.A1.json",
    "data/edi_schemas/837.5010.X222.A1.json",
    "backend/data/base_schemas/837.5010.X222.A1.json"
]

schema = None
for path in schema_paths:
    schema = load_schema_manually(path)
    if schema:
        break

if schema:
    # Use the manually loaded schema
    parser = EdiParser(edi_string=edi_content, schema=schema)
    interchange = parser.parse()
```

### 5. **Memory and Performance Issues**

**Error Message:**
```
MemoryError: Unable to allocate memory
Process killed due to memory limit
```

**Cause:** Large EDI files or memory leaks during processing.

**Solutions:**

**A. Process Large Files in Chunks**
```python
def process_large_edi_file(file_path: str, chunk_size: int = 100):
    """Process large EDI files in manageable chunks."""
    
    def split_edi_into_transactions(edi_content: str):
        """Split EDI content into individual transactions."""
        lines = edi_content.strip().split('\n')
        
        # Find ISA/GS headers to preserve
        isa_line = next((line for line in lines if line.startswith('ISA*')), None)
        gs_line = next((line for line in lines if line.startswith('GS*')), None)
        
        transactions = []
        current_transaction = []
        
        for line in lines:
            if line.startswith('ST*'):
                current_transaction = [line]
            elif line.startswith('SE*'):
                current_transaction.append(line)
                
                # Create complete EDI for this transaction
                transaction_edi = [
                    isa_line,
                    gs_line,
                    *current_transaction,
                    'GE*1*1~',  # Placeholder functional group trailer
                    'IEA*1*000000001~'  # Placeholder interchange trailer
                ]
                
                transactions.append('\n'.join(transaction_edi))
                current_transaction = []
            elif current_transaction:
                current_transaction.append(line)
        
        return transactions
    
    # Read file in chunks if very large
    with open(file_path, 'r') as f:
        content = f.read()
    
    print(f"📄 Processing file: {file_path}")
    print(f"   File size: {len(content):,} characters")
    
    # Split into transactions
    transactions = split_edi_into_transactions(content)
    print(f"   Found {len(transactions)} transactions")
    
    # Process in chunks
    results = []
    
    for i in range(0, len(transactions), chunk_size):
        chunk = transactions[i:i+chunk_size]
        print(f"   Processing chunk {i//chunk_size + 1}: transactions {i+1}-{min(i+chunk_size, len(transactions))}")
        
        chunk_results = []
        for j, txn_edi in enumerate(chunk):
            try:
                schema_manager = SchemaManager()
                schema = schema_manager.get_schema("837.5010.X222.A1")
                
                parser = EdiParser(edi_string=txn_edi, schema=schema)
                interchange = parser.parse()
                
                # Extract minimal data to save memory
                txn_data = extract_minimal_transaction_data(interchange)
                chunk_results.append(txn_data)
                
            except Exception as e:
                print(f"     ❌ Transaction {i+j+1} failed: {str(e)}")
                chunk_results.append({"error": str(e), "transaction_index": i+j+1})
        
        results.extend(chunk_results)
        
        # Force garbage collection
        import gc
        gc.collect()
    
    return results

def extract_minimal_transaction_data(interchange):
    """Extract only essential data to minimize memory usage."""
    data = {
        "control_number": None,
        "claims_count": 0,
        "total_amount": 0.0,
        "errors_count": 0
    }
    
    try:
        transaction = interchange.functional_groups[0].transactions[0]
        data["control_number"] = transaction.header.get_element(2)
        
        # Count claims and amounts quickly
        billing_providers = transaction.body.get_loops("2000A")
        for provider in billing_providers:
            subscribers = provider.get_loops("2000B")
            for subscriber in subscribers:
                claims = subscriber.get_loops("2300")
                data["claims_count"] += len(claims)
                
                for claim in claims:
                    clm_segment = claim.get_segment("CLM")
                    if clm_segment and clm_segment.get_element(2):
                        try:
                            amount = float(clm_segment.get_element(2))
                            data["total_amount"] += amount
                        except ValueError:
                            pass
        
        # Count errors
        all_errors = []
        # Simplified error collection to save memory
        for error in transaction.errors:
            all_errors.append(error)
        data["errors_count"] = len(all_errors)
        
    except Exception as e:
        data["extraction_error"] = str(e)
    
    return data

# Usage
results = process_large_edi_file("large_edi_file.txt", chunk_size=50)
print(f"Processed {len(results)} transactions")

# Summarize results
total_claims = sum(r.get("claims_count", 0) for r in results)
total_amount = sum(r.get("total_amount", 0.0) for r in results)
error_count = sum(1 for r in results if "error" in r)

print(f"Summary: {total_claims} claims, ${total_amount:,.2f} total, {error_count} errors")
```

## Debugging Tools

### 1. **EDI Structure Analyzer**
```python
def analyze_edi_structure(edi_content: str):
    """Analyze EDI structure for debugging."""
    lines = edi_content.strip().split('\n')
    
    analysis = {
        "total_lines": len(lines),
        "envelopes": {"ISA": 0, "GS": 0, "ST": 0},
        "segments_by_type": {},
        "hl_hierarchy": [],
        "issues": []
    }
    
    for i, line in enumerate(lines, 1):
        if '*' in line:
            seg_type = line.split('*')[0]
            analysis["segments_by_type"][seg_type] = analysis["segments_by_type"].get(seg_type, 0) + 1
            
            if seg_type in ["ISA", "GS", "ST"]:
                analysis["envelopes"][seg_type] += 1
            
            if seg_type == "HL":
                parts = line.split('*')
                if len(parts) >= 4:
                    analysis["hl_hierarchy"].append({
                        "line": i,
                        "id": parts[1],
                        "parent": parts[2] if parts[2] else None,
                        "level": parts[3]
                    })
        else:
            analysis["issues"].append(f"Line {i}: Invalid segment format")
    
    # Check for structural issues
    if analysis["envelopes"]["ISA"] == 0:
        analysis["issues"].append("Missing ISA header")
    if analysis["envelopes"]["GS"] == 0:
        analysis["issues"].append("Missing GS functional group header")
    if analysis["envelopes"]["ST"] == 0:
        analysis["issues"].append("Missing ST transaction header")
    
    return analysis

# Usage
analysis = analyze_edi_structure(edi_content)
print(f"EDI Structure Analysis:")
print(f"  Lines: {analysis['total_lines']}")
print(f"  Envelopes: ISA={analysis['envelopes']['ISA']}, GS={analysis['envelopes']['GS']}, ST={analysis['envelopes']['ST']}")
print(f"  Unique segment types: {len(analysis['segments_by_type'])}")
print(f"  HL segments: {len(analysis['hl_hierarchy'])}")
if analysis['issues']:
    print(f"  Issues found: {len(analysis['issues'])}")
    for issue in analysis['issues']:
        print(f"    - {issue}")
```

### 2. **Performance Monitor**
```python
import time
import psutil
import os

def monitor_parsing_performance(edi_content: str):
    """Monitor parsing performance and resource usage."""
    process = psutil.Process(os.getpid())
    
    # Initial measurements
    start_time = time.time()
    start_memory = process.memory_info().rss / 1024 / 1024  # MB
    
    try:
        schema_manager = SchemaManager()
        schema = schema_manager.get_schema("837.5010.X222.A1")
        
        schema_load_time = time.time()
        
        parser = EdiParser(edi_string=edi_content, schema=schema)
        
        parser_init_time = time.time()
        
        interchange = parser.parse()
        
        parse_complete_time = time.time()
        
        all_errors = parser._collect_all_errors(interchange)
        
        error_collection_time = time.time()
        
        # Final measurements
        end_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Calculate metrics
        total_segments = sum(
            len(txn.body.segments) + 
            sum(len(loop.segments) for loop_list in txn.body.loops.values() for loop in loop_list)
            for fg in interchange.functional_groups
            for txn in fg.transactions
        )
        
        performance_report = {
            "timing": {
                "schema_load": schema_load_time - start_time,
                "parser_init": parser_init_time - schema_load_time,
                "parsing": parse_complete_time - parser_init_time,
                "error_collection": error_collection_time - parse_complete_time,
                "total": error_collection_time - start_time
            },
            "memory": {
                "start_mb": start_memory,
                "end_mb": end_memory,
                "peak_mb": process.memory_info().rss / 1024 / 1024,
                "delta_mb": end_memory - start_memory
            },
            "throughput": {
                "segments_count": total_segments,
                "segments_per_second": total_segments / (parse_complete_time - parser_init_time) if parse_complete_time > parser_init_time else 0,
                "chars_count": len(edi_content),
                "chars_per_second": len(edi_content) / (parse_complete_time - parser_init_time) if parse_complete_time > parser_init_time else 0
            },
            "results": {
                "functional_groups": len(interchange.functional_groups),
                "transactions": sum(len(fg.transactions) for fg in interchange.functional_groups),
                "total_errors": len(all_errors),
                "critical_errors": sum(1 for _, error in all_errors if error.is_identifier_error)
            }
        }
        
        return performance_report
        
    except Exception as e:
        end_memory = process.memory_info().rss / 1024 / 1024
        return {
            "error": str(e),
            "timing": {"total": time.time() - start_time},
            "memory": {"delta_mb": end_memory - start_memory}
        }

# Usage
perf_report = monitor_parsing_performance(edi_content)
print("Performance Report:")
print(f"  Parsing Time: {perf_report['timing']['parsing']:.3f}s")
print(f"  Memory Usage: {perf_report['memory']['delta_mb']:.1f} MB")
print(f"  Throughput: {perf_report['throughput']['segments_per_second']:.0f} segments/sec")
print(f"  Results: {perf_report['results']['transactions']} transactions, {perf_report['results']['total_errors']} errors")
```

## Recovery Strategies

### Extract Partial Data
```python
def extract_partial_data_on_failure(edi_content: str):
    """Extract whatever data possible when full parsing fails."""
    try:
        # First try normal parsing
        schema_manager = SchemaManager()
        schema = schema_manager.get_schema("837.5010.X222.A1")
        parser = EdiParser(edi_string=edi_content, schema=schema)
        interchange = parser.parse()
        
        return {"status": "success", "data": interchange}
        
    except Exception as e:
        print(f"⚠️ Full parsing failed: {str(e)}")
        print("🔧 Attempting partial data extraction...")
        
        # Try to extract basic structure
        try:
            partial_data = extract_basic_structure(edi_content)
            return {"status": "partial", "data": partial_data, "error": str(e)}
        except Exception as e2:
            return {"status": "failed", "error": str(e), "fallback_error": str(e2)}

def extract_basic_structure(edi_content: str):
    """Extract basic EDI structure without full schema validation."""
    lines = edi_content.strip().split('\n')
    
    structure = {
        "interchange": {},
        "functional_groups": [],
        "transactions": []
    }
    
    # Extract ISA info
    isa_line = next((line for line in lines if line.startswith('ISA*')), None)
    if isa_line:
        isa_parts = isa_line.split('*')
        if len(isa_parts) >= 16:
            structure["interchange"] = {
                "sender": isa_parts[6],
                "receiver": isa_parts[8],
                "control_number": isa_parts[13],
                "test_indicator": isa_parts[15]
            }
    
    # Extract transactions
    current_transaction = None
    for line in lines:
        if line.startswith('ST*'):
            st_parts = line.split('*')
            current_transaction = {
                "type": st_parts[1] if len(st_parts) > 1 else "Unknown",
                "control_number": st_parts[2] if len(st_parts) > 2 else "Unknown",
                "segments": [],
                "claims": []
            }
        elif line.startswith('SE*') and current_transaction:
            structure["transactions"].append(current_transaction)
            current_transaction = None
        elif current_transaction:
            current_transaction["segments"].append(line.split('*')[0])
            
            # Try to extract claim info
            if line.startswith('CLM*'):
                clm_parts = line.split('*')
                if len(clm_parts) >= 3:
                    claim_info = {
                        "id": clm_parts[1],
                        "amount": clm_parts[2] if clm_parts[2] else "0"
                    }
                    current_transaction["claims"].append(claim_info)
    
    return structure

# Usage
result = extract_partial_data_on_failure(edi_content)
if result["status"] == "success":
    print("✅ Full parsing successful")
elif result["status"] == "partial":
    print("⚠️ Partial data extracted:")
    print(f"   Transactions: {len(result['data']['transactions'])}")
    print(f"   Total claims: {sum(len(txn['claims']) for txn in result['data']['transactions'])}")
else:
    print("❌ Complete parsing failure")
```

## Getting Help

### 1. **Enable Debug Logging**
```python
import logging

# Enable detailed logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('src.core.edi_parser')
logger.setLevel(logging.DEBUG)

# Now run your parsing with detailed logs
parser = EdiParser(edi_string=edi_content, schema=schema)
interchange = parser.parse()
```

### 2. **Create Minimal Reproduction**
```python
def create_minimal_repro(edi_content: str, error_message: str):
    """Create minimal EDI that reproduces the error."""
    lines = edi_content.strip().split('\n')
    
    # Keep essential structure
    essential_lines = []
    for line in lines:
        if line.startswith(('ISA*', 'GS*', 'ST*', 'SE*', 'GE*', 'IEA*')):
            essential_lines.append(line)
        elif line.startswith('BHT*'):  # Transaction header
            essential_lines.append(line)
        elif "missing" in error_message.lower() and "1000A" in error_message:
            # Keep submitter-related segments
            if line.startswith('NM1*41*'):
                essential_lines.append(line)
    
    minimal_edi = '\n'.join(essential_lines)
    
    print("Minimal reproduction EDI:")
    print("=" * 40)
    print(minimal_edi)
    print("=" * 40)
    
    return minimal_edi
```

### 3. **Report Issues**
When reporting issues, include:
- **EDI sample** (minimal reproduction)
- **Error message** (full stack trace)
- **Expected behavior** 
- **Environment info** (Python version, EDI-Lens version)
- **Performance data** (if relevant)

## Next Steps

- **[Quick Start Guide](./05-quick-start.md)**: Basic usage patterns
- **[Usage Examples](./06-usage-examples.md)**: More examples and patterns  
- **[API Reference](./12-api-reference.md)**: Complete method documentation