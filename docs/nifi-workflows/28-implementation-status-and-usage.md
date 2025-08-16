# NiFi Workflow Template System - Implementation Status & Usage Guide

**Date**: August 16, 2025  
**Author**: Assistant  
**Version**: 1.0  
**Status**: ✅ **Phase 1 Complete - Foundation Ready**

## 🎯 Implementation Overview

The NiFi workflow template system has been successfully implemented with a hierarchical template architecture that provides both platform-managed global templates and tenant-customizable templates. The system is now ready for template creation and workflow deployment.

## ✅ Completed Implementation

### **Database Schema (✅ Complete)**

```sql
-- Core template hierarchy tables
workflow_templates     -- Template definitions with global/tenant scope
template_versions      -- Version control and change tracking  
template_usage         -- Analytics and audit tracking
workflows             -- Running workflow instances

-- All tables created with proper indexes, constraints, and relationships
```

**Verification**:
```bash
# Check database tables
./run.sh dev:db:exec "SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND (table_name LIKE '%template%' OR table_name LIKE '%workflow%') ORDER BY table_name;"
```

### **Backend Models (✅ Complete)**

**Location**: `backend/src/models/workflow_template.py`

- **WorkflowTemplate**: Main template model with hierarchy support
- **TemplateVersion**: Version control with change tracking
- **TemplateUsage**: Analytics and audit logging
- **Workflow**: Running workflow instances

**Key Features**:
- Tenant isolation with scope-based access control
- Template inheritance (`based_on` relationships)
- Version management with rollback capabilities
- Usage analytics and audit trails

### **API Schemas (✅ Complete)**

**Location**: `backend/src/api/schemas.py`

Complete Pydantic schemas for:
- Template CRUD operations (Create, Read, Update, Delete)
- Template cloning and customization
- Version management
- Workflow instance management
- Search and filtering capabilities

### **REST API Endpoints (✅ Basic Implementation)**

**Location**: `backend/src/api/endpoints/workflow_templates.py`

Currently implemented:
```http
GET  /api/v1/workflow-templates/              # List templates with filtering
GET  /api/v1/workflow-templates/{template_id} # Get specific template
```

**Authentication**: Integrated with existing JWT-based auth system
**Authorization**: Tenant-aware with scope-based access control

### **Development Tools (✅ Complete)**

**Database Operations**:
```bash
# New db:exec command added to run.sh
./run.sh dev:db:exec "SQL_COMMAND"

# Examples:
./run.sh dev:db:exec "\\dt public.workflow*"
./run.sh dev:db:exec "SELECT * FROM workflow_templates;"
```

## 🏗️ Template Hierarchy Architecture

### **Global Templates (Platform-Managed)**

```json
{
  "template_id": "global-sftp-edi-processor-v1.0",
  "name": "Standard SFTP EDI Batch Processor", 
  "scope": "GLOBAL",
  "maintainer": "edi-lens-platform",
  "category": "BATCH",
  "status": "ACTIVE",
  "is_featured": true,
  "flow_definition": { /* NiFi flow structure */ },
  "configuration_schema": { /* Dynamic UI schema */ }
}
```

**Characteristics**:
- ✅ Read-only for tenants
- ✅ Platform-maintained and versioned
- ✅ Production-tested and secure
- ✅ Available to all tenants

### **Tenant Templates (Tenant-Managed)**

```json
{
  "template_id": "tenant-a-custom-claims-v1.0",
  "name": "Custom Healthcare Claims Processor",
  "scope": "TENANT", 
  "tenant_id": "tenant-a",
  "based_on": "global-sftp-edi-processor-v1.0",
  "category": "BATCH",
  "status": "ACTIVE",
  "flow_definition": { /* Customized flow */ },
  "configuration_schema": { /* Custom config */ }
}
```

**Characteristics**:
- ✅ Fully customizable by tenant
- ✅ Can be based on global templates
- ✅ Version controlled
- ✅ Shareable within tenant organization

## 🔧 Current API Usage

### **Authentication Required**

All endpoints require JWT authentication with tenant context:

```bash
# Get auth token first
AUTH_TOKEN="Bearer eyJ..."
TENANT_ID="tenant-a"

# API calls
curl -X GET "http://localhost:3001/api/v1/workflow-templates/" \
  -H "Authorization: $AUTH_TOKEN" \
  -H "X-Tenant-Id: $TENANT_ID"
```

### **List Templates with Filtering**

```http
GET /api/v1/workflow-templates/
```

**Query Parameters**:
- `scope`: `GLOBAL` | `TENANT` 
- `category`: `BATCH` | `REALTIME` | `TRANSFORMATION` | `INTEGRATION`
- `status`: `ACTIVE` | `DEPRECATED` | `ARCHIVED`
- `featured_only`: `true` | `false`
- `tags`: Array of tags
- `page`: Page number (default: 1)
- `page_size`: Items per page (default: 20)

