# Backend Architecture

## Overview

This backend implements a deployment-first NiFi workflow management system with domain-based service architecture, clean separation of concerns, and crystal-clear responsibilities.

## Architecture Principles

1. **Deployment-First Workflow**: Deploy and validate flows in NiFi first, then upload to Registry with version control
2. **Domain-Based Services**: Single-responsibility services grouped by domain and operation type
3. **Crystal Clear Responsibilities**: No ambiguous service names or mixed client usage
4. **Logical File Grouping**: Small, focused files grouped by functionality (nifi_*, registry_*)
5. **Clean Separation**: Clients handle API calls, services handle business logic, orchestrator coordinates workflows

## File Structure

```
backend/src/
├── clients/                           # API client layer
│   ├── nifi_base.py                  # Core NiFi HTTP operations
│   ├── nifi_unified.py               # Unified NiFi client interface
│   ├── nifi_process_groups.py        # Process group CRUD operations
│   ├── nifi_processors.py            # Processor management operations
│   ├── nifi_connections.py           # Connection management
│   ├── nifi_parameter_contexts.py    # Parameter context operations
│   ├── nifi_version_control.py       # Version control integration with Registry
│   ├── registry_base.py              # Core Registry HTTP operations
│   ├── registry_unified.py           # Unified Registry client interface
│   ├── registry_buckets.py           # Bucket management operations
│   └── registry_flows.py             # Flow and version management in Registry
├── services/                          # Domain-based service layer
│   ├── nifi_flow_deployment.py       # NiFi flow deployment and validation
│   ├── nifi_flow_management.py       # NiFi flow lifecycle (start/stop/delete/status)
│   ├── nifi_parameter_management.py  # NiFi parameter context management
│   ├── registry_bucket_management.py # Registry bucket operations
│   ├── registry_flow_management.py   # Registry flow operations
│   ├── registry_version_management.py # Registry version operations
│   ├── integration_bridge.py         # NiFi ↔ Registry integration
│   └── workflow_orchestrator.py      # Main orchestration service
├── api/
│   ├── routes/
│   │   ├── flows.py                  # Flow management endpoints
│   │   └── health.py                 # Health check endpoints
│   └── dependencies.py              # Dependency injection
├── models/
│   ├── flow_models.py                # Flow-related Pydantic models
│   └── health.py                     # Health check models
└── core/
    ├── config.py                     # Configuration management
    ├── logging.py                    # Logging setup
    └── database.py                   # Database connection
```

## Domain-Based Service Architecture

### NiFi Domain Services

**`nifi_flow_deployment.py`**
- **Single Responsibility**: Deploy and validate flows in NiFi
- **Key Methods**: `deploy_flow()`, `cleanup_failed_deployment()`
- **Client Usage**: Only NiFi unified client

**`nifi_flow_management.py`**
- **Single Responsibility**: Flow lifecycle operations (start/stop/delete/status)
- **Key Methods**: `start_flow()`, `stop_flow()`, `delete_flow()`, `get_flow_status()`, `list_flows()`
- **Client Usage**: Only NiFi unified client

**`nifi_parameter_management.py`**
- **Single Responsibility**: Parameter context management
- **Key Methods**: `create_parameter_context()`, `update_parameter_context()`, `assign_parameter_context_to_process_group()`
- **Client Usage**: Only NiFi unified client

### Registry Domain Services

**`registry_bucket_management.py`**
- **Single Responsibility**: Registry bucket operations
- **Key Methods**: `create_bucket()`, `get_bucket()`, `list_buckets()`, `get_or_create_bucket()`
- **Client Usage**: Only Registry unified client

**`registry_flow_management.py`**
- **Single Responsibility**: Registry flow operations
- **Key Methods**: `create_flow()`, `get_flow()`, `list_flows_in_bucket()`, `get_or_create_flow()`
- **Client Usage**: Only Registry unified client

