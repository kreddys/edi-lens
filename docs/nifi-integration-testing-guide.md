# NiFi Integration Testing Guide

## Overview

This document provides a comprehensive manual testing plan for the EDI Lens NiFi integration. Follow these steps to verify that your NiFi integration is working correctly and to identify any issues.

## Prerequisites

- Docker and Docker Compose installed
- Project environment properly configured
- Access to the project root directory

## Current Test Coverage

### ✅ **Comprehensive Test Suite Available**

Your project now includes a complete test suite for NiFi integration:

#### **Unit Tests** (`pytest.mark.unit`)
- **`test_nifi_comprehensive_unit.py`** - All NiFi components with mocked dependencies
- **`test_nifi_clients_unit.py`** - NiFi and Registry client unit tests  
- **`test_nifi_workflow_service_unit.py`** - Workflow service unit tests

#### **Integration Tests** (`pytest.mark.integration`)
- **`test_nifi_comprehensive_integration.py`** - Real NiFi services with database
- **`test_nifi_workflow_service_integration.py`** - Service integration tests
- **`test_nifi_template_management_integration.py`** - Template management tests
- **`test_builtin_templates_yaml_integration.py`** - YAML template processing

#### **E2E Tests** (`pytest.mark.e2e`)
- **`test_nifi_comprehensive_e2e.py`** - Complete API-to-NiFi workflows
- **`test_nifi_workflow_full_lifecycle_integration.py`** - Full lifecycle tests
- **`test_workflow_templates_e2e.py`** - Template E2E tests

#### **API Tests** (`pytest.mark.integration`)
- **`test_workflows_comprehensive.py`** - Complete workflow API testing
- **`test_workflow_execution_endpoints.py`** - Execution endpoint tests

## Testing Phases

### Phase 1: Environment Setup and Health Checks

#### 1.1 Start the Development Environment

```bash
# Navigate to project root
cd /path/to/edi-lens

# Start all services
./run.sh dev:start

# Wait for services to be healthy (this may take 2-3 minutes)
# Monitor startup progress
./run.sh dev:logs
```

#### 1.2 Verify Service Health

```bash
# Check NiFi service status
./run.sh dev:logs nifi | tail -20

# Check NiFi Registry status  
./run.sh dev:logs nifi-registry | tail -20

# Check backend service status
./run.sh dev:logs backend | tail -20
```

**Expected Results:**
- NiFi should show "NiFi has started" message
- NiFi Registry should show successful startup without errors
- Backend should show "Application startup complete"

#### 1.3 Verify Service Accessibility

```bash
# Test NiFi web interface through Caddy (should return HTML)
curl http://localhost:8080/nifi/

# Test NiFi Registry through Caddy (should return JSON)
curl http://localhost:8080/nifi-registry/

# Test Backend API (should return {"status": "healthy"})
curl http://localhost:8000/health
```

### Phase 2: Template Management Testing

#### 2.1 Seed Built-in Templates

```bash
# Seed the built-in templates
./run.sh dev:setup:templates

# Check logs for template seeding results
./run.sh dev:logs backend | grep -i template
```

**Expected Results:**
- Should see "Successfully seeded X templates" message
- No error messages during template loading

#### 2.2 Verify Templates via API

```bash
# List all templates (test_api.py automatically handles authentication from .env.dev)
python3 scripts/test_api.py -e /api/v1/workflow-templates

# Get specific EDI template
python3 scripts/test_api.py -e /api/v1/workflow-templates/edi-batch-processor-v2
```

**Expected Results:**
- Should return list of templates including "edi-batch-processor-v2"
- Template details should include configuration schema and flow definition

### Phase 3: Basic NiFi Connectivity Testing

#### 3.1 Run Connectivity Tests

