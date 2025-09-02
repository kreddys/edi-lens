# Backend Test Organization

This directory contains all backend tests organized by test type and functionality.

## 📊 Current Test Status

**Last Updated:** 2025-09-02

### Test Summary
- **Total Test Files:** 34
- **Unit Tests:** 28 failed, 86 passed, 26 errors ❌
- **Integration Tests:** 2 failed, 111 passed ⚠️
- **E2E Tests:** 14 passed ✅

### Recent Improvements (Phase 1 - High Priority Fixes)
✅ **Completed:**
- Fixed outdated `test_workflow_persistence.py` - replaced with Registry-first `test_registry_template_persistence.py`
- Fixed `test_nifi_error_handling.py` template creation patterns to use Registry-first architecture
- Created comprehensive unit tests for `RegistryService` (was completely missing)
- Created comprehensive unit tests for `WorkflowExecutionService` (was completely missing) 
- Created API unit tests for registry endpoints (was completely missing)
- Enhanced schema management unit tests

### Known Issues
🔴 **Unit Test Failures (28 failed, 26 errors):**
- New unit tests need import fixes and missing method implementations
- Registry endpoint tests missing some endpoint functions
- Workflow execution service tests need method mocking fixes

🟡 **Integration Test Issues (2 failed):**
- `test_nifi_error_handling.py`: Database connection cleanup issues
- Concurrent deployment tests failing due to database session conflicts

### Architecture Validation Status
✅ **Registry-First Architecture:** Tests now properly validate the current Registry-first architecture where:
- NiFi Registry is the source of truth for workflow definitions
- RegistryService.create_template() creates flows in both Registry and database
- Templates use RegistryTemplate model (not legacy WorkflowTemplate)

✅ **Legacy Pattern Cleanup:** All legacy WorkflowTemplate patterns have been removed from tests

### Test Coverage Analysis
**Well Covered:** 
- ✅ Integration tests (113 tests) - good coverage of NiFi, Registry, Database, API endpoints
- ✅ E2E tests (14 tests) - full workflow scenarios working properly

**Recently Added (New Unit Tests):**
- ✅ `test_registry_service.py` - 21 comprehensive tests for core Registry service
- ✅ `test_workflow_execution_service.py` - 19 tests for workflow execution + status services  
- ✅ `test_registry_endpoints.py` - 15 API endpoint tests
- ✅ Enhanced `test_schema_manager.py` - schema management with storage integration

**Needs Attention:**
- 🔴 Unit test import and implementation fixes (immediate priority)
- 🟡 Integration test database cleanup issues (lower priority)

### Next Phase (Medium Priority)
- Fix remaining unit test errors and imports
- Add unit tests for missing components (audit service, remaining API endpoints)
- Enhance integration test stability
- Add more comprehensive error scenario testing

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