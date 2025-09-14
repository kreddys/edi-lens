# EDI Lens E2E Workflow Lifecycle Documentation

This document provides a comprehensive overview of the EDI Lens end-to-end workflow lifecycle, detailing each phase of the process from template creation through workflow execution and cleanup.

## Overview

The EDI Lens system implements a sophisticated workflow management architecture that separates concerns between template definition, workflow configuration, and runtime execution. The system integrates three main components:

1. **EDI Lens Backend** - Manages workflow metadata, configuration, and orchestration
2. **NiFi Registry** - Provides version-controlled template storage
3. **Apache NiFi** - Handles actual data processing execution

## E2E Test Phases

### Phase 1: Template Creation 🏗️
**API Endpoint**: `POST /api/v1/templates/`

**What happens**:
1. **Static Validation** - `NiFiTemplateValidator` validates the flow definition structure
2. **Dynamic Validation** - Validates processor types and properties against live NiFi instance
3. **Bucket Creation** - Ensures appropriate bucket exists in NiFi Registry (GLOBAL or TENANT scope)
4. **Registry Flow Creation** - Creates flow in NiFi Registry using `registry_client.create_flow()`
5. **Flow Version Upload** - Uploads flow definition as version 1 using `create_flow_version()`
6. **Database Record** - Creates template metadata record in EDI Lens database

**Storage Locations**:
- **NiFi Registry**: Flow definition, version control, bucket structure
- **EDI Lens Database**: Template metadata, registry references, access control

**Key Components**:
- `TemplateService.create_template()`
- `NiFiTemplateValidator`
- `NiFiRegistryClient`

### Phase 2: Workflow Instance Creation 🔧
**API Endpoint**: `POST /api/v1/workflows/`

**What happens**:
1. **Template Validation** - Verifies referenced template exists and is accessible
2. **Workflow Record Creation** - Creates workflow database record with:
   - Template reference (`template_id`)
   - Configuration parameters (input/output directories, patterns)
   - Workflow metadata (name, description, tenant)
   - Initial status: `CREATED`

**Storage Locations**:
- **EDI Lens Database**: Workflow configuration, parameter values, status

**Key Components**:
- `WorkflowService.create_workflow()`
- Workflow model with configuration schema

### Phase 3: Test Setup Validation ✅
**Purpose**: Validates test environment setup

**What happens**:
1. **Directory Validation** - Ensures test input/output directories exist
2. **Test File Creation** - Creates sample input file for processing
3. **Environment Check** - Validates test configuration

### Phase 4: Database State Verification 🔍
**API Endpoints**:
- `GET /api/v1/templates/{template_id}`
- `GET /api/v1/workflows/{workflow_id}`

**What happens**:
1. **Template Retrieval** - Validates template was stored correctly
2. **Workflow Retrieval** - Validates workflow instance was created correctly
3. **Data Integrity Check** - Ensures all relationships and data are consistent

### Phase 5: NiFi Deployment 🚀
**API Endpoint**: `POST /api/v1/workflows/{workflow_id}/deploy`

**What happens** (Hybrid Deployment Engine):
1. **Registry Integration** - Downloads flow definition from NiFi Registry
2. **Parameter Processing** - Applies parameter substitution with validation
3. **Individual Component Deployment**:
   - Creates NiFi ProcessGroup
   - Creates processors individually (GetFile, UpdateAttribute, PutFile)
   - Creates connections between processors
   - Sets up parameter context
4. **Version Control Assignment** - Associates components with Registry flow
5. **Database Update** - Updates workflow record with NiFi component IDs

**Storage Locations**:
- **Live NiFi Canvas**: ProcessGroup, processors, connections, parameter context
- **EDI Lens Database**: Updated with NiFi component IDs, deployment status

**Key Components**:
- `HybridDeploymentEngine` (our new implementation)
- `WorkflowService.deploy_workflow()`
- NiFi API integration

### Phase 5.5: Processor Restart 🔄
**API Endpoint**: `POST /api/v1/workflows/{workflow_id}/restart-processors`

**What happens**:
1. **Parameter Context Association** - Ensures processors recognize parameter context
2. **Processor Restart** - Restarts processors to re-evaluate parameters
3. **Validation Refresh** - Allows NiFi to refresh processor validation status

### Phase 6: Workflow Start ▶️
**API Endpoint**: `POST /api/v1/workflows/{workflow_id}/start`

**What happens**:
1. **Processor State Change** - Changes NiFi processors from STOPPED to RUNNING
2. **Status Verification** - Confirms processors started successfully
3. **Workflow Activation** - Makes workflow ready to process files

### Phase 7: Workflow Execution 🏃‍♂️
**API Endpoint**: `POST /api/v1/workflows/{workflow_id}/execute`

**What happens**:
1. **Execution Request** - Initiates file processing with monitoring
2. **Parameter Override** - Applies execution-specific parameters if provided
3. **Monitoring Setup** - Configures execution monitoring and tracking
4. **File Processing** - NiFi workflow processes files in configured directories

**Key Data Flow**:
```
Input Directory → GetFile Processor → UpdateAttribute Processor → PutFile Processor → Output Directory
```

### Phase 8: File Processing Validation 📁
**Purpose**: Validates actual file processing functionality

**What happens**:
1. **Output Polling** - Polls output directory for processed files
2. **File Validation** - Validates output files match expected pattern
3. **Content Verification** - Ensures file content is processed correctly
4. **Processing Metrics** - Checks processing time and success rates