```bash
# Option 1: Run all NiFi integration tests (recommended)
./run.sh dev:test integration backend/tests/nifi_tests/test_nifi_workflow_service_integration.py

# Option 2: Run specific test methods using pytest directly
cd backend && python -m pytest tests/nifi_tests/test_nifi_workflow_service_integration.py::TestNiFiWorkflowServiceIntegration::test_nifi_connectivity -v

# Option 3: Run tests with keyword filtering
./run.sh dev:test integration -k "nifi_connectivity"
```

**Expected Results:**
- Tests should pass without errors
- Should confirm NiFi and NiFi Registry are accessible
- If tests fail, check service health first

#### 3.2 Test Template Management Integration

```bash
# Run template management tests
./run.sh dev:test integration backend/tests/nifi_tests/test_nifi_template_management_integration.py

# Alternative: Run from backend directory
cd backend && python -m pytest tests/nifi_tests/test_nifi_template_management_integration.py -v

# Run specific template tests
./run.sh dev:test integration -k "template"
```

**Expected Results:**
- Template loading and validation should pass
- NiFi Registry integration should work
- Built-in templates should be accessible

### Phase 4: Workflow CRUD Operations Testing

#### 4.1 Create a Test Workflow

```bash
# Create a simple test workflow
python3 scripts/test_api.py -m POST -e /api/v1/workflows -d '{
  "name": "Manual Test Workflow - Basic",
  "template_id": "edi-batch-processor-v2",
  "configuration": {
    "input_directory": "/edi-lens/manual-test/input",
    "output_directory": "/edi-lens/manual-test/output",
    "filename_filter": ".*\\.(edi|x12|txt)$",
    "polling_interval": "30 sec",
    "keep_source_file": "false",
    "validation_schema": "837.5010.X222.A1.json",
    "snip_level": "3",
    "generate_cdm": "true",
    "generate_ta1": "false",
    "max_concurrent_tasks": "1"
  }
}'
```

**Expected Results:**
- Should return workflow details with a workflow_id
- Status should be "CREATED"
- No deployment-related fields should be populated yet

#### 4.2 List and Retrieve Workflows

```bash
# List all workflows
python3 scripts/test_api.py -e /api/v1/workflows

# Get specific workflow (replace {workflow-id} with actual ID from step 4.1)
python3 scripts/test_api.py -e /api/v1/workflows/{workflow-id}
```

#### 4.3 Update Workflow Configuration

```bash
# Update workflow configuration
python3 scripts/test_api.py -m PUT -e /api/v1/workflows/{workflow-id} -d '{
  "name": "Manual Test Workflow - Updated",
  "configuration": {
    "input_directory": "/edi-lens/manual-test-updated/input",
    "output_directory": "/edi-lens/manual-test-updated/output",
    "filename_filter": ".*\\.(edi|x12|txt)$",
    "polling_interval": "60 sec",
    "keep_source_file": "true",
    "validation_schema": "837.5010.X222.A1.json",
    "snip_level": "2",
    "generate_cdm": "true",
    "generate_ta1": "true",
    "max_concurrent_tasks": "2"
  }
}'
```

### Phase 5: Workflow Deployment Testing (Known Issue Area)

#### 5.1 Attempt Workflow Deployment

```bash
# Try to deploy the workflow (this is where the known issue occurs)
python3 scripts/test_api.py -m POST -e /api/v1/workflows/{workflow-id}/deploy
```

**Expected Results (Current Known Issue):**
- This will likely fail with a 500 error
- Backend logs should show "400 Bad Request" from NiFi
- This is the known processor configuration issue

#### 5.2 Check Deployment Logs

```bash
# Check backend logs for deployment errors
./run.sh dev:logs backend | grep -i -A 5 -B 5 "deploy\|400\|bad request"

# Check NiFi logs for processor errors
./run.sh dev:logs nifi | grep -i -A 5 -B 5 "400\|error\|processor"
```

#### 5.3 Test with Minimal Configuration

