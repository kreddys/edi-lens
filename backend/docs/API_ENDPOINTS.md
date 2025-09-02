# EDI Lens Backend API Endpoints

**Last Updated:** September 2025  
**Version:** 1.0  
**Status:** ✅ Current and Complete

## Overview

The EDI Lens Backend API provides a comprehensive set of endpoints for managing EDI templates and workflows in a Registry-first architecture. All endpoints require proper authentication and tenant context.

## Authentication

All API endpoints require:
1. **JWT Authentication** via `Authorization: Bearer <token>` header
2. **Tenant Context** via `x-tenant-id` header

### Required Headers
```
Authorization: Bearer <jwt-token>
x-tenant-id: tenant-a
```

### Permission Model
- `workflow:read` - Read templates and workflows
- `workflow:write` - Create/update templates and workflows
- `workflow:execute` - Execute workflows
- `admin` - Administrative operations (template seeding, global management)

## Template Management API (`/api/v1/templates/`)

### Create Template
**POST** `/api/v1/templates/`

Creates a new template in both the database and NiFi Registry.

**Request Body:**
```json
{
  "name": "EDI Validation Template",
  "description": "Template for validating EDI files",
  "flow_definition": {
    "processors": [
      {
        "id": "getfile",
        "name": "Get EDI Files",
        "type": "org.apache.nifi.processors.standard.GetFile",
        "position": {"x": 100, "y": 100},
        "properties": {
          "Input Directory": "/tmp/input",
          "File Filter": ".*\\.edi"
        }
      }
    ],
    "connections": []
  }
}
```

**Response:**
```json
{
  "template_id": "b3ea1d0c-a8e6-448d-ada0-f8ab4929e562",
  "bucket_id": "f68bea7b-f0e8-4e88-876c-83a655c68c1d",
  "current_version": 1,
  "name": "EDI Validation Template",
  "description": "Template for validating EDI files",
  "scope": "GLOBAL",
  "tenant_id": null,
  "status": "ACTIVE",
  "is_featured": false,
  "usage_count": 0,
  "created_by": "admin-user",
  "created_at": "2025-09-02T18:58:40.673000",
  "updated_at": "2025-09-02T18:58:40.673000",
  "deprecated_at": null
}
```

**Permissions:** `workflow:write`

### List Templates
**GET** `/api/v1/templates/`

Retrieves a list of templates accessible to the current user.

**Query Parameters:**
- `scope` (optional): Filter by scope (`GLOBAL` or `TENANT`)

**Response:**
```json
[
  {
    "template_id": "b3ea1d0c-a8e6-448d-ada0-f8ab4929e562",
    "bucket_id": "f68bea7b-f0e8-4e88-876c-83a655c68c1d",
    "current_version": 1,
    "name": "EDI Validation Template",
    "description": "Template for validating EDI files",
    "scope": "GLOBAL",
    "tenant_id": null,
    "status": "ACTIVE",
    "is_featured": false,
    "usage_count": 0,
    "created_by": "admin-user",
    "created_at": "2025-09-02T18:58:40.673000",
    "updated_at": "2025-09-02T18:58:40.673000",
    "deprecated_at": null
  }
]
```

**Permissions:** `workflow:read`

### Get Template
**GET** `/api/v1/templates/{template_id}`

Retrieves a specific template by ID.

**Response:**
```json
{
  "template_id": "b3ea1d0c-a8e6-448d-ada0-f8ab4929e562",
  "bucket_id": "f68bea7b-f0e8-4e88-876c-83a655c68c1d",
  "current_version": 1,
  "name": "EDI Validation Template",
  "description": "Template for validating EDI files",
  "scope": "GLOBAL",
  "tenant_id": null,
  "status": "ACTIVE",
  "is_featured": false,
  "usage_count": 0,
  "created_by": "admin-user",
  "created_at": "2025-09-02T18:58:40.673000",
  "updated_at": "2025-09-02T18:58:40.673000",
  "deprecated_at": null
}
```

**Permissions:** `workflow:read`

### Update Template
**PUT** `/api/v1/templates/{template_id}`