**Response**:
```json
{
  "templates": [
    {
      "template_id": "global-sftp-edi-processor-v1.0",
      "name": "Standard SFTP EDI Batch Processor",
      "scope": "GLOBAL",
      "category": "BATCH",
      "status": "ACTIVE",
      "is_featured": true,
      "usage_count": 42,
      "created_at": "2025-08-16T00:00:00Z",
      "flow_definition": { /* NiFi flow */ },
      "configuration_schema": { /* UI schema */ }
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20
}
```

### **Get Specific Template**

```http
GET /api/v1/workflow-templates/{template_id}
```

Returns complete template definition with flow and configuration schema.

## 🚧 Pending Implementation (Phase 2)

### **Additional API Endpoints**

```http
# Template Management
POST   /api/v1/workflow-templates/          # Create template
PUT    /api/v1/workflow-templates/{id}      # Update template  
DELETE /api/v1/workflow-templates/{id}      # Delete template
POST   /api/v1/workflow-templates/clone     # Clone template

# Version Management
GET    /api/v1/workflow-templates/{id}/versions     # List versions
POST   /api/v1/workflow-templates/{id}/versions     # Create version

# Import/Export
GET    /api/v1/workflow-templates/{id}/export       # Export template
POST   /api/v1/workflow-templates/import            # Import template

# Workflow Management
GET    /api/v1/workflows/                    # List workflow instances
POST   /api/v1/workflows/                    # Create workflow instance
GET    /api/v1/workflows/{id}                # Get workflow instance
PUT    /api/v1/workflows/{id}                # Update workflow instance
DELETE /api/v1/workflows/{id}                # Delete workflow instance
POST   /api/v1/workflows/{id}/actions        # Control workflow (pause/resume)
```

### **Template Categories to Implement**

1. **BATCH Templates**
   - SFTP file monitoring and processing
   - Batch EDI validation workflows
   - File archival and cleanup

2. **REALTIME Templates** 
   - HTTP endpoint processors
   - Real-time EDI validation
   - Synchronous acknowledgment generation

3. **TRANSFORMATION Templates**
   - Format conversion (JSON/CSV ↔ EDI)
   - Data mapping and transformation
   - Custom business rule processing

4. **INTEGRATION Templates**
   - Third-party API integration
   - Database operations
   - Message queue processing

## 🔍 Development Workflow

### **1. Create Global Templates**

Global templates should be created by the platform team and seeded into the database:

```sql
-- Example: Insert global SFTP template
INSERT INTO workflow_templates (
    template_id, name, description, category, scope, 
    maintainer, flow_definition, configuration_schema,
    is_featured, status
) VALUES (
    'global-sftp-edi-processor-v1.0',
    'Standard SFTP EDI Batch Processor',
    'Production-ready SFTP file monitoring and EDI validation',
    'BATCH',
    'GLOBAL',
    'edi-lens-platform',
    '{"processors": [], "connections": []}',
    '{"type": "object", "properties": {"input_path": {"type": "string"}}}',
    true,
    'ACTIVE'
);
```

### **2. Test Template API**

```bash
# Start development environment
./run.sh dev:start

# Test API endpoints
curl -X GET "http://localhost:3001/api/v1/workflow-templates/" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "X-Tenant-Id: tenant-a"

# Check database directly
./run.sh dev:db:exec "SELECT template_id, name, scope, category FROM workflow_templates;"
```

### **3. Implement Additional Endpoints**

The foundation is ready - additional endpoints can be implemented incrementally by:

1. Adding endpoint functions to `workflow_templates.py`
2. Implementing business logic in the models
3. Adding validation and error handling
4. Testing with different tenant contexts

### **4. NiFi Integration**

Once templates are created, integrate with NiFi:

1. **Template Deployment**: Convert template JSON to NiFi Process Groups
2. **Parameter Injection**: Apply workflow-specific configuration
3. **Registry Integration**: Store versioned flows in NiFi Registry
4. **Monitoring**: Track workflow execution and performance

## 📊 Database Schema Details

### **Template Hierarchy**

```
workflow_templates
├── template_id (PK)
├── scope (GLOBAL|TENANT) 
├── tenant_id (NULL for global)
├── based_on (FK to parent template)
├── flow_definition (JSONB)
├── configuration_schema (JSONB)
└── ... metadata fields

template_versions
├── version_id (PK)
├── template_id (FK)
├── version (string)
├── flow_definition (JSONB)
├── configuration_schema (JSONB)
└── ... version metadata

workflows  
├── workflow_id (PK)
├── tenant_id
├── template_id (FK)
├── configuration (JSONB)
├── nifi_process_group_id
└── ... runtime metadata
```

### **Access Control**

- **Global templates**: Visible to all tenants, read-only
- **Tenant templates**: Only visible to owning tenant, full CRUD
- **Workflows**: Tenant-isolated, full CRUD within tenant

## 🎉 Ready for Next Phase

The template system foundation is complete and ready for:

1. **Template Creation**: Build your first global templates
2. **UI Development**: Admin interface for template management  
3. **NiFi Integration**: Deploy templates as actual workflows
4. **Production Use**: Full workflow lifecycle management

The architecture supports your complete vision - global templates for standardization, tenant templates for customization, with full versioning, cloning, and workflow management capabilities!