**`registry_version_management.py`**
- **Single Responsibility**: Registry version operations
- **Key Methods**: `create_flow_version()`, `get_flow_version()`, `get_latest_flow_version()`, `export_flow_version()`
- **Client Usage**: Only Registry unified client

### Integration and Orchestration Services

**`integration_bridge.py`**
- **Single Responsibility**: NiFi ↔ Registry integration operations
- **Key Methods**: `upload_flow_to_registry()`, `import_flow_from_registry()`, `sync_flow_with_registry()`
- **Client Usage**: Both NiFi and Registry unified clients

**`workflow_orchestrator.py`**
- **Single Responsibility**: Coordinate domain services for complete workflows
- **Key Methods**: `deploy_and_register_flow()`, `import_and_deploy_flow()`, `get_flow_overview()`
- **Service Usage**: Coordinates all domain services

## Main Workflows

### Deploy and Register Flow (Deployment-First)

```python
# Main workflow method: orchestrator.deploy_and_register_flow()
async def deploy_and_register_flow():
    # 1. Deploy to NiFi with parameters (nifi_flow_deployment)
    # 2. Validate in runtime environment
    # 3. If successful, upload to Registry (integration_bridge)
    # 4. Link version control
    # 5. Return comprehensive result
```

**Benefits:**
- Real validation in actual NiFi environment
- No temporary component cleanup cycles
- Automatic version control setup
- Better error feedback with specific details

### Import and Deploy Flow

```python
# Import from Registry and deploy to NiFi
async def import_and_deploy_flow():
    # 1. Import flow from Registry (integration_bridge)
    # 2. Deploy to NiFi with version control links
    # 3. Apply parameter contexts if provided
    # 4. Return deployment status
```

### Flow Lifecycle Management

```python
# Complete flow lifecycle operations
async def start_flow_workflow():
    # 1. Start all processors (nifi_flow_management)
    # 2. Get comprehensive status
    # 3. Return workflow result

async def get_flow_overview():
    # 1. Get NiFi status (nifi_flow_management)
    # 2. Get version control info (integration_bridge)
    # 3. Get parameter context info (nifi_parameter_management)
    # 4. Return unified overview
```

## Client Architecture

### NiFi Clients
- `nifi_base.py` - Core HTTP operations (auth, requests)
- `nifi_unified.py` - Single interface for all NiFi operations
- Specialized clients for specific operations (process groups, processors, etc.)
- Health check methods in unified client

### Registry Clients
- `registry_base.py` - Core HTTP operations
- `registry_unified.py` - Single interface for all Registry operations
- Specialized clients for buckets and flows
- Health check methods in unified client

## Key Features

1. **Single Responsibility Principle**: Each service has one clear, well-defined responsibility
2. **Crystal Clear Naming**: Service names explicitly indicate their domain and operation type
3. **Pure Domain Services**: NiFi services only use NiFi clients, Registry services only use Registry clients
4. **Resource Efficiency**: No temporary component creation/cleanup cycles
5. **Better Error Handling**: Detailed, actionable error messages with specific fix suggestions
6. **Version Control Integration**: Automatic NiFi ↔ Registry linking
7. **Real Validation**: Validation in actual runtime environment vs. temporary setup
8. **Workflow Orchestration**: High-level workflows that combine multiple domain operations

## Configuration

Configuration uses snake_case with environment aliases:

```python
class Settings(BaseSettings):
    # NiFi settings
    nifi_url: str = Field(alias="NIFI_URL")
    nifi_username: Optional[str] = Field(alias="NIFI_USERNAME")
    nifi_password: Optional[str] = Field(alias="NIFI_PASSWORD")
    nifi_verify_ssl: bool = Field(alias="NIFI_VERIFY_SSL")

    # Registry settings
    registry_url: str = Field(alias="NIFI_REGISTRY_URL")
    registry_auth_token: Optional[str] = Field(alias="NIFI_REGISTRY_AUTH_TOKEN")
    registry_verify_ssl: bool = Field(alias="REGISTRY_VERIFY_SSL")
```

## API Endpoints