### Phase 9: Status Validation 📊
**API Endpoint**: `GET /api/v1/workflows/{workflow_id}/status`

**What happens**:
1. **Comprehensive Status Check**:
   - Workflow deployment status
   - NiFi process group status
   - Processor states
   - Execution metrics
2. **Data Integrity Validation**:
   - Template relationship integrity
   - NiFi component ID consistency
   - Timestamp accuracy
3. **Responsiveness Test** - Ensures system remains responsive after processing

### Phase 10: NiFi Direct Validation 🔧
**Purpose**: Direct validation of NiFi component states

**What happens**:
1. **NiFi API Integration** - Direct queries to NiFi API (when available)
2. **Component State Verification** - Validates processor and connection states
3. **Parameter Context Validation** - Ensures parameter substitution worked correctly

### Phase 11: Cleanup 🧹
**Purpose**: Clean up test resources

**What happens**:
1. **File Cleanup** - Removes test input/output files and directories
2. **Resource Cleanup** - Optionally removes deployed NiFi components
3. **Database Cleanup** - Removes test workflow and template records

## Architecture Components

### EDI Lens Backend Services

#### TemplateService
- **Responsibilities**: Template lifecycle management, NiFi Registry integration
- **Key Methods**:
  - `create_template()` - Creates templates in Registry and database
  - `get_template()` - Retrieves template metadata
  - `validate_template()` - Static and dynamic validation

#### WorkflowService
- **Responsibilities**: Workflow lifecycle management, NiFi deployment orchestration
- **Key Methods**:
  - `create_workflow()` - Creates workflow instances
  - `deploy_workflow()` - Orchestrates NiFi deployment
  - `start_workflow()` - Starts NiFi processors
  - `execute_workflow()` - Initiates file processing

#### HybridDeploymentEngine
- **Responsibilities**: Individual component deployment with detailed error reporting
- **Key Features**:
  - Registry integration for version control
  - Parameter substitution and validation
  - Individual component creation (processors, connections)
  - Comprehensive error reporting and rollback

### Integration Points

#### NiFi Registry Integration
- **Purpose**: Version-controlled template storage
- **Components**: `NiFiRegistryClient`
- **Operations**: Flow creation, version management, template retrieval

#### NiFi API Integration
- **Purpose**: Runtime component management
- **Components**: `NiFiAPIClient`
- **Operations**: Component creation, state management, monitoring

#### Database Integration
- **Purpose**: Metadata and state management
- **Models**: `RegistryTemplate`, `Workflow`
- **Operations**: CRUD operations, relationship management

## Data Flow Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│                 │    │                  │    │                 │
│  EDI Lens DB    │◄──►│  NiFi Registry   │◄──►│  Live NiFi      │
│                 │    │                  │    │                 │
│  • Templates    │    │  • Flow Defs     │    │  • ProcessGroups│
│  • Workflows    │    │  • Versions      │    │  • Processors   │
│  • Metadata     │    │  • Buckets       │    │  • Connections  │
│                 │    │                  │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
        │                        │                        │
        └────────────────────────┼────────────────────────┘
                                 │
                    ┌─────────────▼──────────────┐
                    │                            │
                    │    Hybrid Deployment       │
                    │        Engine              │
                    │                            │
                    │  • Registry Integration    │
                    │  • Parameter Processing    │
                    │  • Component Creation      │
                    │  • Error Reporting         │
                    │                            │
                    └────────────────────────────┘
```

## Error Handling and Monitoring

### Hybrid Deployment Error Reporting
The new hybrid deployment approach provides granular error reporting:

- **Component-level failures** - Specific processor/connection creation errors
- **Parameter validation** - Detailed parameter substitution validation
- **Rollback capabilities** - Automatic cleanup on deployment failure
- **Progress tracking** - Real-time deployment progress reporting

### Validation Layers
1. **Static Validation** - Template structure and syntax validation
2. **Dynamic Validation** - Live NiFi compatibility validation
3. **Runtime Validation** - Deployment-time component validation
4. **Execution Validation** - File processing and workflow execution validation

### Monitoring Integration
- **Execution Tracking** - Request IDs and execution monitoring
- **Status Reporting** - Real-time workflow status updates
- **Metrics Collection** - Performance and success rate tracking
- **Error Aggregation** - Centralized error reporting and analysis

## Testing Strategy

The E2E test validates the complete workflow lifecycle:

1. **Template Management** - Creation, validation, and storage
2. **Workflow Configuration** - Instance creation and parameter management
3. **NiFi Integration** - Deployment, component creation, and state management
4. **File Processing** - End-to-end data processing validation
5. **Status Reporting** - Comprehensive status and metrics validation
6. **Error Handling** - Error reporting and recovery validation

This comprehensive approach ensures that all components work together correctly and that the system can handle both success and failure scenarios gracefully.

## Benefits of This Architecture

1. **Separation of Concerns** - Clear boundaries between template definition, workflow configuration, and execution
2. **Version Control** - Proper versioning through NiFi Registry integration
3. **Scalability** - Templates can be reused across multiple tenants and configurations
4. **Observability** - Comprehensive monitoring and error reporting
5. **Reliability** - Rollback capabilities and detailed error diagnostics
6. **Flexibility** - Parameter-driven configuration without hard-coded values

This architecture enables EDI Lens to provide a robust, scalable, and maintainable workflow management platform that leverages the strengths of both NiFi Registry for version control and Apache NiFi for data processing execution.