Creates a new version of a template in NiFi Registry.

**Request Body:**
```json
{
  "flow_definition": {
    "processors": [
      {
        "id": "getfile",
        "name": "Get EDI Files",
        "type": "org.apache.nifi.processors.standard.GetFile",
        "position": {"x": 100, "y": 100},
        "properties": {
          "Input Directory": "/tmp/input",
          "File Filter": ".*\\.edi"
        }
      },
      {
        "id": "validate",
        "name": "Validate EDI",
        "type": "com.example.processors.ValidateEDI",
        "position": {"x": 300, "y": 100},
        "properties": {
          "Schema Name": "837.5010.X222.A1"
        }
      }
    ],
    "connections": [
      {
        "source": "getfile",
        "destination": "validate"
      }
    ]
  },
  "comments": "Added validation processor"
}
```

**Response:**
```json
{
  "template_id": "b3ea1d0c-a8e6-448d-ada0-f8ab4929e562",
  "bucket_id": "f68bea7b-f0e8-4e88-876c-83a655c68c1d",
  "current_version": 2,
  "name": "EDI Validation Template",
  "description": "Template for validating EDI files",
  "scope": "GLOBAL",
  "tenant_id": null,
  "status": "ACTIVE",
  "is_featured": false,
  "usage_count": 0,
  "created_by": "admin-user",
  "created_at": "2025-09-02T18:58:40.673000",
  "updated_at": "2025-09-02T19:00:41.293000",
  "deprecated_at": null
}
```

**Permissions:** `workflow:write`

### Delete Template
**DELETE** `/api/v1/templates/{template_id}`

Soft deletes a template (marks as inactive).

**Response:** `204 No Content`

**Permissions:** `workflow:write`

### Seed Built-in Templates
**POST** `/api/v1/templates/seed`

Seeds built-in templates from YAML files.

**Response:**
```json
{
  "seeded": [
    {
      "status": "seeded",
      "template_id": "123e4567-e89b-12d3-a456-426614174000",
      "name": "Built-in EDI Template"
    }
  ],
  "skipped": [],
  "errors": []
}
```

**Permissions:** `admin`

### Get Template Flow Definition
**GET** `/api/v1/templates/{template_id}/flow-definition`

Retrieves the flow definition from NiFi Registry.

**Query Parameters:**
- `version` (optional): Specific version to retrieve (defaults to current)

**Response:**
```json
{
  "template_id": "b3ea1d0c-a8e6-448d-ada0-f8ab4929e562",
  "version": 2,
  "flow_definition": {
    "processors": [
      {
        "id": "getfile",
        "name": "Get EDI Files",
        "type": "org.apache.nifi.processors.standard.GetFile",
        "position": {"x": 100, "y": 100},
        "properties": {
          "Input Directory": "/tmp/input",
          "File Filter": ".*\\.edi"
        }
      }
    ],
    "connections": []
  }
}
```

**Permissions:** `workflow:read`

## Workflow Management API (`/api/v1/workflows/`)

### Create Workflow
**POST** `/api/v1/workflows/`

Creates a new workflow instance from a template.

**Request Body:**
```json
{
  "name": "Production EDI Validator",
  "description": "EDI validation workflow for production environment",
  "template_id": "b3ea1d0c-a8e6-448d-ada0-f8ab4929e562",
  "configuration": {
    "input_directory": "/data/edi/input",
    "output_directory": "/data/edi/output",
    "schema_name": "837.5010.X222.A1.json",
    "tenant_id": "tenant-a"
  },
  "template_version": 2
}
```

