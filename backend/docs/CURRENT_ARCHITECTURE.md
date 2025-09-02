# Backend Architecture - Current Status

**Last Updated:** September 2025  
**Status:** ✅ Refactored to Registry-First Architecture

## Overview

The EDI Lens backend has been successfully refactored from a multi-service, mock-heavy architecture to a clean Registry-first architecture with two primary domain services.

## Architecture Principles

### Registry-First Design
- **NiFi Registry** is the source of truth for all flow definitions
- **PostgreSQL Database** stores only references, metadata, and business logic
- **No Mock Services** - All integration tests use real external services
- **Clean Service Separation** - Templates vs Workflows as distinct domains

## Core Services

### 1. TemplateService (`src/services/template_service.py`)
**Purpose:** Template management and NiFi Registry integration

**Responsibilities:**
- Template CRUD operations with Registry integration
- Built-in template seeding from YAML files (`data/templates/builtin/`)
- Registry bucket management (auto-creation and organization)
- Cross-tenant template access control

**Key Methods:**
```python
async def create_template(name, description, flow_definition, scope="GLOBAL", 
                         tenant_id=None, category="GENERAL", version="1.0.0", 
                         configuration_schema=None, created_by=None) -> RegistryTemplate

async def update_template(template_id, name=None, description=None, 
                         flow_definition=None, configuration_schema=None, 
                         comments=None) -> RegistryTemplate

async def delete_template(template_id: UUID) -> bool  # Soft delete

async def seed_templates() -> Dict[str, List]  # Seeds built-in templates from YAML

async def get_template_flow_definition(template_id: UUID, version: Optional[str] = None) -> Dict[str, Any]
```

**Registry Integration:**
- Creates flows in NiFi Registry buckets
- Handles bucket conflicts gracefully (reuses existing buckets)
- Stores flow versions with metadata
- Maintains database references to Registry IDs

### 2. WorkflowService (`src/services/workflow_service.py`)
**Purpose:** Workflow lifecycle management and execution

**Responsibilities:**
- Workflow CRUD operations (instances of templates)
- NiFi Canvas deployment from Registry flows
- Workflow execution with real content processing
- Status monitoring with NiFi integration
- Multi-tenant workflow isolation

**Key Methods:**
```python
async def create_workflow(template_id, name, tenant_id, configuration) -> Workflow

async def deploy_workflow(workflow_id: UUID) -> Workflow

async def execute_workflow(workflow_id: str, request: WorkflowExecutionRequest, 
                          auth_context: AuthContext) -> WorkflowExecutionResult

async def get_workflow_status(workflow_id: str, auth_context: AuthContext) -> Dict
```

**NiFi Integration:**
- Deploys process groups from Registry flows to NiFi Canvas
- Creates parameter contexts for configuration
- Manages workflow lifecycle (start/stop/pause/resume)
- Real-time status monitoring

## Removed/Consolidated Services

### ✅ Successfully Removed
- `RegistryService` → Renamed to `TemplateService` (cleaner domain focus)
- `WorkflowManagementService` → Consolidated into `WorkflowService`  
- `WorkflowExecutionService` → Consolidated into `WorkflowService`
- `WorkflowStatusService` → Consolidated into `WorkflowService`
- `BuiltInTemplateService` → Merged into `TemplateService.seed_templates()`
- `HealthService` → Removed (functionality moved to individual services)

### Service Consolidation Results
- **Before:** 6+ services with overlapping responsibilities and heavy mocking
- **After:** 2 clean domain services with real external service integration
- **Code Reduction:** ~400 lines of mock code removed
- **Architecture Clarity:** Clear separation between Templates and Workflows

## Database Models

### Registry Models (`src/models/registry_models.py`)

#### RegistryTemplate
```python
# Core Registry reference with business metadata
template_id: UUID (PK)    # Matches NiFi Registry flow ID  
bucket_id: UUID           # Registry bucket ID
current_version: int      # Version tracking
name: str                 # Template name
description: str          # Business description  
scope: str                # GLOBAL, TENANT
tenant_id: str           # NULL for global templates
status: str              # ACTIVE, DEPRECATED, ARCHIVED
is_featured: bool         # Featured templates
usage_count: int          # Usage tracking
created_by: str          # User who created template
created_at, updated_at   # Timestamps
deprecated_at            # Deprecation timestamp
```

#### RegistryBucket  
```python
# Registry bucket reference with metadata
bucket_id: UUID (PK)     # Matches NiFi Registry bucket ID
name: str               # Bucket name (e.g., "global-templates")
description: str         # Bucket description
scope: str              # GLOBAL, TENANT  
tenant_id: str          # NULL for global buckets
created_by: str         # User who created bucket
created_at, updated_at  # Timestamps
```