```bash
# Create a workflow with minimal configuration to isolate the issue
python3 scripts/test_api.py -m POST -e /api/v1/workflows -d '{
  "name": "Minimal Test Workflow",
  "template_id": "edi-batch-processor-v2",
  "configuration": {
    "input_directory": "/test/input",
    "output_directory": "/test/output"
  }
}'

# Try to deploy the minimal workflow
python3 scripts/test_api.py -m POST -e /api/v1/workflows/{new-workflow-id}/deploy
```

### Phase 6: Comprehensive Test Suite Execution

#### 6.1 Run Unit Tests (Fast, No External Dependencies)

```bash
# Run all NiFi unit tests
./run.sh dev:test unit backend/tests/nifi_tests/test_nifi_comprehensive_unit.py

# Run specific unit test categories
./run.sh dev:test unit backend/tests/nifi_tests/test_nifi_clients_unit.py
./run.sh dev:test unit backend/tests/nifi_tests/test_nifi_workflow_service_unit.py

# Run all unit tests with coverage
./run.sh dev:test unit backend/tests/nifi_tests/ -k "unit"
```

#### 6.2 Run Integration Tests (Requires Running Services)

```bash
# Run comprehensive integration tests
./run.sh dev:test integration backend/tests/nifi_tests/test_nifi_comprehensive_integration.py

# Run specific integration test suites
./run.sh dev:test integration backend/tests/nifi_tests/test_nifi_workflow_service_integration.py
./run.sh dev:test integration backend/tests/nifi_tests/test_nifi_template_management_integration.py

# Run all integration tests
./run.sh dev:test integration backend/tests/nifi_tests/ -k "integration"
```

#### 6.3 Run E2E Tests (Complete API-to-NiFi Workflows)

```bash
# Run comprehensive E2E tests
./run.sh dev:test e2e backend/tests/nifi_tests/test_nifi_comprehensive_e2e.py

# Run workflow lifecycle E2E tests
./run.sh dev:test e2e backend/tests/nifi_tests/test_nifi_workflow_full_lifecycle_integration.py

# Run all E2E tests
./run.sh dev:test e2e backend/tests/nifi_tests/ -k "e2e"
```

#### 6.4 Run API Tests (Workflow CRUD Operations)

```bash
# Run comprehensive workflow API tests
./run.sh dev:test integration backend/tests/api/test_workflows_comprehensive.py

# Run workflow execution endpoint tests
./run.sh dev:test integration backend/tests/api/test_workflow_execution_endpoints.py

# Run all API tests
./run.sh dev:test integration backend/tests/api/ -k "workflow"
```

#### 6.5 Run All NiFi Tests by Category

```bash
# Run all unit tests (fastest)
./run.sh dev:test unit -m "unit and nifi"

# Run all integration tests (requires services)
./run.sh dev:test integration -m "integration and nifi"

# Run all E2E tests (complete workflows)
./run.sh dev:test e2e -m "e2e and nifi"

# Run ALL NiFi tests (unit + integration + e2e)
./run.sh dev:test integration backend/tests/nifi_tests/
```

### Phase 7: Cleanup and Deletion Testing

#### 7.1 Test Workflow Deletion

```bash
# Delete the test workflows (this should work correctly)
python3 scripts/test_api.py -m DELETE -e /api/v1/workflows/{workflow-id}

# Verify deletion
python3 scripts/test_api.py -e /api/v1/workflows/{workflow-id}
```

**Expected Results:**
- Deletion should succeed
- Subsequent GET should return 404
- NiFi resources should be cleaned up

#### 7.2 Check NiFi Resource Cleanup

```bash
# Check NiFi logs for cleanup activities
./run.sh dev:logs nifi | grep -i -A 3 -B 3 "delete\|remove\|cleanup"

# Verify no orphaned resources in NiFi (manual check via web UI)
echo "Check NiFi web interface at http://localhost:8080/nifi/"
echo "Login with: superuser@edilens.com / password123456789"
echo "Verify no test process groups remain"
```

