# NiFi Integration Architecture & Workflow Management

## Overview

The EDI Lens platform integrates with Apache NiFi to provide powerful, scalable workflow processing capabilities. This document explains the complete architecture, from template creation to workflow deployment and execution.

## Current Implementation Status

### ✅ Completed Features

1. **Template Management System**
   - YAML-based template definitions in `backend/data/templates/builtin/`
   - Built-in template seeding via `./run.sh dev:setup:templates`
   - Template API endpoints for CRUD operations
   - Template versioning and usage tracking

2. **Workflow CRUD Operations**
   - Create workflows from templates via REST API
   - List, update, and delete workflows
   - Proper tenant isolation and permission checks
   - Complete database models for workflow lifecycle

3. **NiFi Client Integration**
   - Full NiFi REST API client implementation
   - Parameter Context creation and management
   - Process Group creation and lifecycle management
   - Processor creation with dynamic property configuration
   - Connection creation between processors
   - Authentication handling with username/password

4. **Enhanced Deletion System**
   - Comprehensive workflow deletion with NiFi resource cleanup
   - Automatic cleanup of Parameter Contexts, Process Groups
   - Graceful error handling and partial failure recovery
   - Proper logging throughout deletion process

### 🔄 Current Issues & Debugging

#### Issue 1: Processor Configuration Updates (400 Bad Request)

**Problem:** During workflow deployment, processor property updates are failing with 400 Bad Request errors.

**Error Pattern:**
```
[ERROR] Failed to deploy workflow: 400, message='Bad Request', url='https://nifi:8443/nifi-api/processors/{processor-id}'
```

**Investigation:**
1. **Parameter Substitution Working:** Parameter contexts are created successfully with all configuration values
2. **Basic Processor Creation Working:** Processors are created in NiFi without properties
3. **Update Step Failing:** The subsequent property update call fails

**Attempted Solutions:**
1. ✅ Separated processor creation from configuration (create basic processor first, then update properties)
2. ✅ Added proper revision handling in update calls
3. ✅ Verified parameter substitution logic works correctly
4. ❌ Issue persists with complex property configurations

**Next Steps for Resolution:**
- Investigate specific property values causing the 400 error
- Test with minimal property sets to isolate problematic properties
- Check NiFi processor type compatibility (especially custom `EDIProcessor`)
- Verify property naming conventions match NiFi expectations

#### Issue 2: EDI Processor Dependency

**Problem:** The `edi-batch-processor-v2` template uses a custom `EDIProcessor` type that may not be properly registered in NiFi.

**Template Definition:**
```yaml
- id: "edi-processor-001"
  name: "Process EDI"
  type: "EDIProcessor"  # Custom processor type
  properties:
    "Validation Schema": "#{validation_schema}"
    "SNIP Level": "#{snip_level}"
    # ... other properties
```

**Investigation Needed:**
- Verify EDI processor is properly loaded in NiFi container
- Check processor registration and availability
- Validate custom processor property names and types

### 🧪 Testing Results

#### Workflow Lifecycle Testing
- ✅ Template seeding: 5 templates loaded successfully
- ✅ Workflow creation: Successfully created multiple workflows
- ✅ Parameter substitution: All configuration parameters properly injected
- ✅ Workflow deletion: Complete cleanup including NiFi resources
- ❌ Workflow deployment: Fails during processor property configuration

#### Test Commands Used
```bash
# Create workflow with complete configuration
TEST_JWT="..." python scripts/test_api.py -m POST -e /api/v1/workflows -d '{
  "name": "Complete EDI Test Workflow",
  "template_id": "edi-batch-processor-v2",
  "configuration": {
    "input_directory": "/edi-lens/complete-test/input",
    "output_directory": "/edi-lens/complete-test/output",
    "filename_filter": ".*\\.(edi|x12|txt)$",
    "polling_interval": "10 sec",
    "keep_source_file": "false",
    "validation_schema": "837.5010.X222.A1.json",
    "snip_level": "3",
    "generate_cdm": "true",
    "generate_ta1": "false",
    "max_concurrent_tasks": "1"
  }
}'

# Attempt deployment (currently fails)
TEST_JWT="..." python scripts/test_api.py -m POST -e /api/v1/workflows/{workflow-id}/deploy

# Test deletion (works correctly)
TEST_JWT="..." python scripts/test_api.py -m DELETE -e /api/v1/workflows/{workflow-id}
```