### Workflow Models (`src/models/workflow_models.py`)

#### Workflow
```python
# Workflow instances with NiFi Canvas integration
workflow_id: UUID (PK)           # Workflow instance ID
template_id: str                 # Reference to RegistryTemplate
name: str                        # Workflow instance name
description: str                 # Workflow description
tenant_id: str                   # Tenant isolation
status: str                      # CREATED, ACTIVE, PAUSED, DELETED
is_deployed: bool                # Deployed to NiFi Canvas
nifi_process_group_id: str       # NiFi Canvas process group ID  
nifi_parameter_context_id: str   # NiFi parameter context ID
nifi_registry_client_id: str     # NiFi registry client ID
version_control_info: JSON       # NiFi version control metadata
configuration: JSON              # Workflow-specific configuration
created_by: str                 # User who created workflow
created_at, updated_at          # Timestamps
deployed_at, undeployed_at      # Deployment lifecycle
last_started_at, last_stopped_at # Execution tracking
```

## API Endpoints

### Templates (`/api/v1/templates/`)
- `POST /` - Create template (requires `workflow:write` permission)
- `GET /` - List templates (tenant-aware, supports filtering)
- `GET /{id}` - Get template details
- `PUT /{id}` - Update template metadata (creates new Registry version)
- `DELETE /{id}` - Soft delete template (requires `workflow:write` permission)
- `POST /seed` - Seed built-in templates (admin only)
- `GET /{id}/flow-definition` - Get template flow definition from Registry

### Workflows (`/api/v1/workflows/`)  
- `POST /` - Create workflow instance
- `GET /` - List workflows (tenant-isolated)
- `GET /{id}` - Get workflow details
- `PUT /{id}` - Update workflow
- `DELETE /{id}` - Delete workflow
- `POST /{id}/deploy` - Deploy to NiFi Canvas
- `POST /{id}/undeploy` - Remove from NiFi Canvas
- `POST /{id}/execute` - Execute workflow with content
- `GET /{id}/status` - Get workflow status
- `POST /{id}/control` - Control workflow (start/stop/pause/resume)

## External Service Integration

### NiFi Registry (`nifi-registry:18080`)
**Purpose:** Source of truth for flow definitions

**Integration Points:**
- **Bucket Management:** Auto-creation of tenant/global buckets
- **Flow Storage:** All flow definitions stored as versioned flows
- **Version Control:** Flow versions tracked with metadata
- **Conflict Resolution:** Graceful handling of existing buckets/flows

### NiFi Canvas (`nifi:8443`)  
**Purpose:** Workflow execution environment

**Integration Points:**
- **Process Group Deployment:** Deploy Registry flows to Canvas
- **Parameter Context Management:** Configuration injection  
- **Lifecycle Control:** Start/stop/pause workflow execution
- **Status Monitoring:** Real-time execution status

### PostgreSQL Database
**Purpose:** Business metadata and references

**Integration Points:**
- **Reference Storage:** Registry and Canvas IDs
- **Business Logic:** Templates, workflows, tenant isolation
- **Audit Trail:** Creation, updates, usage tracking
- **Authorization:** Role-based access control

## Authentication & Authorization

### Multi-Tenant Architecture
- **Tenant Isolation:** Templates/workflows scoped by tenant
- **Global Templates:** Accessible across all tenants (admin-created)  
- **Role-Based Access:** `workflow:read`, `workflow:write`, `workflow:execute`, `admin`

### Headers Required
- `x-tenant-id` - Required for all API calls
- `Authorization` - JWT token with user/role claims

## Configuration

### Key Settings (`src/core/config.py`)
```python
# NiFi Integration
NIFI_URL = "http://nifi:8443/nifi-api"
NIFI_REGISTRY_URL = "http://nifi-registry:18080"
NIFI_USERNAME, NIFI_PASSWORD  # Authentication
NIFI_REGISTRY_AUTH_TOKEN     # Registry auth

# Database
DATABASE_URL = "postgresql+asyncpg://..."

# Built-in Templates  
TEMPLATES_DIR = "data/templates/builtin"
```

## Current Status Summary

✅ **Completed:**
- Registry-first architecture implementation
- Service consolidation (6 → 2 services)
- Database model alignment
- API endpoint refactoring  
- External service integration
- Authentication/authorization
- Built-in template seeding
- Template versioning with Registry
- Soft delete functionality
- Comprehensive API documentation

🔄 **In Progress:**
- Integration test refactoring (partially complete)
- Registry-database consistency validation
- Comprehensive error handling

📋 **Next Steps:**
- Complete integration test suite
- Add end-to-end EDI processor tests
- Performance testing and optimization
- Documentation completion