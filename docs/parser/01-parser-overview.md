# Parser Overview

## Architecture

The EDI-Lens parser follows a modular, schema-driven architecture designed for robustness, flexibility, and maintainability.

### Core Components

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   EDI String    │───▶│   EdiParser     │───▶│ CdmInterchange  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                               │
                               ▼
                    ┌─────────────────┐
                    │ Schema Manager  │
                    └─────────────────┘
                               │
                               ▼
                    ┌─────────────────┐
                    │Implementation   │
                    │Guide Schema     │
                    └─────────────────┘
```

### 1. **EdiParser** (`src/core/edi_parser.py`)
The main parsing engine that orchestrates the entire parsing process.

**Key Responsibilities:**
- **Segment Parsing**: Splits EDI string into individual segments
- **Loop Detection**: Identifies hierarchical loop structures based on HL segments
- **Schema Validation**: Applies implementation guide rules and validations
- **Error Collection**: Aggregates and reports all validation errors
- **CDM Generation**: Converts parsed data into Canonical Data Model

**Key Methods:**
```python
class EdiParser:
    def parse() -> CdmInterchange           # Main parsing entry point
    def _parse_interchange()                # Parses ISA-IEA envelope
    def _parse_functional_group()           # Parses GS-GE envelope  
    def _parse_transaction()                # Parses ST-SE transaction
    def _parse_loop_structure()             # Identifies loop hierarchy
    def _collect_all_errors()               # Aggregates validation errors
```

### 2. **Canonical Data Model (CDM)** (`src/core/cdm.py`)
A hierarchical data structure that represents parsed EDI data in a consistent, type-safe format.

**CDM Hierarchy:**
```
CdmInterchange
├── CdmFunctionalGroup[]
    ├── CdmTransaction[]
        ├── header: CdmSegment (ST)
        ├── trailer: CdmSegment (SE)
        └── body: CdmLoop (Transaction body)
            ├── segments: CdmSegment[]
            └── loops: Dict[str, CdmLoop[]]
```

**Benefits:**
- **Type Safety**: Pydantic models ensure data integrity
- **Easy Access**: Intuitive methods for navigating hierarchical data
- **Error Tracking**: Each component can contain validation errors
- **Raw Preservation**: Original segment strings preserved for debugging

### 3. **Schema System** (`src/edi_schemas/edi_guide.py`)
Defines the structure and validation rules for EDI transactions.

**Schema Components:**
- **ImplementationGuideSchema**: Top-level schema container
- **StructureLoop**: Defines loop hierarchy and nesting rules
- **StructureSegment**: Defines segment composition and validation
- **ElementDefinition**: Defines element data types, lengths, and codes
- **SyntaxRule**: Advanced validation rules and conditions

### 4. **Schema Manager** (`src/core/schema_manager.py`)
Manages loading and caching of EDI implementation guide schemas.

**Features:**
- **Schema Caching**: Avoids repeated file I/O operations
- **Version Management**: Supports multiple schema versions
- **Lazy Loading**: Schemas loaded on-demand
- **Singleton Pattern**: Ensures single instance across application

## Parsing Strategy

### Schema-Driven Approach
The parser uses implementation guide schemas to understand:
1. **Expected Loop Structure**: What loops can appear and where
2. **Segment Definitions**: Required vs optional segments within loops
3. **Element Validation**: Data types, lengths, formats, and code sets
4. **Business Rules**: Complex validation logic and syntax rules

### Error-Tolerant Design
The parser is designed to be **fault-tolerant**:
- **Continue on Errors**: Parsing continues even when validation errors occur
- **Error Isolation**: Errors in one transaction don't affect others
- **Partial Success**: Valid portions of data remain accessible
- **Comprehensive Reporting**: All errors are collected and reported with context

### Hierarchical Loop Processing
EDI transactions use hierarchical loop structures (HL segments). The parser:
1. **Identifies Loop Boundaries**: Uses HL segments to detect loop starts
2. **Builds Hierarchy**: Creates nested loop structure based on parent relationships
3. **Assigns Segments**: Places segments within appropriate loops
4. **Validates Structure**: Ensures loops conform to schema requirements

## Key Design Principles

### 1. **Separation of Concerns**
- **Parsing Logic**: Separated from validation logic
- **Data Structure**: CDM independent of parsing implementation
- **Schema Management**: Isolated from parsing engine
- **Error Handling**: Centralized error collection and reporting

### 2. **Extensibility**
- **Schema-Driven**: New transaction types supported via schema files
- **Pluggable Validation**: Custom validation rules via schema syntax rules  
- **Multiple Formats**: Architecture supports extending beyond X12

### 3. **Performance**
- **Streaming Parser**: Processes data incrementally, not loading entire structure into memory
- **Schema Caching**: Avoids repeated schema parsing
- **Efficient Data Structures**: Uses appropriate data structures for different access patterns

### 4. **Debugging & Observability**
- **Detailed Logging**: Comprehensive logging at different levels
- **Raw Data Preservation**: Original segments preserved for debugging
- **Error Context**: Errors include line numbers, segment IDs, and element positions
- **Parsing Statistics**: Reports on parsing success/failure rates

## Supported Transaction Types

### Healthcare Transactions
- **837P (Professional Claims)**: Fully supported with comprehensive validation
- **837I (Institutional Claims)**: Schema-ready, parser supports structure
- **835 (Remittance Advice)**: Schema-ready, parser supports structure

### Loop Types Supported
- **2000A**: Billing Provider Hierarchical Level
- **2000B**: Subscriber Hierarchical Level  
- **2000C**: Patient Hierarchical Level
- **2300**: Claim Information Loop
- **2400**: Service Line Loop
- **Various Supporting Loops**: 1000A/B, 2010AA/AB/BA, etc.

## Error Handling Philosophy

The parser follows a **"Parse First, Validate Second"** approach:

1. **Structural Parsing**: Always attempts to parse the EDI structure
2. **Validation Layer**: Applies business rules and schema validation
3. **Error Collection**: Collects but doesn't halt on validation errors
4. **Graceful Degradation**: Valid data remains accessible despite errors elsewhere

This approach ensures maximum data recovery and provides detailed diagnostics for data quality issues.

## Next Steps

- **[Parsing Flow](./02-parsing-flow.md)**: Detailed step-by-step parsing process
- **[Data Structures](./03-data-structures.md)**: Deep dive into CDM components
- **[Error Handling](./04-error-handling.md)**: Comprehensive error handling strategies