## Architecture Components

### 1. Core Integration Stack

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   EDI Lens      │    │   Apache NiFi   │    │  NiFi Registry  │
│   Backend       │◄──►│                 │◄──►│                 │
│                 │    │   Workflows     │    │   Templates     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
        │                       │                       │
        │              ┌─────────────────┐              │
        │              │   Parameter     │              │
        └──────────────┤   Contexts      │──────────────┘
                       └─────────────────┘
```

### 2. Key Services

- **NiFiWorkflowService** (`src/services/nifi_workflow_service.py`): Core workflow lifecycle management
- **NiFiAPIClient** (`src/nifi/clients/nifi_client.py`): Direct NiFi REST API integration
- **NiFiRegistryClient** (`src/nifi/clients/registry_client.py`): Template version management
- **BuiltInTemplatesService** (`src/nifi/services/built_in_templates_service.py`): Template loading and seeding

## Template System

### Template Structure

Templates are defined in YAML format with two main sections:

#### 1. Configuration Schema
Defines user-configurable parameters with UI generation metadata:

```yaml
# backend/data/templates/builtin/edi-batch-processor-v2.yaml
name: "EDI Batch Processor v2"
category: "BATCH"
description: "Consolidated EDI batch processing workflow"

configuration_schema:
  input_directory:
    type: "string"
    title: "Input Directory"
    description: "Directory to monitor for EDI files"
    default: "/data/input"
    required: true
    ui_component: "text"
    validation:
      pattern: "^/.*"
      message: "Must be an absolute path"
  
  validation_schema:
    type: "string"
    title: "Validation Schema"
    description: "EDI schema for validation"
    default: "837.5010.X222.A1.json"
    required: true
    ui_component: "select"
    options:
      - value: "837.5010.X222.A1.json"
        label: "837P - Professional Claims"
      - value: "835.5010.X221.A1.json"
        label: "835 - Payment Remittance"
```

#### 2. Flow Definition
Defines the actual NiFi processors and connections:

```yaml
flow_definition:
  processors:
    - id: "getfile-001"
      name: "Get EDI Files"
      type: "org.apache.nifi.processors.standard.GetFile"
      position:
        x: 100
        y: 200
      properties:
        "Input Directory": "#{input_directory}"
        "File Filter": "#{filename_filter}"
        "Keep Source File": "#{keep_source_file}"
        "Minimum File Age": "1 sec"
        "Polling Interval": "#{polling_interval}"
      scheduling:
        strategy: "TIMER_DRIVEN"
        period: "#{polling_interval}"
        concurrent_tasks: "#{max_concurrent_tasks}"
        
    - id: "edi-processor-001"
      name: "Process EDI"
      type: "EDIProcessor"
      position:
        x: 400
        y: 200
      properties:
        "Validation Schema": "#{validation_schema}"
        "SNIP Level": "#{snip_level}"
        "Generate CDM": "#{generate_cdm}"
        "Generate TA1": "#{generate_ta1}"
        
  connections:
    - id: "conn-001"
      name: "Files to Process"
      source:
        id: "getfile-001"
        type: "PROCESSOR"
      destination:
        id: "edi-processor-001"
        type: "PROCESSOR"
      selectedRelationships: ["success"]
      backPressureObjectThreshold: 1000
      backPressureDataSizeThreshold: "1 GB"
```

### Parameter Substitution

Templates use `#{parameter_name}` syntax for dynamic values that get substituted during deployment:

- `#{input_directory}` → `/data/input` (from workflow configuration)
- `#{tenant_id}` → `tenant-a` (from workflow context)
- `#{validation_schema}` → `837.5010.X222.A1.json` (from user configuration)

## Workflow Lifecycle

### 1. Template Loading and Seeding

Templates are loaded during application startup via the `seed_templates` process:

```bash
./run.sh dev:setup:templates
```

**Process:**
1. `BuiltInTemplatesService` scans `backend/data/templates/builtin/`
2. YAML files are parsed and validated
3. Templates are stored in PostgreSQL with `flow_definition` as JSONB
4. Configuration schemas are processed for UI generation

### 2. Workflow Creation

**API Endpoint:** `POST /api/v1/workflows`

```json
{
  "template_id": "edi-batch-processor-v2",
  "name": "My EDI Processing Workflow",
  "description": "Processes EDI claims files",
  "configuration": {
    "input_directory": "/data/input",
    "output_directory": "/data/output",
    "validation_schema": "837.5010.X222.A1.json",
    "snip_level": 3,
    "generate_cdm": true,
    "generate_ta1": false,
    "polling_interval": "10 sec",
    "max_concurrent_tasks": 1
  }
}
```

**Process:**
1. Validate `template_id` exists
2. Validate configuration against schema
3. Create `Workflow` record in database
4. Return workflow with unique `workflow_id`

### 3. Workflow Deployment

**API Endpoint:** `POST /api/v1/workflows/{workflow_id}/deploy`

**Deployment Process:**

#### Step 1: Parameter Context Creation
```python
# Creates NiFi parameter context with workflow configuration
param_context = await nifi_client.create_parameter_context(
    name=f"workflow-{workflow.workflow_id}",
    parameters=[
        {"name": "input_directory", "value": "/data/input"},
        {"name": "validation_schema", "value": "837.5010.X222.A1.json"},
        # ... other parameters
    ]
)
```

#### Step 2: Process Group Creation
```python
# Creates empty process group in NiFi
process_group = await nifi_client.create_process_group(
    parent_group_id=root_pg_id,
    name=f"{workflow.name}-{workflow.workflow_id}",
    position={"x": 100, "y": 100}
)
```

#### Step 3: Template Flow Instantiation
```python
# NEW: Complete template instantiation logic
await self._instantiate_template_flow(
    nifi_client, 
    process_group["component"]["id"], 
    template, 
    workflow,
    param_context
)
```

**Template Instantiation Process:**
1. **Parse Flow Definition**: Extract processors and connections from template
2. **Parameter Substitution**: Replace `#{param_name}` with actual values
3. **Create Processors**: 
   ```python
   for processor_def in processors:
       # Create basic processor
       processor = await nifi_client.create_processor(
           parent_group_id=process_group_id,
           processor_type=processor_def["type"],
           name=processor_def["name"],
           position=processor_def.get("position", {"x": 100, "y": 100})
       )
       
       # Configure processor properties
       await nifi_client.update_processor(
           processor_id=processor["component"]["id"],
           properties=substituted_properties,
           scheduling=processor_def.get("scheduling")
       )
   ```
4. **Create Connections**: Link processors based on flow definition
   ```python
   for conn_def in connections:
       await nifi_client.create_connection(
           source_id=processor_ids[conn_def["source"]["id"]],
           destination_id=processor_ids[conn_def["destination"]["id"]],
           relationships=conn_def.get("selectedRelationships", [])
       )
   ```

#### Step 4: Database Update
```python
workflow.update_nifi_deployment(
    process_group_id=process_group["component"]["id"],
    parameter_context_id=param_context["component"]["id"],
    deployment_method="registry",
    flow_version=1
)
```

### 4. Workflow Control

#### Start Workflow
**API Endpoint:** `POST /api/v1/workflows/{workflow_id}/start`

```python
async with NiFiAPIClient(settings.NIFI_URL, username=..., password=...) as client:
    await client.start_process_group(workflow.nifi_process_group_id)
```

#### Stop Workflow
**API Endpoint:** `POST /api/v1/workflows/{workflow_id}/stop`

#### Workflow Status
**API Endpoint:** `GET /api/v1/workflows/{workflow_id}/status`

Returns comprehensive status including:
- Deployment status
- NiFi process group state
- Processor states
- Health check results
- Execution metrics

### 5. Batch Processing Flow

For EDI batch processing workflows:

1. **File Monitoring**: GetFile processor monitors `input_directory`
2. **File Processing**: EDI files are processed by EDIProcessor
3. **Output Routing**: 
   - Success → `output_directory/success/`
   - Failure → `output_directory/failed/`
4. **Validation**: Schema validation based on `validation_schema` parameter
5. **CDM Generation**: Optional CDM output if `generate_cdm=true`
6. **TA1 Generation**: Optional TA1 acknowledgments if `generate_ta1=true`

## API Integration Examples

### Testing with Scripts

The platform includes comprehensive testing scripts:

```bash
# Test API connectivity
python scripts/test_api.py -e "/api/v1/workflow-templates"

# Create workflow
python scripts/test_api.py -m POST -e "/api/v1/workflows" -d '{
  "template_id": "edi-batch-processor-v2",
  "name": "Test Workflow",
  "configuration": {...}
}'

# Deploy workflow
python scripts/test_api.py -m POST -e "/api/v1/workflows/{id}/deploy"

# Check status
python scripts/test_api.py -e "/api/v1/workflows/{id}/status"
```

### Authentication

All API calls require JWT token authentication:

```bash
# Generate token
python scripts/auth_token_helper.py --user superuser@edilens.com

# Use token in requests
curl -H "Authorization: Bearer $TOKEN" http://localhost:3001/api/v1/workflows
```

## Configuration Management

### Environment Variables

Key NiFi integration settings:

```env
# .env.dev
NIFI_URL=https://nifi:8443
NIFI_REGISTRY_URL=http://nifi-registry:18080
NIFI_USERNAME=superuser@edilens.com
NIFI_PASSWORD=password123456789
NIFI_AUTH_TOKEN=""  # Optional: pre-generated token
NIFI_REGISTRY_AUTH_TOKEN=""  # Optional: registry token
```

### Security

- **Authentication**: Single-user provider for development, OIDC for production
- **SSL/TLS**: Self-signed certificates for development
- **API Access**: Token-based authentication with automatic renewal
- **Tenant Isolation**: Process groups and parameter contexts are tenant-scoped

## Advanced Features

### Custom Processors

The platform supports custom Python processors:

1. **EDIProcessor**: Custom processor for EDI validation and transformation
2. **Location**: `/opt/nifi/nifi-current/python_extensions/edi-processors/`
3. **Schema Support**: JSON schema-based validation
4. **CDM Generation**: Common Data Model output
5. **TA1 Generation**: EDI acknowledgment generation

### Monitoring and Observability

- **Health Checks**: Automated workflow health monitoring
- **Metrics**: Execution counts, success rates, error tracking
- **Logging**: Comprehensive logging throughout the workflow lifecycle
- **Status API**: Real-time workflow and processor status

## Troubleshooting

### Common Issues

#### 1. Deployment Failures
- **Parameter Context Conflicts**: Clear existing contexts or use unique names
- **Authentication Issues**: Verify NiFi credentials and token validity
- **Template Parsing**: Check YAML syntax and flow definition structure

#### 2. File Processing Issues
- **Directory Permissions**: Ensure NiFi can read/write to specified directories
- **File Filters**: Verify filename patterns and filters
- **Schema Validation**: Check EDI schema files are available

#### 3. Connection Issues
- **Network Connectivity**: Verify NiFi and Registry are accessible
- **SSL Certificates**: Check certificate validity for HTTPS connections
- **Service Health**: Ensure all services are healthy and running

### Debugging Commands

```bash
# Check NiFi connectivity
curl -k https://localhost:8443/nifi-api/system-diagnostics

# View workflow logs
docker logs backend --tail=50 | grep workflow

# Check NiFi process groups
curl -H "Authorization: Bearer $TOKEN" https://localhost:8443/nifi-api/process-groups/root

# Test template instantiation
python scripts/test_api.py -m POST -e "/api/v1/workflows/{id}/deploy" -v
```

## Development Workflow

### Adding New Templates

1. Create YAML template in `backend/data/templates/builtin/`
2. Define configuration schema and flow definition
3. Test parameter substitution
4. Seed templates: `./run.sh dev:setup:templates`
5. Test deployment and execution

