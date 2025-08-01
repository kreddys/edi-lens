# EDI Parser Documentation

This directory contains comprehensive documentation for the EDI-Lens EDI Parser, a robust and flexible Electronic Data Interchange (EDI) parsing engine designed specifically for healthcare transactions.

## Overview

The EDI-Lens parser is a schema-driven EDI parsing system that can handle complex healthcare EDI transactions such as 837P (Professional Claims), 835 (Remittance Advice), and other X12 transaction sets. It provides comprehensive validation, error handling, and data extraction capabilities while maintaining structural integrity even when encountering malformed data.

## Documentation Structure

### Core Documentation
- **[Parser Overview](./01-parser-overview.md)** - High-level architecture and key concepts
- **[Parsing Flow](./02-parsing-flow.md)** - Detailed parsing process and algorithm
- **[Data Structures](./03-data-structures.md)** - CDM (Canonical Data Model) and internal structures
- **[Error Handling](./04-error-handling.md)** - Validation, error reporting, and recovery mechanisms

### Usage Guides  
- **[Quick Start Guide](./05-quick-start.md)** - Getting started with the parser
- **[Usage Examples](./06-usage-examples.md)** - Common use cases and code examples
- **[Advanced Features](./07-advanced-features.md)** - Complex scenarios and edge cases
- **[Troubleshooting](./08-troubleshooting.md)** - Common issues and solutions

### Technical Reference
- **[Schema System](./09-schema-system.md)** - Implementation guides and schema structure
- **[Testing Guide](./10-testing-guide.md)** - Test patterns and best practices
- **[Performance](./11-performance.md)** - Performance characteristics and optimization
- **[API Reference](./12-api-reference.md)** - Complete API documentation

## Key Features

### 🔧 **Robust Parsing Engine**
- **Schema-driven parsing** with support for X12 implementation guides
- **Hierarchical loop structure** parsing with proper nesting
- **Multiple transaction set** support in a single interchange
- **Flexible segment and element** validation

### 🛡️ **Error Handling & Validation**
- **Comprehensive validation** at segment, element, and loop levels
- **Error isolation** - errors in one transaction don't affect others
- **Detailed error reporting** with line numbers and context
- **Graceful degradation** - continues parsing despite errors

### 📊 **Data Access & Management**
- **Canonical Data Model (CDM)** for structured data access
- **Intuitive API** for accessing nested data structures
- **Type-safe data models** using Pydantic
- **Raw segment preservation** for debugging and audit trails

### 🔍 **Healthcare Focus**
- **837P Professional Claims** fully supported
- **Complex claim scenarios** including multiple providers and subscribers
- **Patient vs Subscriber** claim distinction
- **Service line and diagnosis** handling

## Quick Example

```python
from src.core.edi_parser import EdiParser
from src.core.schema_manager import SchemaManager

# Load schema and parse EDI
schema_manager = SchemaManager()
schema = schema_manager.get_schema("837.5010.X222.A1")

parser = EdiParser(edi_string=edi_content, schema=schema)
interchange = parser.parse()

# Access parsed data
for functional_group in interchange.functional_groups:
    for transaction in functional_group.transactions:
        billing_provider = transaction.body.get_loop("2000A")
        provider_name = billing_provider.get_loop("2010AA").get_segment("NM1").get_element(3)
        print(f"Billing Provider: {provider_name}")

# Check for errors
all_errors = parser._collect_all_errors(interchange)
if all_errors:
    for location, error in all_errors:
        print(f"Error at {location}: {error.message}")
```

## Getting Started

1. **Start with the [Parser Overview](./01-parser-overview.md)** to understand the architecture
2. **Read the [Quick Start Guide](./05-quick-start.md)** for basic usage
3. **Explore [Usage Examples](./06-usage-examples.md)** for common scenarios
4. **Reference [Error Handling](./04-error-handling.md)** for production use

## Contributing

When adding new features or fixing bugs:
1. Update relevant documentation
2. Add test cases following the [Testing Guide](./10-testing-guide.md)
3. Update API documentation if needed
4. Consider performance implications per [Performance Guide](./11-performance.md)

## Support

For issues and questions:
- Check the [Troubleshooting Guide](./08-troubleshooting.md)
- Review [Common Issues](./08-troubleshooting.md#common-issues)
- Consult the [API Reference](./12-api-reference.md) for detailed specifications