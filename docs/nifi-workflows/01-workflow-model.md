# Workflow Model

## Workflow Entity Structure

Each workflow is an independent, template-driven processing unit with the following structure:

```json
{
    "workflow_id": "healthcare-claims-batch-001",
    "tenant_id": "tenant-a",
    "name": "Healthcare Claims Batch Processing",
    "description": "Processes 837P claims via SFTP with validation and TA1 generation",
    "tags": ["healthcare", "claims", "837p", "production"],
    "template_id": "sftp-edi-processor-v1.0",
    "status": "ACTIVE",
    "configuration": {
        // Template-specific configuration
    },
    "created_by": "user-123",
    "created_at": "2025-01-01T10:00:00Z",
    "updated_at": "2025-01-01T10:00:00Z"
}
```

## Core Properties

### Basic Identification
- **workflow_id**: Unique identifier (UUID)
- **tenant_id**: Tenant isolation
- **name**: Human-readable workflow name
- **description**: Detailed explanation of workflow purpose

### Organization
- **tags**: Array of strings for categorization and filtering
  - Examples: `["healthcare", "claims", "837p", "production"]`
  - Used for filtering in UI and API queries
  - No predefined taxonomy - user-defined

### Template Association
- **template_id**: References the workflow template
- **configuration**: Template-specific configuration object

### Status Management
- **status**: Current workflow state
  - `ACTIVE`: Running and processing
  - `PAUSED`: Temporarily disabled
  - `ERROR`: Requires attention

## Configuration Patterns

### SFTP Batch Processing Example
```json
{
    "template_id": "sftp-edi-processor-v1.0",
    "configuration": {
        "input_path": "/sftp/tenants/tenant-a/claims/in/",
        "file_patterns": ["*.edi", "*.x12"],
        "validation": {
            "schema": "837.5010.X222.A1.json",
            "snip_level": 3
        },
        "acknowledgments": {
            "generate_ta1": true,
            "generate_999": true,
            "ta1_pattern": "{filename}_TA1_{timestamp}.edi",
            "999_pattern": "{filename}_999_{timestamp}.edi"
        },
        "output": {
            "success_path": "/sftp/tenants/tenant-a/claims/out/",
            "error_path": "/sftp/tenants/tenant-a/claims/error/",
            "archive_path": "/sftp/tenants/tenant-a/claims/archive/"
        },
        "translation": {
            "enabled": false
        }
    }
}
```

### Real-time HTTP Processing Example
```json
{
    "template_id": "http-edi-processor-v1.0",
    "configuration": {
        "endpoint": "/api/workflows/realtime-eligibility-001/process",
        "listening_port": 8081,
        "timeout_seconds": 30,
        "max_payload_size_mb": 10,
        "validation": {
            "schema": "270.5010.X279.A1.json",
            "snip_level": 2
        },
        "acknowledgments": {
            "generate_ta1": true,
            "generate_999": false
        },
        "response": {
            "format": "JSON",
            "include_ta1": true,
            "include_999": false
        },
        "translation": {
            "enabled": false
        }
    }
}
```

**Key Differences**:
- **Batch**: Uses file monitoring, asynchronous processing with webhooks
- **Real-time**: Uses HTTP listener, synchronous processing with immediate response
- **API Endpoints**: `/validate-batch` vs `/validate-realtime`
- **Response Pattern**: Job creation + webhook vs immediate result

### Format Conversion Example
```json
{
    "template_id": "format-converter-v1.0",
    "configuration": {
        "input_format": "JSON",
        "output_format": "EDI_837P",
        "mapping_rules": {
            "patient.first_name": "NM1*IL*1*{value}",
            "patient.last_name": "NM1*IL*1*{previous}*{value}",
            "claim.amount": "CLM*{claim_id}*{value}"
        },
        "validation": {
            "validate_output": true,
            "schema": "837.5010.X222.A1.json"
        },
        "delivery": {
            "method": "SFTP",
            "path": "/sftp/tenants/tenant-a/converted/out/"
        }
    }
}
```

## Workflow Lifecycle

### Creation
1. User selects a template
2. User configures template parameters
3. Configuration is validated against template schema
4. Workflow is saved to database
5. NiFi process group is created and deployed
6. Workflow status set to `ACTIVE`

### Execution
- **Batch workflows**: Triggered by file events or schedule
- **Real-time workflows**: Triggered by HTTP requests
- **Transformation workflows**: Triggered by file upload or API call

### Management
- **Pause**: Stop processing temporarily
- **Resume**: Restart paused workflow
- **Update**: Modify configuration (requires redeployment)
- **Delete**: Remove workflow and associated NiFi process group

## Database Schema

```sql
CREATE TABLE workflows (
    workflow_id UUID PRIMARY KEY,
    tenant_id VARCHAR NOT NULL,
    name VARCHAR NOT NULL,
    description TEXT,
    tags TEXT[],
    template_id VARCHAR REFERENCES workflow_templates(template_id),
    configuration JSONB NOT NULL,
    status VARCHAR DEFAULT 'ACTIVE',
    created_by VARCHAR,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_workflows_tenant ON workflows(tenant_id);
CREATE INDEX idx_workflows_template ON workflows(template_id);
CREATE INDEX idx_workflows_tags ON workflows USING GIN(tags);
CREATE INDEX idx_workflows_status ON workflows(status);
```

## API Operations

### List Workflows
```http
GET /api/v1/workflows?tenant_id=tenant-a&tags=healthcare,production&template_id=sftp-edi-processor-v1.0
```

### Create Workflow
```http
POST /api/v1/workflows
Content-Type: application/json

{
    "name": "New Claims Processor",
    "description": "...",
    "tags": ["claims", "test"],
    "template_id": "sftp-edi-processor-v1.0",
    "configuration": {...}
}
```

### Update Workflow
```http
PUT /api/v1/workflows/{workflow_id}
Content-Type: application/json

{
    "name": "Updated Claims Processor",
    "configuration": {...}
}
```

### Control Workflow
```http
POST /api/v1/workflows/{workflow_id}/pause
POST /api/v1/workflows/{workflow_id}/resume
DELETE /api/v1/workflows/{workflow_id}
```

## Validation Rules

1. **Configuration must match template schema**
2. **Tenant isolation must be enforced**
3. **Unique workflow names within tenant** (optional)
4. **Valid file paths for SFTP workflows**
5. **Unique endpoints for real-time workflows**
6. **Schema references must exist**

## Best Practices

### Naming Conventions
- Use descriptive, business-focused names
- Include processing type (batch/realtime) if needed
- Version with suffixes when creating variants

### Tag Usage
- Include business domain: `healthcare`, `finance`, `logistics`
- Include processing type: `batch`, `realtime`, `transformation`
- Include environment: `dev`, `staging`, `production`
- Include data type: `837p`, `835`, `270`, `271`

### Configuration Management
- Use environment-specific paths
- Include error handling configurations
- Set appropriate timeouts for real-time workflows
- Configure proper acknowledgment patterns

This workflow model provides the foundation for flexible, template-driven EDI processing while maintaining simplicity and tenant isolation.