### Main Workflow
- `POST /flows/deploy-and-store` - Deploy to NiFi and store in Registry
- `GET /flows/{process_group_id}/status` - Get comprehensive flow overview
- `POST /flows/{process_group_id}/start|stop` - Control flow execution
- `DELETE /flows/{process_group_id}` - Delete flow (optionally from Registry too)

### Version Control
- `POST /flows/{process_group_id}/version-control/commit` - Commit changes to Registry
- `POST /flows/{process_group_id}/version-control/update` - Update from Registry
- `POST /flows/{process_group_id}/version-control/revert` - Revert local changes
- `GET /flows/{process_group_id}/version-control/modifications` - Check local modifications

### Registry Access
- `GET /flows/registry/buckets` - List buckets
- `GET /flows/registry/buckets/{bucket_id}/flows` - List flows in bucket
- `GET /flows/registry/buckets/{bucket_id}/flows/{flow_id}` - Get flow version

### Health Checks
- `GET /health` - Application health
- `GET /health/nifi` - NiFi connectivity
- `GET /health/registry` - Registry connectivity

## Service Dependencies

```
workflow_orchestrator.py
├── nifi_flow_deployment.py         → nifi_unified.py
├── nifi_flow_management.py         → nifi_unified.py
├── nifi_parameter_management.py    → nifi_unified.py
├── registry_bucket_management.py   → registry_unified.py
├── registry_flow_management.py     → registry_unified.py
├── registry_version_management.py  → registry_unified.py
└── integration_bridge.py           → nifi_unified.py + registry_unified.py
```

## Usage Examples

### Deploy a Flow (Deployment-First)

```python
request = DeployAndStoreFlowRequest(
    bucket_id="my-bucket",  # Will be treated as bucket name
    flow_definition=FlowDefinition(
        name="My Flow",
        processors=[...],
        connections=[...]
    ),
    parameters={"param1": "value1"}
)

response = await client.post("/flows/deploy-and-store", json=request.dict())
```

### Get Comprehensive Flow Status

```python
# Returns NiFi status + Registry info + parameter context info
status = await client.get("/flows/{process_group_id}/status")
```

### Sync with Registry

```python
# Commit local changes to Registry
await client.post(
    f"/flows/{process_group_id}/version-control/commit",
    params={"comments": "Updated flow logic"}
)

# Pull latest changes from Registry
await client.post(f"/flows/{process_group_id}/version-control/update")
```

## Error Handling

All errors include:
- `error_type`: Classification of the error
- `user_message`: Human-readable explanation
- `action_required`: Specific steps to resolve
- `details`: Additional technical information

Example:
```json
{
  "error_type": "DEPLOYMENT_FAILED",
  "user_message": "Processor validation failed",
  "action_required": "Fix processor configuration and retry",
  "details": {
    "component_type": "processor",
    "component_name": "MyProcessor",
    "validation_errors": ["Missing required property 'Directory'"]
  }
}
```

## Testing

Run tests with:
```bash
# Unit tests
python -m pytest tests/unit/

# Integration tests
python -m pytest tests/integration/

# E2E tests
python -m pytest tests/e2e/
```

## Development Guidelines

1. **Service Naming**: Follow `{system}_{domain}_management.py` pattern
2. **Single Responsibility**: Each service should have one clear purpose
3. **Pure Domain Services**: Services should only use clients from their domain
4. **Client Usage**: Use unified clients for external interfaces
5. **Error Messages**: Provide detailed, actionable error feedback
6. **Workflow Orchestration**: Use the orchestrator for multi-step operations
7. **No "Improved" Naming**: Use clear, descriptive names without marketing terms

## Architecture Benefits

1. **Maintainability**: Small, focused files (~200-350 lines each)
2. **Testability**: Single responsibility makes unit testing easier
3. **Extensibility**: New features can be added to specific domains
4. **Clarity**: Crystal clear service responsibilities and naming
5. **Separation of Concerns**: Clean boundaries between NiFi, Registry, and integration logic
6. **Workflow Composition**: Complex operations built from simple domain services