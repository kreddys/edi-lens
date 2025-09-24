# EDI Lens Backend - Current Architecture

## Overview

The EDI Lens backend implements a **deployment-first workflow architecture** for managing NiFi flows with integrated Registry version control. The system follows a domain-driven design with clear separation between API, services, and clients.

## Architecture Pattern

### Deployment-First Workflow
```
Flow Definition → Deploy to NiFi → Upload to Registry with Version Control
                (permanent)      (linked deployment)
```

**Key Benefits:**
- ✅ Immediate validation in real NiFi environment
- ✅ Automatic version control integration
- ✅ No temporary components or cleanup needed
- ✅ Single-step deployment process

## System Architecture

### Layer Overview
```
┌─────────────────────────────────────────────────────────────┐
│                      API Layer                             │
│  POST /api/flows/deploy-and-store                          │
│  GET  /api/flows/{id}/status                               │
│  POST /api/flows/{id}/start|stop                           │
│  POST /api/flows/{id}/version-control/commit|update        │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                   Service Layer                            │
│  WorkflowOrchestrator (Main Orchestration)                 │
│  ├── NiFiFlowDeployment                                    │
│  ├── IntegrationBridge (NiFi ↔ Registry)                   │
│  ├── NiFiFlowManagement                                    │
│  ├── RegistryFlowManagement                                │
│  └── Parameter Management                                   │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                   Client Layer                             │
│  NiFiUnifiedClient          RegistryUnifiedClient          │
│  ├── process_groups         ├── buckets                    │
│  ├── processors             ├── flows                      │
│  ├── connections            └── versions                   │
│  ├── parameters                                            │
│  └── version_control                                       │
└─────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. API Layer (`src/api/routes/flows.py`)

#### Primary Endpoint
- **`POST /api/flows/deploy-and-store`** - Main deployment-first workflow
  - Deploys flow to NiFi
  - Uploads to Registry with version control
  - Returns comprehensive deployment result

#### Flow Management
- **`GET /api/flows/{id}/status`** - Get comprehensive flow status
- **`POST /api/flows/{id}/start`** - Start all processors
- **`POST /api/flows/{id}/stop`** - Stop all processors
- **`DELETE /api/flows/{id}`** - Delete flow (optionally from Registry)

#### Version Control Operations
- **`POST /api/flows/{id}/version-control/commit`** - Commit changes to Registry
- **`POST /api/flows/{id}/version-control/update`** - Pull latest from Registry
- **`POST /api/flows/{id}/version-control/revert`** - Revert local changes
- **`GET /api/flows/{id}/version-control/modifications`** - Show local changes

### 2. Service Layer

#### WorkflowOrchestrator (`src/services/workflow_orchestrator.py`)
**Main orchestration service that coordinates all domain services.**

**Key Methods:**
```python
async def deploy_and_register_flow(
    flow_definition: Dict,
    flow_name: str,
    bucket_name: str,
    parameters: Dict = None,
    comments: str = ""
) -> Dict:
    """
    1. Deploy flow to NiFi with parameters
    2. If successful, upload to Registry for version control
    """

async def import_and_deploy_flow(
    bucket_id: str,
    flow_id: str,
    version: int = None,
    parameters: Dict = None
) -> Dict:
    """Import flow from Registry and deploy to NiFi with parameters."""

async def get_flow_overview(process_group_id: str) -> Dict:
    """Get comprehensive flow status including version control info."""
```

#### Domain Services

**NiFiFlowDeployment** (`src/services/nifi_flow_deployment.py`)
- Flow deployment and validation in NiFi
- Parameter context creation and assignment
- Component lifecycle management

**IntegrationBridge** (`src/services/integration_bridge.py`)
- NiFi ↔ Registry integration operations
- Version control setup and management
- Flow synchronization (push/pull)
- Registry upload and import

**NiFiFlowManagement** (`src/services/nifi_flow_management.py`)
- Flow status monitoring
- Start/stop operations
- Process group management

**RegistryFlowManagement** (`src/services/registry_flow_management.py`)
- Registry flow operations
- Flow versioning
- Bucket management integration

### 3. Client Layer

#### NiFiUnifiedClient (`src/clients/nifi_unified.py`)
**Unified client providing access to all NiFi operations.**

**Components:**
- `process_groups` - Process group CRUD operations
- `processors` - Processor configuration and management
- `connections` - Flow connections and relationships
- `parameter_contexts` - Parameter management
- `version_control` - Version control operations

#### RegistryUnifiedClient (`src/clients/registry_unified.py`)
**Unified client for Registry operations.**

**Components:**
- `buckets` - Bucket management
- `flows` - Flow operations
- `versions` - Version management

## Workflow Patterns

### 1. Deploy and Store Workflow

```python
# Primary workflow - deployment-first
result = await orchestrator.deploy_and_register_flow(
    flow_definition={
        "processors": [...],
        "connections": [...]
    },
    flow_name="my-edi-flow",
    bucket_name="edi-processing",
    parameters={"threshold": "100"},
    comments="Initial deployment"
)

