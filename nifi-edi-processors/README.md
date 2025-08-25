# NiFi EDI Processors

Production-ready EDI processing components for Apache NiFi with native Python implementation.

## 🚀 Quick Start

### Deploy to Running NiFi Instance

```bash
# Deploy processors using the automation script
./scripts/nifi-automation/nifi-automation deploy-processors volume

# Or use the complete setup (includes environment setup)
./scripts/nifi-automation/nifi-automation setup
```

### Test the Setup

```bash
# Run all 130 unit tests
./run.sh dev:test unit:edi

# Deploy and test a flow
./scripts/nifi-automation/nifi-automation deploy edi-validation-flow
./scripts/nifi-automation/nifi-automation test edi-validation-flow
```

## 📁 Project Structure

```
nifi-edi-processors/
├── Core Processors (NiFi Components)
│   ├── edi_validation_processor.py    # Schema-based EDI validation
│   ├── edi_parsing_processor.py       # Multi-format EDI parsing (JSON/XML/CSV)
│   └── ta1_generation_processor.py    # Automatic TA1 acknowledgment generation
├── Supporting Modules
│   ├── edi_parser.py                  # Core EDI parsing engine
│   ├── validation_service.py          # EDI validation service
│   ├── schema_manager.py              # Schema loading and caching
│   ├── edi_schema_models.py           # Schema data models
│   ├── ta1_generator.py               # TA1 generation logic
│   ├── ta1_validator.py               # TA1 validation
│   ├── ta1_defs.py                    # TA1 definitions and constants
│   └── cdm.py                         # Common Data Model structures
├── Resources
│   ├── schemas/                       # EDI implementation guide schemas
│   │   └── 837.5010.X222.A1.json     # Sample 837P schema
│   └── __init__.py                    # Python package initialization
├── Tests (130+ comprehensive tests)
│   ├── tests/edi_parser/              # EDI parser tests
│   ├── tests/test_validation_service.py
│   ├── tests/test_ta1_generator.py
│   └── ...                           # Additional test modules
└── Configuration
    ├── pyproject.toml                 # Python project configuration
    └── pytest.ini                    # Test configuration
```

## ✨ Features

### 🔧 **Native Python Processing**
- **No external dependencies** - Runs entirely within NiFi's Python environment
- **High performance** - 30,000+ segments/second throughput
- **Memory efficient** - Streaming parser with minimal memory footprint

### 🏢 **Enterprise Ready**
- **Multi-tenant support** - Tenant isolation and schema management
- **Production tested** - Comprehensive test suite with 130+ tests
- **NiFi clustering support** - Built for scalable deployments
- **Hot reload capability** - Development-friendly volume mounting

### 📊 **Multiple Output Formats**
- **JSON** - Structured data for APIs and databases
- **XML** - Legacy system integration
- **CSV** - Analytics and reporting
- **Metadata extraction** - Transaction counts, totals, dates

### 🛡️ **Comprehensive Error Handling**
- **Detailed validation reporting** - Field-level error details
- **TA1 acknowledgments** - Automatic response generation
- **Error isolation** - Continue processing despite individual transaction errors
- **Audit trails** - Complete processing history

## 🎯 Processor Overview

### 1. EDI Validation Processor (`edi_validation_processor.py`)
**Purpose**: Validates EDI documents against implementation guide schemas

**Properties**:
- `Validation Schema` - EDI schema file (e.g., "837.5010.X222.A1.json")
- `SNIP Level` - Validation strictness (1-5, where 5 is most strict)
- `Tenant ID` - Multi-tenant identifier
- `Schema Base Path` - Directory containing schemas
- `Cache Schemas` - Enable schema caching for performance

**Relationships**:
- `success` → Valid EDI with validation results
- `failure` → Invalid EDI or processing errors

**Output**: JSON with validation results and detailed findings

### 2. EDI Parsing Processor (`edi_parsing_processor.py`)
**Purpose**: Converts EDI to structured formats (JSON/XML/CSV)

