# NiFi Workflow Architecture - Overview

## Vision

EDI Lens is transitioning from a monolithic backend processing system to a flexible, template-driven workflow architecture powered by Apache NiFi. This new architecture separates concerns: the backend provides focused EDI APIs, while NiFi handles workflow orchestration for both batch and real-time processing.

## Core Concepts

### Workflows
- **Independent units** of processing logic
- **Template-driven** configuration
- **Tenant-specific** but reusable
- **Tag-based** organization and filtering

### Templates
- **Reusable workflow definitions** stored in NiFi
- **Configuration schemas** for dynamic UI generation
- **Category-based** organization (BATCH, REALTIME, TRANSFORMATION)
- **Version controlled** for evolution and rollback

### Processing Models
- **Batch Processing**: SFTP file monitoring with asynchronous processing
- **Real-time Processing**: HTTP endpoints with synchronous responses
- **Transformation**: Format conversion (JSON/CSV/XML ↔ EDI)

## Benefits of This Architecture

1. **Flexibility**: Users can create custom workflows without backend changes
2. **Scalability**: NiFi handles orchestration, backend focuses on EDI operations
3. **Reusability**: Templates can be used across tenants with different configurations
4. **Unified Processing**: Same workflow engine for batch and real-time
5. **Configuration-Driven**: No code changes needed for new processing patterns

## Architecture Components

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Admin UI      │    │   Backend APIs  │    │   NiFi Engine   │
│                 │    │                 │    │                 │
│ • Workflow Mgmt │◄──►│ • EDI Validation│◄──►│ • Workflow Exec │
│ • Template UI   │    │ • TA1/999 Gen   │    │ • File Monitor  │
│ • Monitoring    │    │ • Schema Mgmt   │    │ • HTTP Listener │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────────┐
                    │   PostgreSQL    │
                    │                 │
                    │ • Workflows     │
                    │ • Templates     │
                    │ • Config        │
                    └─────────────────┘
```

## Key Design Principles

1. **Template-Driven**: All workflows are based on predefined, configurable templates
2. **Schema Validation**: Configuration schemas ensure valid workflow setup
3. **Tenant Isolation**: Complete separation of tenant data and workflows
4. **API-First**: Backend provides focused APIs for EDI operations
5. **Monitoring-Ready**: Built-in observability and metrics collection

## Implementation Status

**Phase**: ✅ **Phase 1 Complete - Foundation Implementation** (August 16, 2025)  
**Next Phase**: Template Creation and Advanced API Development

### ✅ **Completed**
- Database schema with 4 core tables (workflow_templates, template_versions, template_usage, workflows)
- SQLAlchemy models with relationships and business logic
- Pydantic schemas for API request/response handling
- Basic REST API endpoints (list, get) with authentication
- Template hierarchy support (global/tenant scope)
- Developer tools (db:exec command added to run.sh)
- Comprehensive documentation and quick-start guide

### 🚧 **In Progress**
- Additional CRUD API endpoints (create, update, delete, clone)
- Template versioning and import/export features
- Workflow instance management
- NiFi integration planning

### 📋 **Ready for**
- Creating first global templates
- Building Admin UI template management interface
- NiFi Registry integration
- Production workflow deployment

## Next Steps

The foundation is complete! The current implementation provides:
- ✅ Eliminated trading partner/profile complexity
- ✅ Template hierarchy for global/tenant workflow management  
- ✅ Unified approach for batch and real-time processing
- ✅ Flexible, user-configurable workflow system
- ✅ Scalable EDI processing architecture

**Key Documents**:
- **Implementation Guide**: `28-implementation-status-and-usage.md`
- **Developer Quick Start**: `29-developer-quick-start.md`
- **Template Architecture**: `27-template-hierarchy-and-management.md`

See the other documents in this folder for detailed specifications and implementation guidance.