### Extending NiFi Client

Add new methods to `NiFiAPIClient` for additional NiFi API functionality:

```python
async def create_custom_processor(self, ...):
    """Add custom processor creation logic"""
    pass

async def update_connection_properties(self, ...):
    """Add connection property updates"""
    pass
```

### Testing Integration

```bash
# Full integration test
./run.sh dev:clean
./run.sh dev:start
python scripts/test_api.py -e "/api/v1/workflow-templates"
# Create, deploy, and test workflow
```

## Troubleshooting & Next Steps

### Immediate Actions Required

1. **EDI Processor Investigation**
   ```bash
   # Check if EDI processor is available in NiFi
   docker exec -it nifi curl -k -u admin:admin123456789 \
     'https://localhost:8443/nifi-api/flow/processor-types' | \
     grep -i "edi"
   
   # Check Python extensions
   docker exec -it nifi ls -la /opt/nifi/nifi-current/python_extensions/
   ```

2. **Property Configuration Analysis**
   - Create minimal test workflow with only standard NiFi processors (GetFile, PutFile)
   - Test property updates with simple string values first
   - Gradually add complex properties to isolate the issue

3. **Alternative Template Testing**
   ```bash
   # Test with simpler Generic Batch Processor template
   TEST_JWT="..." python scripts/test_api.py -m POST -e /api/v1/workflows -d '{
     "name": "Generic Batch Test",
     "template_id": "global-generic-batch-processor-v1.0",
     "configuration": {
       "input_path": "/test/input",
       "file_patterns": ["*.txt"],
       "output_paths": {
         "success_archive": "/test/success",
         "error_archive": "/test/error"
       },
       "validation": {"strict_mode": false}
     }
   }'
   ```

### Debugging Strategy

1. **Simplify Template**
   - Create a minimal EDI template with only GetFile → PutFile processors
   - Remove custom EDI processor temporarily
   - Test basic file movement workflow first

2. **Property Validation**
   - Log exact property values being sent to NiFi API
   - Compare with NiFi documentation for property naming
   - Test each property individually

3. **NiFi Environment Check**
   - Verify custom processors are properly loaded
   - Check NiFi logs for processor registration errors
   - Ensure Python extensions are accessible

### Code Locations for Investigation

**Key Files to Examine:**
- `backend/src/services/nifi_workflow_service.py:486` - Property update logic
- `backend/src/nifi/clients/nifi_client.py:379` - NiFi processor update method
- `backend/data/templates/builtin/edi-batch-processor-v2.yaml` - Template definition
- `nifi-edi-processors/edi_processor.py` - Custom EDI processor implementation

**Logging Points:**
```python
# Add detailed logging in nifi_workflow_service.py
log.debug(f"Updating processor {processor_id} with properties: {properties}")
log.debug(f"NiFi API response status: {response.status}")
log.debug(f"NiFi API response body: {await response.text()}")
```

### Success Metrics

The deployment issue will be resolved when:
- ✅ Workflow deployment completes without 400 errors
- ✅ All processors are created and configured correctly
- ✅ Parameter substitution works for all property types
- ✅ Process groups are properly started and running
- ✅ End-to-end file processing works as expected

### Current Status Summary

**Working Components:**
- Template management and seeding ✅
- Workflow CRUD operations ✅ 
- Parameter context creation ✅
- Basic processor creation ✅
- Workflow deletion with cleanup ✅

**Blocked Components:**
- Processor property configuration ❌
- Full workflow deployment ❌
- End-to-end processing testing ❌

**Priority:** Resolve processor property update issue to unblock workflow deployment and testing.
```

## Future Enhancements

- **Dynamic Template Creation**: UI-based template builder
- **Workflow Versioning**: Template and workflow version management  
- **Advanced Monitoring**: Prometheus metrics integration
- **Multi-Tenant Security**: Enhanced tenant isolation
- **Workflow Orchestration**: Complex workflow dependencies and scheduling
- **Real-time Processing**: Stream processing capabilities

---

*Last updated: 2025-08-28*
*Version: 1.0*