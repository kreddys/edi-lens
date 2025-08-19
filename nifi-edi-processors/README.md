# NiFi EDI Processors

Native Python processors for Apache NiFi to handle EDI validation, parsing, and TA1 generation without external API dependencies.

## Project Structure

```
nifi-edi-processors/
├── processors/           # NiFi Python processors
│   ├── edi_validation_processor.py
│   ├── ta1_generation_processor.py
│   └── edi_parsing_processor.py
├── edi_common/          # Shared modules ported from backend
│   ├── validation_service.py
│   ├── ta1_generator.py
│   ├── edi_parser.py
│   ├── schema_manager.py
│   └── cdm.py
├── tests/               # Comprehensive test suite
│   ├── edi_parser/      # Unit tests for EDI parsing
│   └── ...              # Integration and format tests
├── schemas/             # EDI schema files
└── test_runner.py       # Convenient test runner script
```

## Installation

```bash
cd nifi-edi-processors
pip install -e .
```

## Development

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run all tests
pytest

# Run specific test categories
pytest tests/edi_parser/          # Unit tests
pytest tests/test_validation_service.py  # Validation service tests

# Use the test runner script
python test_runner.py all         # Run all tests
python test_runner.py unit        # Run unit tests only
python test_runner.py verbose     # Verbose output
```

## Testing Framework

The project includes a comprehensive pytest-based testing framework that mirrors the robust testing approach used in the backend:

- **Unit Tests**: For isolated component testing
- **Integration Tests**: For testing component interactions
- **Format Tests**: For validating output formats (JSON, XML, CSV)
- **Edge Case Tests**: For error handling and boundary conditions

See [tests/README.md](tests/README.md) for detailed documentation on the testing framework.

## Processors

### EDI Validation Processor
- Validates EDI documents against schemas
- Supports tenant-specific schemas
- Configurable SNIP validation levels

### TA1 Generation Processor  
- Generates TA1 acknowledgments
- Routes based on validation results
- Supports forced generation

### EDI Parsing Processor
- Parses EDI into structured formats
- Multiple output formats (JSON, XML, CSV)
- Configurable segment filtering