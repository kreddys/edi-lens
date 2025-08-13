# API Specifications

## Overview

This document defines the API specifications for the NiFi workflow architecture. The APIs are designed to support both the Admin UI and NiFi processor interactions, with a focus on performance, security, and multi-tenancy.

## Authentication & Authorization

All APIs require authentication via JWT tokens issued by Keycloak.

**Headers**:
```http
Authorization: Bearer {jwt_token}
Content-Type: application/json
X-Tenant-ID: {tenant_id}  # Required for tenant isolation
```

**Scopes**:
- `workflow:read` - View workflows and templates
- `workflow:write` - Create and modify workflows
- `workflow:admin` - Advanced workflow management
- `edi:process` - Process EDI content (for NiFi service account)

## Template Management APIs

### List Templates

```http
GET /api/v1/templates
```

**Query Parameters**:
- `category` (optional): Filter by template category (BATCH, REALTIME, TRANSFORMATION)
- `status` (optional): Filter by template status (ACTIVE, DEPRECATED)

**Response**:
```json
{
    "templates": [
        {
            "template_id": "sftp-edi-processor-v1.0",
            "name": "SFTP EDI File Processor",
            "description": "Monitors SFTP directories for EDI files and processes them",
            "category": "BATCH",
            "version": "1.0",
            "status": "ACTIVE",
            "metadata": {
                "use_cases": ["Batch claims processing", "Daily remittance processing"],
                "supported_formats": ["837P", "835", "270", "271"]
            }
        }
    ],
    "total": 3
}
```

### Get Template Details

```http
GET /api/v1/templates/{template_id}
```

**Response**:
```json
{
    "template_id": "sftp-edi-processor-v1.0",
    "name": "SFTP EDI File Processor",
    "description": "Monitors SFTP directories for EDI files and processes them",
    "category": "BATCH",
    "version": "1.0",
    "status": "ACTIVE",
    "configuration_schema": {
        "type": "object",
        "required": ["input_path", "file_patterns", "validation"],
        "properties": {
            "input_path": {
                "type": "string",
                "description": "SFTP directory to monitor"
            }
        }
    },
    "metadata": {
        "author": "EDI Lens Team",
        "use_cases": ["Batch claims processing"],
        "supported_formats": ["837P", "835"]
    }
}
```

### Validate Configuration

```http
POST /api/v1/templates/{template_id}/validate
```

**Request Body**:
```json
{
    "input_path": "/sftp/tenants/tenant-a/claims/in/",
    "file_patterns": ["*.edi", "*.x12"],
    "validation": {
        "schema": "837.5010.X222.A1.json",
        "snip_level": 3
    }
}
```

**Response**:
```json
{
    "valid": true,
    "errors": []
}
```

**Error Response**:
```json
{
    "valid": false,
    "errors": [
        {
            "field": "input_path",
            "message": "Path must start with /sftp/tenants/{tenant_id}/"
        }
    ]
}
```

## Workflow Management APIs

### List Workflows

```http
GET /api/v1/workflows
```

**Query Parameters**:
- `tenant_id` (required): Tenant identifier
- `tags` (optional): Comma-separated list of tags to filter by
- `template_id` (optional): Filter by template ID
- `status` (optional): Filter by workflow status
- `limit` (optional): Number of results to return (default: 50)
- `offset` (optional): Offset for pagination (default: 0)

**Response**:
```json
{
    "workflows": [
        {
            "workflow_id": "healthcare-claims-batch-001",
            "tenant_id": "tenant-a",
            "name": "Healthcare Claims Batch Processing",
            "description": "Processes 837P claims via SFTP with validation and TA1 generation",
            "tags": ["healthcare", "claims", "837p", "production"],
            "template_id": "sftp-edi-processor-v1.0",
            "status": "ACTIVE",
            "created_by": "user-123",
            "created_at": "2025-01-01T10:00:00Z",
            "updated_at": "2025-01-01T10:00:00Z"
        }
    ],
    "total": 15,
    "limit": 50,
    "offset": 0
}
```

### Get Workflow Details

```http
GET /api/v1/workflows/{workflow_id}
```

