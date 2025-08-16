# Template Hierarchy and Management System

**Date**: August 15, 2025  
**Author**: Assistant  
**Version**: 1.0

## Overview

The EDI Lens NiFi integration implements a hierarchical template system that provides both global system templates and tenant-specific customizable templates. This system enables standardized workflows while allowing tenant-specific customizations and extensions.

## Template Hierarchy

### 1. Global System Templates

**Purpose**: Provide standardized, battle-tested workflow templates maintained by the EDI Lens platform.

**Characteristics**:
- **Read-only** for tenants (cannot be modified)
- **Platform-maintained** and updated with system releases
- **Pre-configured** with best practices and security standards
- **Tested and validated** across multiple tenant scenarios
- **Version controlled** with automatic updates

**Global Template Categories**:

#### SFTP Batch Processing Templates
```json
{
    "template_id": "global-sftp-edi-processor-v1.0",
    "name": "Standard SFTP EDI Batch Processor",
    "description": "Production-ready SFTP file monitoring and EDI validation",
    "category": "BATCH",
    "scope": "GLOBAL",
    "maintainer": "edi-lens-platform",
    "features": [
        "Multi-tenant file routing",
        "Comprehensive error handling",
        "Automatic acknowledgment generation",
        "File archival and cleanup",
        "Audit trail integration"
    ]
}
```

#### Real-time HTTP Processing Templates
```json
{
    "template_id": "global-http-edi-processor-v1.0", 
    "name": "Standard HTTP Real-time EDI Processor",
    "description": "Production-ready HTTP endpoint for real-time EDI validation",
    "category": "REALTIME",
    "scope": "GLOBAL",
    "maintainer": "edi-lens-platform",
    "features": [
        "Synchronous EDI validation",
        "Configurable timeout handling",
        "Standard error responses",
        "Rate limiting support",
        "Authentication integration"
    ]
}
```

#### Format Translation Templates
```json
{
    "template_id": "global-format-converter-v1.0",
    "name": "Standard Format Converter",
    "description": "Production-ready format conversion (JSON/CSV/XML ↔ EDI)",
    "category": "TRANSFORMATION",
    "scope": "GLOBAL", 
    "maintainer": "edi-lens-platform",
    "features": [
        "Bidirectional format conversion",
        "Schema-driven mapping",
        "Validation before and after conversion",
        "Error handling and rollback",
        "Batch and single-item processing"
    ]
}
```

### 2. Tenant-Specific Templates

**Purpose**: Allow tenants to customize workflows for their specific business requirements.

**Characteristics**:
- **Tenant-owned** and fully customizable
- **Based on global templates** or created from scratch
- **Version controlled** per tenant
- **Shareable** within tenant organization
- **Testable** in isolated environments

**Creation Methods**:
1. **Clone from Global**: Start with proven template, customize as needed
2. **Clone from Tenant**: Duplicate existing tenant template
3. **Create from Scratch**: Build entirely custom workflow
4. **Import from Export**: Share templates between tenants/environments

## Template-to-Workflow Relationship

### Conceptual Model

**Template** = Blueprint/Recipe  
**Workflow** = Running Instance/Deployment

```
┌─────────────────┐    instantiate    ┌─────────────────┐
│   Template      │ ─────────────────► │   Workflow      │
│                 │                    │                 │
│ • JSON Definition│                    │ • NiFi Process  │
│ • Config Schema │                    │   Group         │
│ • Parameters    │                    │ • Running State │
│ • Metadata      │                    │ • Tenant Config │
└─────────────────┘                    └─────────────────┘
```

### Detailed Relationship

#### Templates Define:
1. **NiFi Flow Structure** - Processors, connections, and flow logic
2. **Configuration Schema** - What parameters can be customized
3. **Parameter Constraints** - Validation rules and allowed values
4. **Default Values** - Sensible defaults for quick deployment
5. **Documentation** - Usage instructions and examples

#### Workflows Contain:
1. **Template Reference** - Which template is being used
2. **Configuration Values** - Tenant-specific parameter values
3. **Runtime State** - Running, paused, error status
4. **NiFi Deployment** - Actual process group in NiFi
5. **Execution History** - Logs, metrics, and audit trail

### Example Relationship

**Template Definition**:
```json
{
    "template_id": "tenant-a-custom-claims-v1.0",
    "name": "Custom Healthcare Claims Processor",
    "description": "Specialized 837P processing with custom validations",
    "category": "BATCH",
    "scope": "TENANT",
    "tenant_id": "tenant-a",
    "based_on": "global-sftp-edi-processor-v1.0",
    
    "configuration_schema": {
        "type": "object",
        "required": ["input_path", "validation_rules"],
        "properties": {
            "input_path": {
                "type": "string",
                "description": "SFTP directory to monitor"
            },
            "validation_rules": {
                "type": "object",
                "properties": {
                    "require_npi": {"type": "boolean", "default": true},
                    "max_claim_amount": {"type": "number", "default": 10000},
                    "allowed_procedure_codes": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                }
            },
            "notification_webhooks": {
                "type": "array",
                "items": {"type": "string", "format": "uri"}
            }
        }
    }
}
```

