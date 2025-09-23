# Backend Architecture

## Overview

This backend implements a deployment-first NiFi workflow management system with clean separation of concerns and logical file organization.

## Architecture Principles

1. **Deployment-First Workflow**: Deploy and validate flows in NiFi first, then upload to Registry with version control
2. **Logical File Grouping**: Small, focused files grouped by functionality (nifi_*, registry_*)
3. **Clean Separation**: Clients handle API calls, services handle business logic
4. **Unified Interfaces**: Single entry points for complex operations

## File Structure

```
backend/src/
├── clients/                    # API client layer
│   ├── nifi_base.py           # Core NiFi HTTP operations
│   ├── nifi_unified.py        # Unified NiFi client interface
│   ├── nifi_process_groups.py # Process group operations
│   ├── nifi_processors.py     # Processor operations
│   ├── nifi_connections.py    # Connection operations
│   ├── nifi_parameter_contexts.py # Parameter context operations
│   ├── nifi_version_control.py # Version control operations
│   ├── registry_base.py       # Core Registry HTTP operations
│   ├── registry_unified.py    # Unified Registry client interface
│   ├── registry_buckets.py    # Bucket operations
│   └── registry_flows.py      # Flow operations
├── services/                   # Business logic layer
│   ├── flow_service.py        # Main orchestration service
│   ├── nifi_deployment_service.py # Deployment and validation
│   ├── nifi_version_control_service.py # Version control integration
│   └── registry_flow_service.py # Registry operations
├── api/
│   ├── routes/
│   │   └── flows.py           # Flow management endpoints
│   └── dependencies.py       # Dependency injection
├── models/
│   └── flow_models.py         # Pydantic models
└── core/
    ├── config.py             # Configuration management
    ├── logging.py            # Logging setup
    └── database.py           # Database connection
```

## Main Workflow

### Deploy and Store Flow

```python
# Main endpoint: POST /flows/deploy-and-store
async def deploy_and_store_flow():
    # 1. Deploy to NiFi with parameter context
    # 2. Validate in runtime environment
    # 3. Upload to Registry with version control
    # 4. Return comprehensive result
```

**Benefits:**
- Single API call for complete workflow
- Real validation in actual NiFi environment
- Automatic version control setup
- Better error feedback with actionable details

### Client Architecture

**NiFi Clients:**
- `nifi_base.py` - Core HTTP operations (auth, requests)
- `nifi_unified.py` - Single interface for all NiFi operations
- Specialized clients for specific operations (process groups, processors, etc.)

**Registry Clients:**
- `registry_base.py` - Core HTTP operations
- `registry_unified.py` - Single interface for all Registry operations
- Specialized clients for buckets and flows

### Service Architecture

**Main Service (`flow_service.py`):**
- Orchestrates the complete workflow
- Integrates NiFi deployment with Registry storage
- Handles version control operations

**Specialized Services:**
- `nifi_deployment_service.py` - NiFi deployment logic
- `nifi_version_control_service.py` - Version control operations
- `registry_flow_service.py` - Registry operations

## Key Features

1. **Resource Efficiency**: No temporary component creation/cleanup cycles
2. **Better Error Handling**: Detailed, actionable error messages with specific fix suggestions
3. **Version Control Integration**: Automatic NiFi ↔ Registry linking
4. **Real Validation**: Validation in actual runtime environment vs. temporary setup
5. **Clean APIs**: Logically organized endpoints with consistent patterns

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
- `GET /flows/{process_group_id}/status` - Get flow status
- `POST /flows/{process_group_id}/start|stop` - Control flow execution
- `DELETE /flows/{process_group_id}` - Delete flow

### Version Control
- `POST /flows/{process_group_id}/version-control/commit` - Commit changes
- `POST /flows/{process_group_id}/version-control/update` - Update from Registry
- `POST /flows/{process_group_id}/version-control/revert` - Revert changes

### Registry Access
- `GET /flows/registry/buckets` - List buckets
- `GET /flows/registry/buckets/{bucket_id}/flows` - List flows
- `GET /flows/registry/buckets/{bucket_id}/flows/{flow_id}` - Get flow

## Usage Examples

### Deploy a Flow

```python
request = DeployAndStoreFlowRequest(
    bucket_id="my-bucket",
    flow_definition=FlowDefinition(
        name="My Flow",
        processors=[...],
        connections=[...]
    ),
    parameters={"param1": "value1"}
)

response = await client.post("/flows/deploy-and-store", json=request.dict())
```

### Check Flow Status

```python
status = await client.get("/flows/{process_group_id}/status")
```

### Commit Changes

```python
await client.post(
    f"/flows/{process_group_id}/version-control/commit",
    params={"comments": "Updated flow logic"}
)
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

## Development

1. All new clients follow the `{system}_{operation}.py` pattern
2. Services orchestrate multiple clients for business logic
3. Use unified clients for external interfaces
4. Follow the deployment-first workflow pattern
5. Provide detailed error messages with actionable feedback