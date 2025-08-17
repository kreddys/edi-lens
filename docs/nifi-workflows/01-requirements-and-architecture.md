# NiFi Integration Requirements and Architecture

## Overview

EDI Lens implements a template-driven workflow architecture powered by Apache NiFi, separating concerns between backend EDI APIs and workflow orchestration. This architecture provides flexibility, scalability, and reusability for both batch and real-time EDI processing.

## Core Requirements

### 1. Workflow Management
- **Template-Driven**: All workflows based on predefined, configurable templates
- **Multi-Tenant**: Complete separation of tenant data and workflows
- **Category-Based**: Support for BATCH, REALTIME, and TRANSFORMATION workflows
- **Version Control**: Template versioning for evolution and rollback
- **Configuration Validation**: Schema validation for workflow setup

### 2. Processing Models
- **Batch Processing**: SFTP file monitoring with asynchronous processing
- **Real-time Processing**: HTTP endpoints with synchronous responses
- **Transformation**: Format conversion (JSON/CSV/XML ↔ EDI)

### 3. NiFi Integration
- **Registry Integration**: Templates stored in NiFi Registry for versioned flows
- **Process Group Management**: Workflow instances as NiFi process groups
- **Parameter Contexts**: Workflow-specific configuration management
- **State Control**: Start, stop, restart deployed workflows
- **Monitoring**: Real-time status and health checks

### 4. Built-in Templates
Two core built-in templates with configurable translation capabilities:
1. **Batch EDI Processor**: Monitors SFTP directories for file processing with optional format translation
2. **Real-time EDI Processor**: Processes EDI transactions via HTTP endpoints with optional format translation

Each template includes configurable translation processors that can convert between EDI and other formats (JSON/CSV/XML) as needed.

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

## Data Flow Architecture

1. **Template Creation**: Users create workflow templates through the API
2. **Workflow Instantiation**: Templates instantiated as workflows with configurations
3. **NiFi Deployment**: Workflows deployed to NiFi Registry and process groups
4. **Parameter Configuration**: Workflow configs applied as NiFi parameter contexts
5. **Execution**: EDI content processed through deployed NiFi workflows
6. **Monitoring**: Workflow status and health continuously monitored

## Technical Requirements

### Dependencies
- Apache NiFi 1.23+
- Apache NiFi Registry 1.23+
- PostgreSQL database
- Keycloak identity provider

### Core Services
- **NiFi API Client**: Management of process groups, parameter contexts, templates
- **NiFi Registry Client**: Management of buckets, flows, and flow versions
- **Workflow Service**: Complete workflow lifecycle management
- **Template Management**: Built-in template seeding and management
- **Health Monitoring**: NiFi service health and status monitoring

### Security Requirements
- JWT-based authentication for all API endpoints
- Role-based access control (admin vs viewer)
- Tenant isolation with complete data separation
- Secure communication with NiFi services (HTTPS)
- Sensitive parameter handling in NiFi

## Design Principles

1. **Template-Driven**: All workflows based on predefined templates
2. **Schema Validation**: Configuration schemas ensure valid workflow setup
3. **Tenant Isolation**: Complete separation of tenant data and workflows
4. **API-First**: Backend provides focused APIs for EDI operations
5. **Monitoring-Ready**: Built-in observability and metrics collection