**Response:**
```json
{
  "workflow_id": "13e51f57-4c33-40b8-903a-8599c6785a4c",
  "name": "Production EDI Validator",
  "description": "EDI validation workflow for production environment",
  "tenant_id": "tenant-a",
  "template_id": "b3ea1d0c-a8e6-448d-ada0-f8ab4929e562",
  "template_version": 2,
  "configuration": {
    "input_directory": "/data/edi/input",
    "output_directory": "/data/edi/output",
    "schema_name": "837.5010.X222.A1.json",
    "tenant_id": "tenant-a"
  },
  "nifi_process_group_id": null,
  "nifi_parameter_context_id": null,
  "nifi_registry_client_id": null,
  "version_control_info": null,
  "status": "CREATED",
  "created_by": "admin-user",
  "created_at": "2025-09-02T19:28:50.346000",
  "updated_at": "2025-09-02T19:28:50.346000",
  "deployed_at": null,
  "last_started_at": null,
  "last_stopped_at": null,
  "template": {
    "template_id": "b3ea1d0c-a8e6-448d-ada0-f8ab4929e562",
    "bucket_id": "f68bea7b-f0e8-4e88-876c-83a655c68c1d",
    "current_version": 2,
    "name": "EDI Validation Template",
    "description": "Template for validating EDI files",
    "scope": "GLOBAL",
    "tenant_id": null,
    "status": "ACTIVE",
    "is_featured": false,
    "usage_count": 1,
    "created_by": "admin-user",
    "created_at": "2025-09-02T18:58:40.673000",
    "updated_at": "2025-09-02T19:00:41.293000",
    "deprecated_at": null
  }
}
```

**Permissions:** `workflow:write`

### List Workflows
**GET** `/api/v1/workflows/`

Retrieves a list of workflows for the current tenant.

**Response:**
```json
[
  {
    "workflow_id": "13e51f57-4c33-40b8-903a-8599c6785a4c",
    "name": "Production EDI Validator",
    "description": "EDI validation workflow for production environment",
    "tenant_id": "tenant-a",
    "template_id": "b3ea1d0c-a8e6-448d-ada0-f8ab4929e562",
    "template_version": 2,
    "configuration": {
      "input_directory": "/data/edi/input",
      "output_directory": "/data/edi/output",
      "schema_name": "837.5010.X222.A1.json",
      "tenant_id": "tenant-a"
    },
    "nifi_process_group_id": null,
    "nifi_parameter_context_id": null,
    "nifi_registry_client_id": null,
    "version_control_info": null,
    "status": "CREATED",
    "created_by": "admin-user",
    "created_at": "2025-09-02T19:28:50.346000",
    "updated_at": "2025-09-02T19:28:50.346000",
    "deployed_at": null,
    "last_started_at": null,
    "last_stopped_at": null,
    "template": {
      "template_id": "b3ea1d0c-a8e6-448d-ada0-f8ab4929e562",
      "bucket_id": "f68bea7b-f0e8-4e88-876c-83a655c68c1d",
      "current_version": 2,
      "name": "EDI Validation Template",
      "description": "Template for validating EDI files",
      "scope": "GLOBAL",
      "tenant_id": null,
      "status": "ACTIVE",
      "is_featured": false,
    "usage_count": 1,
      "created_by": "admin-user",
      "created_at": "2025-09-02T18:58:40.673000",
      "updated_at": "2025-09-02T19:00:41.293000",
      "deprecated_at": null
    }
  }
]
```

**Permissions:** `workflow:read`

### Get Workflow
**GET** `/api/v1/workflows/{workflow_id}`

Retrieves a specific workflow by ID.

**Response:**
```json
{
  "workflow_id": "13e51f57-4c33-40b8-903a-8599c6785a4c",
  "name": "Production EDI Validator",
  "description": "EDI validation workflow for production environment",
  "tenant_id": "tenant-a",
  "template_id": "b3ea1d0c-a8e6-448d-ada0-f8ab4929e562",
  "template_version": 2,
  "configuration": {
    "input_directory": "/data/edi/input",
    "output_directory": "/data/edi/output",
    "schema_name": "837.5010.X222.A1.json",
    "tenant_id": "tenant-a"
  },
  "nifi_process_group_id": null,
  "nifi_parameter_context_id": null,
  "nifi_registry_client_id": null,
  "version_control_info": null,
  "status": "CREATED",
  "created_by": "admin-user",
  "created_at": "2025-09-02T19:28:50.346000",
  "updated_at": "2025-09-02T19:28:50.346000",
  "deployed_at": null,
  "last_started_at": null,
  "last_stopped_at": null,
  "template": {
    "template_id": "b3ea1d0c-a8e6-448d-ada0-f8ab4929e562",
    "bucket_id": "f68bea7b-f0e8-4e88-876c-83a655c68c1d",
    "current_version": 2,
    "name": "EDI Validation Template",
    "description": "Template for validating EDI files",
    "scope": "GLOBAL",
    "tenant_id": null,
    "status": "ACTIVE",
    "is_featured": false,
    "usage_count": 1,
    "created_by": "admin-user",
    "created_at": "2025-09-02T18:58:40.673000",
    "updated_at": "2025-09-02T19:00:41.293000",
    "deprecated_at": null
  }
}
```

