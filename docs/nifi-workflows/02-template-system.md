# Template System

## Overview

Templates are reusable workflow definitions that provide structure and configuration schemas for creating workflows. They act as blueprints that users can instantiate with their specific configurations.

## Template Structure

```json
{
    "template_id": "sftp-edi-processor-v1.0",
    "name": "SFTP EDI File Processor",
    "description": "Monitors SFTP directories for EDI files and processes them",
    "category": "BATCH",
    "version": "1.0",
    "nifi_template_file": "sftp-edi-processor-v1.0.xml",
    "configuration_schema": {
        // JSON Schema for configuration validation
    },
    "metadata": {
        "author": "EDI Lens Team",
        "use_cases": [
            "Batch claims processing",
            "Daily remittance processing",
            "Bulk eligibility files"
        ],
        "supported_formats": ["837P", "835", "270", "271"]
    },
    "created_at": "2025-01-01T10:00:00Z",
    "updated_at": "2025-01-01T10:00:00Z"
}
```

## Template Categories

### BATCH
Templates for processing files from storage systems (SFTP, S3, local filesystem).

**Characteristics:**
- File-based triggers
- Asynchronous processing
- Bulk operations
- Archive and error handling

### REALTIME
Templates for processing individual transactions via HTTP endpoints.

**Characteristics:**
- HTTP-based triggers
- Synchronous processing
- Individual transactions
- Immediate responses

### TRANSFORMATION
Templates for converting between data formats.

**Characteristics:**
- Format conversion (JSON/CSV/XML ↔ EDI)
- Mapping rule configuration
- Validation of output
- Multiple delivery options

## Built-in Templates

### 1. SFTP EDI Processor (sftp-edi-processor-v1.0)

**Purpose**: Monitor SFTP directories for EDI files and process them with validation and acknowledgment generation.

**Configuration Schema**:
```json
{
    "type": "object",
    "required": ["input_path", "file_patterns", "validation", "output"],
    "properties": {
        "input_path": {
            "type": "string",
            "description": "SFTP directory to monitor",
            "pattern": "^/sftp/tenants/[^/]+/.+/$"
        },
        "file_patterns": {
            "type": "array",
            "items": {"type": "string"},
            "description": "File patterns to match (e.g., *.edi, *.x12)",
            "minItems": 1
        },
        "validation": {
            "type": "object",
            "required": ["schema"],
            "properties": {
                "schema": {
                    "type": "string",
                    "description": "EDI schema file for validation"
                },
                "snip_level": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 5,
                    "default": 3
                }
            }
        },
        "acknowledgments": {
            "type": "object",
            "properties": {
                "generate_ta1": {"type": "boolean", "default": true},
                "generate_999": {"type": "boolean", "default": false},
                "ta1_pattern": {
                    "type": "string",
                    "default": "{filename}_TA1_{timestamp}.edi"
                },
                "999_pattern": {
                    "type": "string", 
                    "default": "{filename}_999_{timestamp}.edi"
                }
            }
        },
        "output": {
            "type": "object",
            "required": ["success_path"],
            "properties": {
                "success_path": {"type": "string"},
                "error_path": {"type": "string"},
                "archive_path": {"type": "string"}
            }
        },
        "translation": {
            "type": "object",
            "properties": {
                "enabled": {"type": "boolean", "default": false},
                "target_format": {
                    "type": "string",
                    "enum": ["JSON", "XML", "CSV"]
                }
            }
        }
    }
}
```

### 2. HTTP EDI Processor (http-edi-processor-v1.0)

**Purpose**: Process EDI transactions via HTTP endpoints in real-time.

**Configuration Schema**:
```json
{
    "type": "object",
    "required": ["endpoint", "validation"],
    "properties": {
        "endpoint": {
            "type": "string",
            "description": "HTTP endpoint for processing requests",
            "pattern": "^/api/workflows/[^/]+/process$"
        },
        "timeout_seconds": {
            "type": "integer",
            "minimum": 5,
            "maximum": 300,
            "default": 30
        },
        "max_payload_size_mb": {
            "type": "integer",
            "minimum": 1,
            "maximum": 100,
            "default": 10
        },
        "validation": {
            "type": "object",
            "required": ["schema"],
            "properties": {
                "schema": {"type": "string"},
                "snip_level": {"type": "integer", "minimum": 1, "maximum": 5}
            }
        },
        "acknowledgments": {
            "type": "object",
            "properties": {
                "generate_ta1": {"type": "boolean", "default": true},
                "generate_999": {"type": "boolean", "default": false}
            }
        },
        "response": {
            "type": "object",
            "properties": {
                "format": {
                    "type": "string",
                    "enum": ["EDI", "JSON", "XML"]
                },
                "include_original": {"type": "boolean", "default": false},
                "include_acknowledgments": {"type": "boolean", "default": true}
            }
        }
    }
}
```

### 3. Format Converter (format-converter-v1.0)