**Properties**:
- `Output Format` - JSON, XML, or CSV
- `Schema` - EDI schema for parsing guidance  
- `Tenant ID` - Multi-tenant identifier
- `Include Metadata` - Add transaction counts, totals, etc.

**Relationships**:
- `success` → Successfully parsed EDI
- `failure` → Parsing errors or invalid EDI

**Output**: Structured data in specified format with optional metadata

### 3. TA1 Generation Processor (`ta1_generation_processor.py`)
**Purpose**: Generates TA1 acknowledgment responses

**Properties**:
- `Force TA1 Generation` - Generate TA1 even if not requested
- `TA1 Control Number Strategy` - How to assign control numbers

**Relationships**:
- `ta1` → Generated TA1 acknowledgment
- `original` → Original EDI (when TA1 not needed)
- `failure` → Processing errors

**Output**: TA1 EDI document or original passthrough

## 🔄 Typical Workflows

### Basic Validation Flow
```
GetFile → EDI Validation → LogMessage → PutFile
                      ↓
                   PutFile (failures)
```

### Complete Processing Pipeline
```
GetFile → EDI Validation → TA1 Generation → EDI Parsing → PutFile
                      ↓              ↓              ↓
                   PutFile      PutFile         PutFile
                 (failures)   (TA1 responses)  (parsed data)
```

## 🧪 Testing

### Run Tests
```bash
# All EDI processor tests (130+ tests)
./run.sh dev:test unit:edi

# All tests (backend + EDI processors)  
./run.sh dev:test unit:all

# Direct pytest execution
cd nifi-edi-processors && python -m pytest tests/ -v
```

### Test Coverage
- **EDI Parser Tests**: 90+ tests covering edge cases, syntax rules, envelope validation
- **Validation Service Tests**: Schema validation, error handling, multi-tenant scenarios
- **TA1 Generation Tests**: Acknowledgment logic, error codes, control numbers
- **Processor Interface Tests**: NiFi integration, property validation, relationship handling
- **Integration Tests**: End-to-end workflow validation

## 📦 Deployment Options

### 1. Volume Mount (Development - Hot Reload)
```bash
./scripts/nifi-automation/nifi-automation deploy-processors volume
```
- Changes reflected immediately
- No container rebuild needed
- Ideal for development

### 2. Docker Build (Production)
```bash
docker build -f docker/nifi-processors/Dockerfile.extension -t nifi-edi:latest .
```
- Immutable deployments
- Production ready
- Container-based distribution

## 🔧 Configuration

### Schema Management
- Schemas stored in `schemas/` directory
- Support for tenant-specific schema overrides
- Automatic schema caching for performance
- JSON-based implementation guide schemas

### Multi-Tenant Support
```yaml
# Schema resolution order:
# 1. /schemas/{tenant_id}/{schema_name}
# 2. /schemas/{schema_name} (fallback)
```

### Performance Tuning
```yaml
Properties:
  Cache Schemas: true        # Enable schema caching
  SNIP Level: 3             # Balance validation vs performance
  Batch Size: 10            # Process multiple files per batch
```

## 🔗 Integration

### With EDI Lens Backend
- Shared schema definitions
- Common validation logic
- Consistent error reporting

### With NiFi Ecosystem
- Standard NiFi processor interface
- Expression language support
- Flow file attributes for routing
- Provenance and lineage tracking

## 📚 Additional Resources

- **NiFi Automation**: See `scripts/nifi-automation/README.md`
- **Docker Setup**: See `docker/nifi-processors/`
- **Flow Examples**: See `scripts/nifi-automation/flows/`
- **Troubleshooting**: See `scripts/nifi-automation/docs/TROUBLESHOOTING.md`

## 🎯 Next Steps

1. **Deploy processors**: `./scripts/nifi-automation/nifi-automation setup`
2. **Create flows**: Use the automation scripts to deploy predefined flows
3. **Custom workflows**: Build custom NiFi flows using the processors
4. **Production deployment**: Use Docker builds for production environments

---

*Built with ❤️ for high-performance EDI processing in Apache NiFi*