# Result structure:
{
    "workflow": "deploy_and_register",
    "success": True,
    "stage": "completed",
    "nifi_deployment": {
        "process_group_id": "pg-123",
        "parameter_context_id": "pc-456"
    },
    "registry_upload": {
        "flow_id": "flow-789",
        "version": 1
    },
    "bucket_info": {
        "bucket_id": "bucket-abc"
    }
}
```

### 2. Import and Deploy Workflow

```python
# Import existing flow from Registry
result = await orchestrator.import_and_deploy_flow(
    bucket_id="bucket-abc",
    flow_id="flow-789",
    version=2,  # Optional - latest if not specified
    parameters={"new_param": "value"}
)
```

### 3. Version Control Operations

```python
# Commit local changes
await orchestrator.integration_bridge.sync_flow_with_registry(
    process_group_id="pg-123",
    action="push"
)

# Pull latest from Registry
await orchestrator.integration_bridge.sync_flow_with_registry(
    process_group_id="pg-123", 
    action="pull"
)

# Compare with Registry
comparison = await orchestrator.integration_bridge.compare_with_registry(
    process_group_id="pg-123"
)
```

## Configuration

### Environment Variables (`.env.local`)
```bash
# NiFi Configuration
NIFI_URL=https://localhost:8443
NIFI_USERNAME=admin
NIFI_PASSWORD=adminadmin123
NIFI_VERIFY_SSL=false

# Registry Configuration  
NIFI_REGISTRY_URL=http://localhost:18080
REGISTRY_VERIFY_SSL=false

# Database Configuration
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/edi_lens

# Application Configuration
DEBUG=true
APP_VERSION=0.1.0
```

## Error Handling

### Staged Error Response
The system provides detailed error information with actionable guidance:

```python
{
    "workflow": "deploy_and_register",
    "success": False,
    "stage": "nifi_deployment",  # Where failure occurred
    "nifi_deployment": {
        "success": False,
        "errors": [...]
    },
    "message": "Flow deployment to NiFi failed"
}
```

### Error Types
- **`nifi_deployment`** - Issues with NiFi deployment
- **`registry_upload`** - Registry upload failures
- **`version_control`** - Version control setup issues
- **`parameter_application`** - Parameter configuration problems

## Testing Strategy

### Service Layer Testing
```python
# Test the orchestrator directly
async def test_deploy_and_register_workflow():
    orchestrator = WorkflowOrchestrator(nifi_client, registry_client)
    
    result = await orchestrator.deploy_and_register_flow(
        flow_definition=test_flow,
        flow_name="test-flow",
        bucket_name="test-bucket"
    )
    
    assert result["success"] is True
    assert result["stage"] == "completed"
```

### API Layer Testing
```python
# Test the REST endpoints
async def test_deploy_and_store_endpoint():
    response = await client.post("/api/flows/deploy-and-store", json={
        "flow_definition": test_flow,
        "flow_name": "test-flow",
        "bucket_id": "test-bucket"
    })
    
    assert response.status_code == 201
    assert response.json()["success"] is True
```

## Monitoring and Observability

### Logging
- **Request/Response Logging** - All API calls with timing
- **Service Operation Logging** - Domain service operations
- **Error Logging** - Detailed error tracking with context
- **Audit Logging** - System events and user actions

### Metrics
- **Deployment Success Rate** - Track workflow success/failure
- **Response Times** - API and service layer performance
- **Resource Usage** - NiFi and Registry resource consumption

## Development Guidelines

### Adding New Workflows
1. **Create Service Method** in `WorkflowOrchestrator`
2. **Add API Endpoint** in `src/api/routes/flows.py`
3. **Define Request/Response Models** in `src/models/flow_models.py`
4. **Write Tests** for both service and API layers

### Client Extensions
1. **Add Client Module** in `src/clients/`
2. **Register in Unified Client** (`nifi_unified.py` or `registry_unified.py`)
3. **Create Service Wrapper** if needed
4. **Update Orchestrator** to use new functionality

### Error Handling Standards
- **Service Layer** - Raise descriptive exceptions
- **API Layer** - Return structured error responses
- **Client Layer** - Handle HTTP errors gracefully
- **Always** provide actionable error messages

This architecture provides a robust, scalable foundation for NiFi workflow management with integrated version control and comprehensive error handling.