**Purpose**: Convert between different data formats with configurable mapping rules.

**Configuration Schema**:
```json
{
    "type": "object",
    "required": ["input_format", "output_format", "mapping_rules"],
    "properties": {
        "input_format": {
            "type": "string",
            "enum": ["JSON", "CSV", "XML", "EDI"]
        },
        "output_format": {
            "type": "string",
            "enum": ["EDI_837P", "EDI_835", "EDI_270", "EDI_271", "JSON", "XML", "CSV"]
        },
        "mapping_rules": {
            "type": "object",
            "description": "Field mapping configuration",
            "additionalProperties": {"type": "string"}
        },
        "validation": {
            "type": "object",
            "properties": {
                "validate_input": {"type": "boolean", "default": true},
                "validate_output": {"type": "boolean", "default": true},
                "input_schema": {"type": "string"},
                "output_schema": {"type": "string"}
            }
        },
        "delivery": {
            "type": "object",
            "required": ["method"],
            "properties": {
                "method": {
                    "type": "string",
                    "enum": ["SFTP", "HTTP", "S3"]
                },
                "path": {"type": "string"},
                "endpoint": {"type": "string"}
            }
        }
    }
}
```

## Template Versioning

Templates use semantic versioning (MAJOR.MINOR.PATCH):

- **MAJOR**: Breaking changes to configuration schema
- **MINOR**: New features, backward-compatible changes
- **PATCH**: Bug fixes, minor improvements

Example progression:
- `sftp-edi-processor-v1.0` - Initial version
- `sftp-edi-processor-v1.1` - Added new optional configuration
- `sftp-edi-processor-v2.0` - Changed required fields

## NiFi Template Files

Each template references a NiFi template XML file that contains the actual processing logic.

**File Naming Convention**: `{template_id}.xml`

**Template Structure**:
```xml
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<template encoding-version="1.4">
    <description>SFTP EDI File Processor Template</description>
    <groupId>edi-lens-templates</groupId>
    <name>SFTP EDI Processor v1.0</name>
    <snippet>
        <processGroups>
            <!-- NiFi processors and connections -->
        </processGroups>
    </snippet>
</template>
```

**Parameter Placeholders**:
- `${INPUT_PATH}` - Replaced with configuration.input_path
- `${FILE_PATTERNS}` - Replaced with configuration.file_patterns
- `${VALIDATION_SCHEMA}` - Replaced with configuration.validation.schema
- `${TENANT_ID}` - Replaced with workflow.tenant_id

## Database Schema

```sql
CREATE TABLE workflow_templates (
    template_id VARCHAR PRIMARY KEY,
    name VARCHAR NOT NULL,
    description TEXT,
    category VARCHAR NOT NULL,
    version VARCHAR DEFAULT '1.0',
    nifi_template_file VARCHAR NOT NULL,
    configuration_schema JSONB NOT NULL,
    metadata JSONB,
    status VARCHAR DEFAULT 'ACTIVE',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_templates_category ON workflow_templates(category);
CREATE INDEX idx_templates_status ON workflow_templates(status);
```

## Template Management APIs

### List Templates
```http
GET /api/v1/templates?category=BATCH&status=ACTIVE
```

### Get Template Details
```http
GET /api/v1/templates/sftp-edi-processor-v1.0
```

### Validate Configuration
```http
POST /api/v1/templates/sftp-edi-processor-v1.0/validate
Content-Type: application/json

{
    "input_path": "/sftp/tenants/tenant-a/claims/in/",
    "file_patterns": ["*.edi"],
    "validation": {
        "schema": "837.5010.X222.A1.json"
    }
}
```

## Template Development Workflow

### 1. Design Phase
- Define template purpose and use cases
- Identify configuration parameters
- Design NiFi processing flow

### 2. Implementation Phase
- Create NiFi template with parameterized processors
- Define JSON configuration schema
- Write template metadata

### 3. Testing Phase
- Test NiFi template with various configurations
- Validate schema enforcement
- Test edge cases and error handling

### 4. Deployment Phase
- Register template in database
- Deploy NiFi template file
- Update documentation

## Custom Template Development

Organizations can create custom templates by:

1. **Designing NiFi Flow**: Create processing logic in NiFi
2. **Adding Parameters**: Use variables for configurable values
3. **Exporting Template**: Export as XML template
4. **Creating Schema**: Define configuration schema
5. **Registering Template**: Add to template registry

**Example Custom Template Registration**:
```python
await template_service.register_template(
    template_id="custom-batch-processor-v1.0",
    name="Custom Batch Processor",
    description="Organization-specific batch processing logic",
    category="BATCH",
    nifi_template_file="custom-batch-processor-v1.0.xml",
    configuration_schema=custom_schema,
    metadata={
        "author": "Organization IT Team",
        "use_cases": ["Custom business logic"]
    }
)
```

This template system provides the foundation for flexible, reusable workflow creation while maintaining consistency and validation across all workflow instances.