**Workflow Instance**:
```json
{
    "workflow_id": "wf-claims-prod-001",
    "template_id": "tenant-a-custom-claims-v1.0",
    "tenant_id": "tenant-a",
    "name": "Production Claims Processing",
    "status": "ACTIVE",
    
    "configuration": {
        "input_path": "/sftp/tenants/tenant-a/claims/production/in/",
        "validation_rules": {
            "require_npi": true,
            "max_claim_amount": 50000,
            "allowed_procedure_codes": ["99213", "99214", "99215"]
        },
        "notification_webhooks": [
            "https://tenant-a.com/webhooks/claims-processed",
            "https://internal.tenant-a.com/api/edi-notifications"
        ]
    },
    
    "nifi_deployment": {
        "process_group_id": "pg-12345-abcde",
        "parameter_context_id": "pc-67890-fghij",
        "deployment_method": "registry",
        "flow_version": 3
    }
}
```

## Template Management Operations

### 1. Template Discovery and Browsing

#### List Global Templates
```http
GET /api/v1/workflow-templates?scope=global&category=BATCH
```

#### List Tenant Templates  
```http
GET /api/v1/workflow-templates?scope=tenant&tenant_id=tenant-a
```

#### Template Details with Schema
```http
GET /api/v1/workflow-templates/global-sftp-edi-processor-v1.0
```

### 2. Template Creation Operations

#### Clone from Global Template
```http
POST /api/v1/workflow-templates/clone
Content-Type: application/json

{
    "source_template_id": "global-sftp-edi-processor-v1.0",
    "new_template": {
        "name": "Custom Claims Processor",
        "description": "Specialized for our healthcare claims workflow",
        "customizations": {
            "add_processors": [...],
            "modify_configuration_schema": {...},
            "add_validation_rules": [...]
        }
    }
}
```

#### Create from Scratch
```http
POST /api/v1/workflow-templates
Content-Type: application/json

{
    "name": "Custom Integration Workflow",
    "description": "Handles our specific B2B integration requirements",
    "category": "TRANSFORMATION",
    "flow_definition": {...},
    "configuration_schema": {...}
}
```

#### Clone from Tenant Template
```http
POST /api/v1/workflow-templates/clone
Content-Type: application/json

{
    "source_template_id": "tenant-a-custom-claims-v1.0",
    "new_template": {
        "name": "Claims Processor - Development Version",
        "description": "Development environment version for testing"
    }
}
```

### 3. Template Customization

#### Modify Template Configuration
```http
PUT /api/v1/workflow-templates/tenant-a-custom-claims-v1.0
Content-Type: application/json

{
    "description": "Updated with new validation requirements",
    "configuration_schema": {
        // Updated schema with new fields
    },
    "flow_definition": {
        // Modified NiFi flow structure
    }
}
```

#### Add Custom Processors
```http
POST /api/v1/workflow-templates/tenant-a-custom-claims-v1.0/processors
Content-Type: application/json

{
    "processor": {
        "id": "custom-validation-processor",
        "name": "Custom Validation Logic",
        "type": "org.apache.nifi.processors.standard.InvokeHTTP",
        "properties": {
            "Remote URL": "https://tenant-a.com/api/custom-validation"
        }
    },
    "position": {"x": 500, "y": 200},
    "connections": [...]
}
```

### 4. Template Versioning

#### Create New Version
```http
POST /api/v1/workflow-templates/tenant-a-custom-claims-v1.0/versions
Content-Type: application/json

{
    "version": "1.1",
    "changes": "Added support for ERA processing",
    "flow_definition": {...},
    "configuration_schema": {...}
}
```

#### Rollback to Previous Version
```http
POST /api/v1/workflow-templates/tenant-a-custom-claims-v1.0/rollback
Content-Type: application/json

{
    "target_version": "1.0",
    "reason": "New version has performance issues"
}
```

### 5. Template Import/Export

#### Export Template
```http
GET /api/v1/workflow-templates/tenant-a-custom-claims-v1.0/export
Accept: application/json

Response: Complete template definition with metadata
```

#### Import Template
```http
POST /api/v1/workflow-templates/import
Content-Type: application/json

{
    "template_data": {...},
    "import_options": {
        "overwrite_existing": false,
        "validate_before_import": true,
        "assign_new_id": true
    }
}
```

## Template Categories and Features

### Batch Processing Templates
- **File monitoring** and automatic processing
- **Error handling** and retry logic
- **Acknowledgment generation** (TA1, 999)
- **Archive and cleanup** workflows
- **Multi-tenant routing** and isolation

### Real-time Processing Templates
- **HTTP endpoints** for synchronous processing
- **Timeout management** and error responses
- **Rate limiting** and throttling
- **Authentication integration**
- **Response formatting** and caching

### Transformation Templates
- **Format conversion** (JSON/CSV/XML ↔ EDI)
- **Data mapping** and field transformation
- **Validation** before and after conversion
- **Batch and streaming** processing modes
- **Custom mapping rules** and business logic