**Response**:
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
        "input_path": "/sftp/tenants/tenant-a/claims/in/",
        "file_patterns": ["*.edi", "*.x12"],
        "validation": {
            "schema": "837.5010.X222.A1.json",
            "snip_level": 3
        },
        "acknowledgments": {
            "generate_ta1": true,
            "generate_999": true
        },
        "output": {
            "success_path": "/sftp/tenants/tenant-a/claims/out/",
            "error_path": "/sftp/tenants/tenant-a/claims/error/"
        }
    },
    "nifi_process_group_id": "process-group-uuid",
    "created_by": "user-123",
    "created_at": "2025-01-01T10:00:00Z",
    "updated_at": "2025-01-01T10:00:00Z"
}
```

### Create Workflow

```http
POST /api/v1/workflows
```

**Request Body**:
```json
{
    "name": "New Claims Processor",
    "description": "Processes healthcare claims for tenant-a",
    "tags": ["healthcare", "claims", "test"],
    "template_id": "sftp-edi-processor-v1.0",
    "configuration": {
        "input_path": "/sftp/tenants/tenant-a/claims/in/",
        "file_patterns": ["*.edi"],
        "validation": {
            "schema": "837.5010.X222.A1.json",
            "snip_level": 3
        },
        "acknowledgments": {
            "generate_ta1": true,
            "generate_999": false
        },
        "output": {
            "success_path": "/sftp/tenants/tenant-a/claims/out/"
        }
    }
}
```

**Response**:
```json
{
    "workflow_id": "new-workflow-uuid",
    "status": "ACTIVE",
    "nifi_process_group_id": "process-group-uuid",
    "created_at": "2025-01-01T11:00:00Z"
}
```

### Update Workflow

```http
PUT /api/v1/workflows/{workflow_id}
```

**Request Body** (same as create, all fields optional):
```json
{
    "name": "Updated Claims Processor",
    "description": "Updated description",
    "tags": ["healthcare", "claims", "production"],
    "configuration": {
        "input_path": "/sftp/tenants/tenant-a/claims/in/",
        "file_patterns": ["*.edi", "*.x12"]
    }
}
```

**Response**:
```json
{
    "workflow_id": "workflow-uuid",
    "status": "ACTIVE",
    "updated_at": "2025-01-01T12:00:00Z",
    "nifi_redeployment_required": true
}
```

### Delete Workflow

```http
DELETE /api/v1/workflows/{workflow_id}
```

**Response**:
```json
{
    "workflow_id": "workflow-uuid",
    "status": "DELETED",
    "nifi_process_group_removed": true,
    "deleted_at": "2025-01-01T13:00:00Z"
}
```

### Workflow Control Operations

#### Pause Workflow
```http
POST /api/v1/workflows/{workflow_id}/pause
```

#### Resume Workflow
```http
POST /api/v1/workflows/{workflow_id}/resume
```

#### Restart Workflow
```http
POST /api/v1/workflows/{workflow_id}/restart
```

**Standard Response for Control Operations**:
```json
{
    "workflow_id": "workflow-uuid",
    "action": "pause|resume|restart",
    "status": "PAUSED|ACTIVE|RESTARTING",
    "nifi_status": "STOPPED|RUNNING|STARTING",
    "timestamp": "2025-01-01T14:00:00Z"
}
```

## EDI Processing APIs (for NiFi)

These APIs are optimized for NiFi processor interactions and include batch processing capabilities.

### Single EDI Validation

```http
POST /api/v1/edi/validate-single
```

**Request Body**:
```json
{
    "edi_content": "ISA*00*          *00*          *ZZ*...",
    "tenant_id": "tenant-a",
    "workflow_id": "workflow-123",
    "validation_schema": "837.5010.X222.A1.json",
    "snip_level": 3,
    "file_name": "claims_20250101.edi"
}
```

**Response**:
```json
{
    "valid": true,
    "validation_results": [
        {
            "level": "warning",
            "code": "W001",
            "message": "Optional element missing",
            "location": {
                "segment": "NM1",
                "element": "04"
            }
        }
    ],
    "processing_time_ms": 150,
    "schema_used": "837.5010.X222.A1.json",
    "snip_level_used": 3
}
```

### Batch EDI Validation

```http
POST /api/v1/edi/validate-batch
```

**Request Body**:
```json
{
    "requests": [
        {
            "request_id": "req-1",
            "edi_content": "ISA*00*...",
            "tenant_id": "tenant-a",
            "workflow_id": "workflow-123",
            "validation_schema": "837.5010.X222.A1.json",
            "file_name": "file1.edi"
        },
        {
            "request_id": "req-2",
            "edi_content": "ISA*00*...",
            "tenant_id": "tenant-a",
            "workflow_id": "workflow-123",
            "validation_schema": "835.5010.X221.A1.json",
            "file_name": "file2.edi"
        }
    ]
}
```

**Response**:
```json
{
    "results": [
        {
            "request_id": "req-1",
            "valid": true,
            "validation_results": [...],
            "processing_time_ms": 150
        },
        {
            "request_id": "req-2",
            "valid": false,
            "validation_results": [...],
            "processing_time_ms": 120
        }
    ],
    "total_processing_time_ms": 270
}
```

### Generate Acknowledgments

```http
POST /api/v1/edi/generate-acknowledgments
```

**Request Body**:
```json
{
    "edi_content": "ISA*00*...",
    "tenant_id": "tenant-a",
    "workflow_id": "workflow-123",
    "generate_ta1": true,
    "generate_999": false,
    "validation_errors": [
        {
            "level": "error",
            "code": "E001",
            "message": "Required element missing"
        }
    ],
    "file_name": "claims_20250101.edi"
}
```

**Response**:
```json
{
    "ta1_acknowledgment": "ISA*00*          *00*          *ZZ*...",
    "ack999_acknowledgment": null,
    "acknowledgment_status": "A",
    "error_code": null,
    "processing_time_ms": 50
}
```

### Format Transformation

```http
POST /api/v1/edi/transform
```

**Request Body**:
```json
{
    "input_content": "{\"patient\": {\"firstName\": \"John\"}}",
    "input_format": "JSON",
    "output_format": "EDI_837P",
    "mapping_rules": {
        "patient.firstName": "NM1*IL*1*{value}",
        "patient.lastName": "NM1*IL*1*{previous}*{value}"
    },
    "tenant_id": "tenant-a",
    "workflow_id": "workflow-123"
}
```

**Response**:
```json
{
    "output_content": "ISA*00*...",
    "output_format": "EDI_837P",
    "validation_results": [...],
    "processing_time_ms": 200
}
```

## Workflow Execution APIs

### Real-time Processing Endpoint

```http
POST /api/workflows/{workflow_id}/process
```

**Request Body**:
```json
{
    "edi_content": "ISA*00*...",
    "request_id": "client-request-123"
}
```

**Response**:
```json
{
    "valid": true,
    "validation_results": [...],
    "ta1_acknowledgment": "ISA*00*...",
    "ack999_acknowledgment": null,
    "processing_time_ms": 180,
    "request_id": "client-request-123",
    "workflow_id": "workflow-123"
}
```

### Batch Job Status

```http
GET /api/v1/workflows/{workflow_id}/jobs/{job_id}
```

**Response**:
```json
{
    "job_id": "job-uuid",
    "workflow_id": "workflow-123",
    "status": "COMPLETED",
    "file_name": "claims_20250101.edi",
    "started_at": "2025-01-01T10:00:00Z",
    "completed_at": "2025-01-01T10:02:30Z",
    "processing_time_ms": 150000,
    "results": {
        "files_processed": 1,
        "validation_status": "VALID",
        "acknowledgments_generated": ["TA1"],
        "output_files": [
            "/sftp/tenants/tenant-a/claims/out/claims_20250101_TA1_20250101102030.edi"
        ]
    },
    "errors": []
}
```

## Monitoring & Metrics APIs

### Workflow Metrics

```http
GET /api/v1/workflows/{workflow_id}/metrics
```

**Query Parameters**:
- `from` (optional): Start date (ISO 8601)
- `to` (optional): End date (ISO 8601)
- `granularity` (optional): hour, day, week (default: day)

**Response**:
```json
{
    "workflow_id": "workflow-123",
    "period": {
        "from": "2025-01-01T00:00:00Z",
        "to": "2025-01-02T00:00:00Z"
    },
    "metrics": {
        "files_processed": 150,
        "processing_time_avg_ms": 2500,
        "processing_time_p95_ms": 4200,
        "success_rate": 0.987,
        "error_rate": 0.013,
        "throughput_files_per_hour": 6.25
    }
}
```

### System Health

```http
GET /api/v1/health
```

**Response**:
```json
{
    "status": "healthy",
    "timestamp": "2025-01-01T15:00:00Z",
    "services": {
        "database": "healthy",
        "nifi": "healthy",
        "keycloak": "healthy",
        "storage": "healthy"
    },
    "version": "2.0.0"
}
```

## Error Handling

### Standard Error Response Format

```json
{
    "error": {
        "code": "VALIDATION_ERROR",
        "message": "Configuration validation failed",
        "details": {
            "field": "input_path",
            "reason": "Path must be within tenant directory"
        },
        "timestamp": "2025-01-01T15:00:00Z",
        "request_id": "req-uuid"
    }
}
```

### Common Error Codes

- `VALIDATION_ERROR` - Configuration or input validation failed
- `TEMPLATE_NOT_FOUND` - Specified template does not exist
- `WORKFLOW_NOT_FOUND` - Specified workflow does not exist
- `PERMISSION_DENIED` - Insufficient permissions for operation
- `TENANT_ISOLATION_VIOLATION` - Attempt to access resources outside tenant
- `NIFI_DEPLOYMENT_ERROR` - Error deploying to NiFi
- `PROCESSING_ERROR` - Error during EDI processing
- `RATE_LIMIT_EXCEEDED` - Too many requests

### HTTP Status Codes

- `200` - Success
- `201` - Created (for POST operations)
- `400` - Bad Request (validation errors)
- `401` - Unauthorized (authentication required)
- `403` - Forbidden (insufficient permissions)
- `404` - Not Found
- `409` - Conflict (resource already exists)
- `429` - Too Many Requests (rate limiting)
- `500` - Internal Server Error
- `503` - Service Unavailable (dependent service down)

## Rate Limiting

APIs are rate-limited based on tenant and endpoint:

**Headers in Response**:
```http
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1640995200
```

**Rate Limits**:
- Template APIs: 100 requests/minute per tenant
- Workflow Management: 200 requests/minute per tenant
- EDI Processing: 1000 requests/minute per tenant
- Real-time Processing: 100 requests/minute per workflow

This API specification provides a comprehensive foundation for both Admin UI interactions and NiFi processor integrations while maintaining security, performance, and multi-tenancy requirements.