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

## Next Steps

This documentation will evolve as we develop the system. The current design provides a solid foundation for:
- Eliminating trading partner/profile complexity
- Unifying batch and real-time processing
- Providing flexible, user-configurable workflows
- Scaling EDI processing operations

See the other documents in this folder for detailed specifications and implementation guidance.