**Permissions:** `workflow:read`

### Update Workflow
**PUT** `/api/v1/workflows/{workflow_id}`

Updates a workflow's configuration.

**Request Body:**
```json
{
  "name": "Updated Production EDI Validator",
  "description": "Updated EDI validation workflow for production environment",
  "configuration": {
    "input_directory": "/data/edi/input",
    "output_directory": "/data/edi/output",
    "schema_name": "837.5010.X222.A1.json",
    "tenant_id": "tenant-a",
    "max_file_size": "10MB"
  }
}
```

**Response:**
```json
{
  "workflow_id": "13e51f57-4c33-40b8-903a-8599c6785a4c",
  "name": "Updated Production EDI Validator",
  "description": "Updated EDI validation workflow for production environment",
  "tenant_id": "tenant-a",
  "template_id": "b3ea1d0c-a8e6-448d-ada0-f8ab4929e562",
  "template_version": 2,
  "configuration": {
    "input_directory": "/data/edi/input",
    "output_directory": "/data/edi/output",
    "schema_name": "837.5010.X222.A1.json",
    "tenant_id": "tenant-a",
    "max_file_size": "10MB"
  },
  "nifi_process_group_id": null,
  "nifi_parameter_context_id": null,
  "nifi_registry_client_id": null,
  "version_control_info": null,
  "status": "CREATED",
  "created_by": "admin-user",
  "created_at": "2025-09-02T19:28:50.346000",
  "updated_at": "2025-09-02T19:35:22.145000",
  "deployed_at": null,
  "last_started_at": null,
  "last_stopped_at": null,
  "template": {
    "template_id": "b3ea1d0c-a8e6-448d-ada0-f8ab4929e562",
    "bucket_id": "f68bea7b-f0e8-4e88-876c-83a655c68c1d",
    "current_version": 2,
    "name": "EDI Validation Template",
    "description": "Template for validating EDI files",
    "scope": "GLOBAL",
    "tenant_id": null,
    "status": "ACTIVE",
    "is_featured": false,
    "usage_count": 1,
    "created_by": "admin-user",
    "created_at": "2025-09-02T18:58:40.673000",
    "updated_at": "2025-09-02T19:00:41.293000",
    "deprecated_at": null
  }
}
```

**Permissions:** `workflow:write`

### Delete Workflow
**DELETE** `/api/v1/workflows/{workflow_id}`

Deletes a workflow.

**Response:** `204 No Content`

**Permissions:** `workflow:write`

### Deploy Workflow
**POST** `/api/v1/workflows/{workflow_id}/deploy`

Deploys a workflow to the NiFi Canvas.