### Integration Templates
- **Third-party API** integration
- **Database** read/write operations
- **Message queue** publishing and consumption
- **Event-driven** processing
- **Custom protocol** handling

## Database Schema

```sql
-- Template hierarchy and management
CREATE TABLE workflow_templates (
    template_id VARCHAR PRIMARY KEY,
    name VARCHAR NOT NULL,
    description TEXT,
    category VARCHAR NOT NULL, -- BATCH, REALTIME, TRANSFORMATION, INTEGRATION
    
    -- Template scope and ownership
    scope VARCHAR NOT NULL, -- GLOBAL, TENANT
    tenant_id VARCHAR, -- NULL for global templates
    maintainer VARCHAR, -- 'edi-lens-platform' for global, user ID for tenant
    
    -- Template lineage
    based_on VARCHAR REFERENCES workflow_templates(template_id), -- Parent template
    version VARCHAR DEFAULT '1.0',
    
    -- Template definition
    flow_definition JSONB NOT NULL,
    configuration_schema JSONB NOT NULL,
    
    -- NiFi deployment
    deployment_method VARCHAR DEFAULT 'registry',
    nifi_registry_flow_id VARCHAR,
    nifi_registry_bucket_id VARCHAR,
    
    -- Template metadata
    tags TEXT[],
    features TEXT[], -- Capabilities provided by template
    documentation TEXT, -- Usage instructions
    examples JSONB, -- Example configurations
    
    -- Status and lifecycle
    status VARCHAR DEFAULT 'ACTIVE', -- ACTIVE, DEPRECATED, ARCHIVED
    is_featured BOOLEAN DEFAULT false, -- Show in featured templates
    usage_count INTEGER DEFAULT 0, -- Track popularity
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    deprecated_at TIMESTAMP,
    
    -- Constraints
    CONSTRAINT valid_scope CHECK (scope IN ('GLOBAL', 'TENANT')),
    CONSTRAINT tenant_scope_consistency CHECK (
        (scope = 'GLOBAL' AND tenant_id IS NULL) OR 
        (scope = 'TENANT' AND tenant_id IS NOT NULL)
    )
);

-- Template versions for change tracking
CREATE TABLE template_versions (
    version_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_id VARCHAR REFERENCES workflow_templates(template_id),
    version VARCHAR NOT NULL,
    
    -- Version content
    flow_definition JSONB NOT NULL,
    configuration_schema JSONB NOT NULL,
    
    -- Change tracking
    changes TEXT, -- Description of changes
    created_by VARCHAR NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    
    -- Version metadata
    is_current BOOLEAN DEFAULT false,
    deployment_count INTEGER DEFAULT 0,
    
    UNIQUE(template_id, version)
);

-- Template usage analytics
CREATE TABLE template_usage (
    usage_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_id VARCHAR REFERENCES workflow_templates(template_id),
    template_version VARCHAR,
    tenant_id VARCHAR NOT NULL,
    
    -- Usage context
    workflow_id VARCHAR, -- Which workflow used this template
    action VARCHAR NOT NULL, -- DEPLOY, UPDATE, DELETE, CLONE
    
    -- Usage metadata
    configuration_hash VARCHAR, -- Hash of configuration used
    success BOOLEAN,
    error_message TEXT,
    
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX idx_templates_scope ON workflow_templates(scope);
CREATE INDEX idx_templates_tenant ON workflow_templates(tenant_id);
CREATE INDEX idx_templates_category ON workflow_templates(category);
CREATE INDEX idx_templates_status ON workflow_templates(status);
CREATE INDEX idx_templates_based_on ON workflow_templates(based_on);
CREATE INDEX idx_templates_featured ON workflow_templates(is_featured) WHERE is_featured = true;

CREATE INDEX idx_template_versions_template ON template_versions(template_id);
CREATE INDEX idx_template_versions_current ON template_versions(template_id) WHERE is_current = true;

CREATE INDEX idx_template_usage_template ON template_usage(template_id);
CREATE INDEX idx_template_usage_tenant ON template_usage(tenant_id);
CREATE INDEX idx_template_usage_action ON template_usage(action);
```

## Template Lifecycle

### Development Phase
1. **Create** - Author new template or clone existing
2. **Design** - Configure processors and flow logic
3. **Validate** - Test configuration schema and flow
4. **Document** - Add usage instructions and examples

### Testing Phase
1. **Deploy Test** - Create test workflow instances
2. **Validation** - Verify functionality and performance
3. **Security Review** - Ensure tenant isolation and security
4. **Load Testing** - Performance under realistic conditions

### Production Phase
1. **Publish** - Make available for workflow creation
2. **Monitor** - Track usage and performance metrics
3. **Maintain** - Fix issues and add improvements
4. **Version** - Release updates and manage versions

### End-of-Life Phase
1. **Deprecate** - Mark as deprecated, discourage new usage
2. **Migration** - Help users migrate to newer templates
3. **Archive** - Remove from active catalog but preserve data
4. **Cleanup** - Remove unused templates and associated data

This hierarchical template system provides the flexibility for tenants to customize workflows while maintaining the reliability and security of platform-managed global templates.