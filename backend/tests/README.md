# Backend Test Organization

This directory contains all backend tests organized by test type and functionality.

## Test Structure

### 🔧 Unit Tests (`unit/`)
Fast, isolated tests with no external dependencies (database, NiFi, Registry, etc.)

#### Core Business Logic (`unit/core/`)
- `test_auth_service.py` - Authentication and authorization logic
- `test_audit_service.py` - Audit logging and tracking
- `test_schema_manager.py` - Schema validation and management
- `test_template_service.py` - Template management service
- `test_workflow_service.py` - Workflow orchestration service

#### Data Models (`unit/models/`)
- `test_edi_schema_models.py` - EDI schema data models

#### External Clients (`unit/clients/`)
- `test_nifi_client.py` - NiFi API client unit tests

#### Utilities (`unit/utils/`)
- `test_auth_helpers.py` - Authentication utility functions
- `test_jwt_utils.py` - JWT token utilities
- `test_storage_utils.py` - Storage and file utilities

### 🔗 Integration Tests (`integration/`)
Component interaction tests with external dependencies

#### API Endpoints (`integration/api/`)
- `test_auth_endpoints.py` - Authentication API endpoints
- `test_health_endpoints.py` - Health check endpoints
- `test_main_endpoints.py` - Main application endpoints
- `test_registry_endpoints.py` - Registry template API endpoints
- `test_workflow_endpoints.py` - Workflow execution endpoints

#### Database Integration (`integration/database/`)
- `test_database_extensions.py` - Database extensions and utilities
- `test_registry_persistence.py` - Registry data persistence
- `test_workflow_persistence.py` - Workflow data persistence

#### NiFi Integration (`integration/nifi/`)
- `test_nifi_connectivity.py` - NiFi connection and health
- `test_nifi_deployment.py` - Workflow deployment to NiFi
- `test_nifi_error_handling.py` - NiFi error recovery
- `test_nifi_template_management.py` - NiFi template operations
- `test_nifi_version_control.py` - NiFi version control integration

#### Registry Integration (`integration/registry/`)
- `test_registry_connectivity.py` - Registry connection and health
- `test_registry_multi_tenant.py` - Multi-tenant registry operations
- `test_registry_template_operations.py` - Template CRUD operations
- `test_registry_versioning.py` - Template versioning and seeding

#### External Services (`integration/external/`)
- `test_keycloak_integration.py` - Keycloak authentication integration

### 🌐 End-to-End Tests (`e2e/`)
Complete business workflows and user scenarios

#### Complete Workflows (`e2e/workflows/`)
- `test_edi_processing_complete.py` - Complete EDI processing workflow
- `test_template_lifecycle_complete.py` - Template creation to deployment
- `test_workflow_deployment_complete.py` - Full workflow deployment lifecycle

#### System Validation (`e2e/system/`)
- `test_system_health_complete.py` - Full system health validation

## Running Tests

### Run by Test Type
```bash
# Unit tests only (fast)
./run.sh dev:test unit

# Integration tests only
./run.sh dev:test integration

# E2E tests only
./run.sh dev:test e2e
```

### Run by Component
```bash
# All NiFi-related tests
./run.sh dev:test integration/nifi

# All Registry-related tests
./run.sh dev:test integration/registry

# All API tests
./run.sh dev:test integration/api
```

### Run Specific Functionality
```bash
# Authentication tests
./run.sh dev:test -k "auth"

# Template management tests
./run.sh dev:test -k "template"

# Workflow tests
./run.sh dev:test -k "workflow"
```

## Test Guidelines

### Unit Tests
- No external dependencies (mock everything)
- Fast execution (< 1 second per test)
- Test single functions/methods
- High code coverage

### Integration Tests
- Test component interactions
- Use real external services (database, NiFi, Registry)
- Moderate execution time (< 30 seconds per test)
- Test API contracts and data flow

### E2E Tests
- Test complete user workflows
- Use full system stack
- Longer execution time acceptable
- Test business scenarios

## Debugging Tests

### Find Tests by Functionality
- **Authentication**: Look in `unit/core/test_auth_service.py` and `integration/api/test_auth_endpoints.py`
- **NiFi Issues**: Check `integration/nifi/` directory
- **Registry Issues**: Check `integration/registry/` directory
- **Database Issues**: Check `integration/database/` directory
- **API Issues**: Check `integration/api/` directory
- **Complete Workflows**: Check `e2e/workflows/` directory

### Test Naming Convention
- `test_<functionality>_<scenario>.py` - Clear indication of what is tested
- Test classes: `Test<Component><TestType>` (e.g., `TestNiFiConnectivity`)
- Test methods: `test_<action>_<expected_result>` (e.g., `test_deploy_workflow_success`)