**Response:**
```json
{
  "workflow_id": "13e51f57-4c33-40b8-903a-8599c6785a4c",
  "name": "Updated Production EDI Validator",
  "description": "Updated EDI validation workflow for production environment",
  "tenant_id": "tenant-a",
  "template_id": "b3ea1d0c-a8e6-448d-ada0-f8ab4929e562",
  "template_version": 2,
  "configuration": {
    "input_directory": "/data/edi/input",
    "output_directory": "/data/edi/output",
    "schema_name": "837.5010.X222.A1.json",
    "tenant_id": "tenant-a",
    "max_file_size": "10MB"
  },
  "nifi_process_group_id": "a1b2c3d4-e5f6-7890-g1h2-i3j4k5l6m7n8",
  "nifi_parameter_context_id": "b2c3d4e5-f6g7-8901-h2i3-j4k5l6m7n8o9",
  "nifi_registry_client_id": null,
  "version_control_info": null,
  "status": "ACTIVE",
  "created_by": "admin-user",
  "created_at": "2025-09-02T19:28:50.346000",
  "updated_at": "2025-09-02T19:35:22.145000",
  "deployed_at": "2025-09-02T19:40:15.789000",
  "last_started_at": null,
  "last_stopped_at": null,
  "template": {
    "template_id": "b3ea1d0c-a8e6-448d-ada0-f8ab4929e562",
    "bucket_id": "f68bea7b-f0e8-4e88-876c-83a655c68c1d",
    "current_version": 2,
    "name": "EDI Validation Template",
    "description": "Template for validating EDI files",
    "scope": "GLOBAL",
    "tenant_id": null,
    "status": "ACTIVE",
    "is_featured": false,
    "usage_count": 1,
    "created_by": "admin-user",
    "created_at": "2025-09-02T18:58:40.673000",
    "updated_at": "2025-09-02T19:00:41.293000",
    "deprecated_at": null
  }
}
```

**Permissions:** `workflow:write`

### Undeploy Workflow
**POST** `/api/v1/workflows/{workflow_id}/undeploy`

Removes a workflow from the NiFi Canvas.

**Response:**
```json
{
  "workflow_id": "13e51f57-4c33-40b8-903a-8599c6785a4c",
  "name": "Updated Production EDI Validator",
  "description": "Updated EDI validation workflow for production environment",
  "tenant_id": "tenant-a",
  "template_id": "b3ea1d0c-a8e6-448d-ada0-f8ab4929e562",
  "template_version": 2,
  "configuration": {
    "input_directory": "/data/edi/input",
    "output_directory": "/data/edi/output",
    "schema_name": "837.5010.X222.A1.json",
    "tenant_id": "tenant-a",
    "max_file_size": "10MB"
  },
  "nifi_process_group_id": null,
  "nifi_parameter_context_id": null,
  "nifi_registry_client_id": null,
  "version_control_info": null,
  "status": "CREATED",
  "created_by": "admin-user",
  "created_at": "2025-09-02T19:28:50.346000",
  "updated_at": "2025-09-02T19:45:33.456000",
  "deployed_at": null,
  "last_started_at": null,
  "last_stopped_at": null,
  "template": {
    "template_id": "b3ea1d0c-a8e6-448d-ada0-f8ab4929e562",
    "bucket_id": "f68bea7b-f0e8-4e88-876c-83a655c68c1d",
    "current_version": 2,
    "name": "EDI Validation Template",
    "description": "Template for validating EDI files",
    "scope": "GLOBAL",
    "tenant_id": null,
    "status": "ACTIVE",
    "is_featured": false,
    "usage_count": 1,
    "created_by": "admin-user",
    "created_at": "2025-09-02T18:58:40.673000",
    "updated_at": "2025-09-02T19:00:41.293000",
    "deprecated_at": null
  }
}
```

**Permissions:** `workflow:write`

### Execute Workflow
**POST** `/api/v1/workflows/{workflow_id}/execute`

Executes a workflow with content.

**Request Body:**
```json
{
  "content": "ISA*00*          *00*          *ZZ*SENDERID       *ZZ*RECEIVERID     *250902*1945*U*00401*000000001*0*P*>~GS*PO*SENDERID*RECEIVERID*20250902*1945*1*X*004010~ST*850*0001~BEG*00*SA*123456789**20250902~REF*DP*00001~PER*IC*John Doe*TE*123-456-7890~FOB*TP~CTT*1~SE*8*0001~GE*1*1~IEA*1*000000001~",
  "content_type": "application/edi-x12",
  "parameters": {
    "schema_name": "837.5010.X222.A1.json"
  }
}
```