## Test Results Documentation

### Success Criteria

| Test Phase | Component | Expected Result | Status | Notes |
|------------|-----------|----------------|---------|-------|
| Phase 1 | Environment Setup | All services healthy | ⏳ | |
| Phase 2 | Template Management | Templates loaded successfully | ⏳ | |
| Phase 3 | NiFi Connectivity | Connection tests pass | ⏳ | |
| Phase 4 | Workflow CRUD | Create/Read/Update operations work | ⏳ | |
| Phase 5 | Workflow Deployment | **KNOWN ISSUE** - Expected to fail | ⏳ | 400 Bad Request |
| Phase 6 | Integration Tests | Most tests pass, deployment fails | ⏳ | |
| Phase 7 | Cleanup | Deletion works correctly | ⏳ | |

### Known Issues to Investigate

1. **Processor Configuration Updates (400 Bad Request)**
   - Location: Workflow deployment step
   - Symptoms: NiFi returns 400 when updating processor properties
   - Investigation: Check processor property names and values

2. **Custom EDI Processor Dependency**
   - Location: EDI processor type registration
   - Symptoms: May not be properly loaded in NiFi
   - Investigation: Verify custom processor availability

### Debugging Commands

```bash
# Check NiFi processor types available (through Caddy proxy)
curl -u "superuser@edilens.com:password123456789" \
  "http://localhost:8080/nifi-api/flow/processor-types" | jq '.processorTypes[] | select(.type | contains("EDI"))'

# Check parameter contexts in NiFi
curl -u "superuser@edilens.com:password123456789" \
  "http://localhost:8080/nifi-api/parameter-contexts"

# Check process groups
curl -u "superuser@edilens.com:password123456789" \
  "http://localhost:8080/nifi-api/flow/process-groups/root"
```

## Troubleshooting

### Common Issues

1. **"no tests ran" error**: 
   - Use full file paths: `backend/tests/nifi_tests/test_file.py`
   - Or run from backend directory: `cd backend && python -m pytest tests/nifi_tests/`
   - Check test file exists: `ls backend/tests/nifi_tests/`

2. **Services not starting**: Check Docker resources and port conflicts
3. **Authentication failures**: Verify Keycloak is running and configured
4. **Template loading failures**: Check YAML syntax and file permissions
5. **NiFi connection timeouts**: Increase startup wait time

### Test Command Troubleshooting

```bash
# If pytest commands fail, try these alternatives:

# List available test files
ls backend/tests/nifi_tests/

# Run tests with full path from project root
./run.sh dev:test integration backend/tests/nifi_tests/test_nifi_workflow_service_integration.py

# Run from backend directory
cd backend
python -m pytest tests/nifi_tests/test_nifi_workflow_service_integration.py -v

# Run all NiFi tests
cd backend
python -m pytest tests/nifi_tests/ -v

# Run with specific markers
cd backend  
python -m pytest -m integration tests/nifi_tests/ -v
```

### Log Locations

- **Backend logs**: `./run.sh dev:logs backend`
- **NiFi logs**: `./run.sh dev:logs nifi`
- **NiFi Registry logs**: `./run.sh dev:logs nifi-registry`
- **Database logs**: `./run.sh dev:logs db`

## Next Steps

After completing this testing:

1. **Document all results** in the Status column above
2. **Identify specific failure points** for the deployment issue
3. **Investigate processor property compatibility** with NiFi
4. **Consider alternative deployment strategies** if needed
5. **Update integration based on findings**

## Additional Resources

- **NiFi Web UI**: http://localhost:8080/nifi/ (superuser@edilens.com / password123456789)
- **NiFi Registry UI**: http://localhost:8080/nifi-registry/
- **Backend API Docs**: http://localhost:8000/docs
- **Project Documentation**: `docs/nifi-integration-guide.md`

---

*Last Updated: $(date)*
*Testing Version: Manual Testing Guide v1.0*