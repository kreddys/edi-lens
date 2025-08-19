# Testing Framework for NiFi EDI Processors

This directory contains a comprehensive pytest-based testing framework for the NiFi EDI processors, mirroring the robust testing approach used in the backend.

## Test Organization

The tests are organized into the following categories:

### Unit Tests (`tests/edi_parser/`)
- **test_edi_parser.py**: Basic parser functionality tests
- **test_edi_parser_837p.py**: 837P-specific parsing tests
- **test_edi_parser_complex_structures.py**: Tests for complex EDI structures
- **test_edi_parser_edge_cases.py**: Edge case and error handling tests
- **test_edi_parser_syntax_rules.py**: Syntax rule validation tests

### Integration Tests (`tests/`)
- **test_validation_service.py**: EDI validation service tests
- **test_integrated_workflow.py**: Complete workflow integration tests
- **test_parsing_formats.py**: Multi-format parsing output tests

## Running Tests

### Run All Tests
```bash
cd nifi-edi-processors
pytest
```

### Run Specific Test Categories
```bash
# Run only unit tests
pytest tests/edi_parser/

# Run only integration tests
pytest tests/test_validation_service.py tests/test_integrated_workflow.py

# Run only format tests
pytest tests/test_parsing_formats.py
```

### Run Tests with Verbose Output
```bash
pytest -v
```

### Run Tests with Coverage
```bash
pytest --cov=edi_common --cov=processors --cov-report=html
```

## Test Markers

The tests use the following markers:

- `@pytest.mark.unit`: Pure unit tests with no external dependencies
- `@pytest.mark.integration`: Tests requiring external services or complex setups
- `@pytest.mark.format`: Tests for specific output format validation

## Test Fixtures

### Shared Fixtures (`tests/conftest.py`)
- `standalone_schema`: Loads the 837P schema for unit tests
- `valid_837p_edi_string`: Provides a compliant 837P EDI string
- `edi_with_ack_requested`: EDI with TA1 acknowledgment requested
- `edi_with_isa_error`: EDI with ISA/IEA control number mismatch
- `complex_837p_edi_string`: Complex 837P structure with multiple subscribers/claims

## Configuration

The testing framework is configured through:

- `pytest.ini`: Main pytest configuration
- `pyproject.toml`: Project dependencies and pytest settings

## Development Workflow

1. **Write tests first**: Follow TDD practices when adding new functionality
2. **Use appropriate markers**: Tag tests with the correct category
3. **Leverage fixtures**: Use shared fixtures for common test data
4. **Mock external dependencies**: Use unittest.mock for isolating units under test
5. **Test edge cases**: Include tests for error conditions and boundary cases

## Test Coverage

The current test suite provides coverage for:

- Basic EDI parsing functionality
- 837P healthcare claim processing
- Complex EDI structures with multiple subscribers and claims
- Error handling and edge cases
- TA1 acknowledgment generation
- Multi-format output (JSON, XML, CSV)
- Integration between components
- Validation service functionality