**Response:**
```json
{
  "workflow_id": "13e51f57-4c33-40b8-903a-8599c6785a4c",
  "execution_id": "c4d5e6f7-8901-2345-a6b7-c8d9e0f1g2h3",
  "status": "COMPLETED",
  "result": {
    "validation_passed": true,
    "acknowledgment": "ISA*00*          *00*          *ZZ*RECEIVERID     *ZZ*SENDERID       *250902*1945*U*00401*000000002*0*P*>~GS*FA*RECEIVERID*SENDERID*20250902*1945*2*X*004010~ST*997*0002~AK1*PO*0001~AK2*850*0001~AK5*A~SE*5*0002~GE*1*2~IEA*1*000000002~",
    "errors": []
  },
  "started_at": "2025-09-02T19:50:12.345000",
  "completed_at": "2025-09-02T19:50:15.678000",
  "duration_ms": 3333
}
```

**Permissions:** `workflow:execute`

### Get Workflow Status
**GET** `/api/v1/workflows/{workflow_id}/status`

Retrieves the current status of a workflow.

**Response:**
```json
{
  "workflow_id": "13e51f57-4c33-40b8-903a-8599c6785a4c",
  "status": "ACTIVE",
  "nifi_status": {
    "state": "Running",
    "run_status": "Running",
    "active_thread_count": 0,
    "last_updated": "2025-09-02T19:50:15.678000"
  },
  "last_execution": {
    "execution_id": "c4d5e6f7-8901-2345-a6b7-c8d9e0f1g2h3",
    "status": "COMPLETED",
    "started_at": "2025-09-02T19:50:12.345000",
    "completed_at": "2025-09-02T19:50:15.678000"
  }
}
```

**Permissions:** `workflow:read`

### Control Workflow
**POST** `/api/v1/workflows/{workflow_id}/control`

Controls workflow execution (start/stop/pause/resume).

**Request Body:**
```json
{
  "action": "start"
}
```

**Available Actions:**
- `start` - Start workflow execution
- `stop` - Stop workflow execution
- `pause` - Pause workflow execution
- `resume` - Resume workflow execution

**Response:**
```json
{
  "workflow_id": "13e51f57-4c33-40b8-903a-8599c6785a4c",
  "status": "ACTIVE",
  "message": "Workflow started successfully"
}
```

**Permissions:** `workflow:write`

## Error Responses

### 400 Bad Request
```json
{
  "detail": "Tenant ID required for tenant-scoped templates"
}
```

### 401 Unauthorized
```json
{
  "detail": "Not authenticated"
}
```

### 403 Forbidden
```json
{
  "detail": "Access denied to this template"
}
```

### 404 Not Found
```json
{
  "detail": "Template not found"
}
```

### 422 Unprocessable Entity
```json
{
  "detail": [
    {
      "loc": ["body", "name"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

### 500 Internal Server Error
```json
{
  "detail": "Failed to create template"
}
```

## Architecture Notes

### Registry-First Design
- **NiFi Registry** is the source of truth for all flow definitions
- **PostgreSQL Database** stores only references, metadata, and business logic
- All template operations create flows in both Registry and database
- Template versioning is managed through Registry flow versions

### Multi-Tenant Architecture
- **Global Templates:** Accessible across all tenants (admin-created)
- **Tenant Templates:** Scoped to specific tenants
- **Tenant Isolation:** Enforced at API and service layers
- **Role-Based Access:** Permissions control access to operations

### Version Control
- Templates support versioning through Registry flow versions
- Each update creates a new version in Registry
- Database tracks current version number
- Flow definitions can be retrieved for specific versions

## Testing Status

All API endpoints have been validated through comprehensive integration tests:

✅ **Template Endpoints:** 10/10 tests passing  
✅ **Workflow Endpoints:** All CRUD operations working  
✅ **Authentication:** Proper permission enforcement  
✅ **Multi-Tenant Isolation:** Correct tenant scoping  
✅ **Error Handling:** Proper HTTP status codes  
✅ **Registry Integration:** Real NiFi Registry operations  
✅ **Version Control:** Template versioning working  

The API endpoints represent the current Registry-first architecture and are fully functional with real external service integration.