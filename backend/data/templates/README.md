# EDI Lens Workflow Templates

This directory contains workflow template definitions for EDI Lens. Templates are defined as YAML files and are loaded by the system at runtime.

## Directory Structure

```
templates/
├── builtin/                    # Built-in platform templates
│   ├── batch-edi-processor.yaml
│   ├── realtime-edi-processor.yaml
│   └── README.md
├── custom/                     # Custom user templates (future)
└── README.md                   # This file
```

## Built-in Templates

### 1. Batch EDI Processor (`batch-edi-processor.yaml`)
- **Purpose**: Monitors SFTP directories for file processing
- **Features**: 
  - SFTP file monitoring
  - Optional input/output format translation
  - EDI validation and acknowledgment generation
  - File archival and error handling
- **Category**: BATCH

### 2. Real-time EDI Processor (`realtime-edi-processor.yaml`)
- **Purpose**: HTTP endpoint for synchronous EDI processing
- **Features**:
  - HTTP listener for real-time requests
  - Optional input/output format translation
  - Real-time EDI validation and response
  - Authentication and authorization
- **Category**: REALTIME

## Template Structure

Each template YAML file contains:

```yaml
metadata:
  # Template identification and metadata
  template_id: "unique-template-id"
  name: "Human Readable Name"
  description: "Template description"
  category: "BATCH|REALTIME|TRANSFORMATION"
  # ... other metadata

flow_definition:
  # NiFi flow definition
  processors: []
  connections: []
  # ... NiFi components

configuration_schema:
  # JSON Schema for UI generation and validation
  type: "object"
  properties: {}
  # ... schema definition
```

## Translation Features

Both templates support configurable translation:

### Input Translation
- **Purpose**: Convert non-EDI formats (JSON, XML, CSV) to EDI before processing
- **Configuration**: `translation.input_translation.enabled`
- **Use Case**: Accept JSON payloads and convert to EDI for validation

### Output Translation  
- **Purpose**: Convert processed EDI to other formats (JSON, XML, CSV)
- **Configuration**: `translation.output_translation.enabled`
- **Use Case**: Return JSON responses instead of raw EDI

### Example Configuration

```yaml
# EDI-only processing (no translation)
translation:
  input_translation:
    enabled: false
  output_translation:
    enabled: false

# JSON input, EDI processing, JSON output
translation:
  input_translation:
    enabled: true
    source_format: "JSON"
    mapping_rules: {...}
  output_translation:
    enabled: true
    target_format: "JSON"
    mapping_rules: {...}
```

## Template Loading

Templates are loaded by the `BuiltInTemplatesService` at application startup:

1. Service scans `backend/data/templates/builtin/` directory
2. Parses YAML files into template objects
3. Validates template structure and schemas
4. Seeds templates into database if not already present
5. Registers templates with NiFi Registry

## Adding New Templates

To add a new built-in template:

1. Create a new YAML file in `builtin/` directory
2. Follow the existing template structure
3. Restart the application to load the new template
4. The template will be automatically seeded and registered

## Version Management

- Template versions are managed through the `metadata.version` field
- Updating a template version will create a new version in the database
- Old versions are preserved for rollback capabilities

## Testing

Templates can be tested using the integration test framework:

```bash
# Test template loading and seeding
./run.sh dev:test integration -k test_template_seeding

# Test template deployment to NiFi
./run.sh dev:test integration -k test_template_deployment
```