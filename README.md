# EDI Parser

A lightweight Python library for parsing EDI (Electronic Data Interchange) files to JSON.

## Description

This library converts X12 EDI files into structured JSON format. It supports schema validation, TA1 acknowledgment generation, and processes 30,000+ segments per second with minimal dependencies.

## Run Tests

```bash
python -m pytest tests/ -v
```

## Usage

### Command Line Tool

```bash
# Parse sample file (uses sample_837p.edi)
python main.py

# Parse specific file to JSON
python main.py input.edi

# Parse to specific output file
python main.py input.edi output.json

# Use custom schema
python main.py input.edi output.json custom_schema.json

# Show help
python main.py --help
```

### Use in Python Code

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from edi_parser import EdiParser
from validation_service import EDIValidationService
from edi_schema_models import ImplementationGuideSchema
import json

# Load schema
def load_schema(schema_path):
    with open(schema_path, 'r') as f:
        schema_data = json.load(f)
    return ImplementationGuideSchema.model_validate(schema_data)

# Parse EDI to JSON
schema = load_schema('src/schemas/837.5010.X222.A1.json')
with open('sample_837p.edi', 'r') as f:
    edi_content = f.read()

parser = EdiParser(edi_string=edi_content, schema=schema)
result = parser.parse()
json_output = result.model_dump_json(indent=2)
print(json_output)

# Validate EDI
validator = EDIValidationService(schema_base_path="src/schemas")
validation_result = validator.validate_edi(edi_content, "837.5010.X222.A1.json")
print(f"Valid: {validation_result.valid}")
```