# E2E Workflow Lifecycle Testing

## Overview

The E2E workflow lifecycle tests provide comprehensive validation of the complete EDI Lens workflow system, from template creation through NiFi deployment, real file processing, and proper cleanup. This documentation describes the current implementation, test phases, API calls, assertions, and infrastructure setup.

**Test Location**: `backend/tests/e2e/workflows/test_simple_file_processing.py`

## Infrastructure Setup

### Required Services
- **NiFi**: Apache NiFi instance with Registry integration
- **NiFi Registry**: Template version control and storage
- **Backend**: EDI Lens API server
- **PostgreSQL**: Database for workflow metadata
- **Keycloak**: Authentication and authorization
- **MinIO**: Object storage for configurations

### Volume Permissions
- **e2e-test-volume-init**: Docker init service that sets proper permissions (1000:1000, 0777) on `/e2e_test_files` to prevent NiFi permission errors
- **Shared volume**: `e2e_test_data:/e2e_test_files` mounted in both backend and NiFi containers

## Test Phases and API Calls

### Phase 1: Authentication & Template Creation
**APIs Called:**
- `POST /realms/edi-lens/protocol/openid-connect/token` (Keycloak)
- `POST /api/v1/templates/` (Backend)

**Actions:**
- Authenticates as superuser with Keycloak
- Creates a registry template with 3-processor workflow:
  - GetFile (reads from `#{input_directory}`)
  - UpdateAttribute (adds `filename: processed_${filename}`)
  - PutFile (writes to `#{output_directory}`)

**Assertions:**
- Template creation returns 201 Created
- Template ID is returned and valid

### Phase 2: Workflow Instance Creation
**APIs Called:**
- `POST /api/v1/workflows/` (Backend)

**Actions:**
- Creates workflow instance from template
- Sets configuration parameters:
  - `input_directory`: `/e2e_test_files/edi_lens_e2e_{test_run_id}/input`
  - `output_directory`: `/e2e_test_files/edi_lens_e2e_{test_run_id}/output`
  - `error_directory`: `/e2e_test_files/edi_lens_e2e_{test_run_id}/error`

**Assertions:**
- Workflow creation returns 201 Created
- Workflow ID is returned
- Configuration parameters are properly stored

### Phase 3: Test Setup Validation
**Actions:**
- Creates test directories on shared volume
- Sets proper permissions (0777 for directories, 0666 for files)
- Validates directory structure

**Assertions:**
- All test directories exist and are accessible
- Permissions are set correctly

### Phase 4: Database State Verification
**APIs Called:**
- `GET /api/v1/templates/{template_id}` (Backend)
- `GET /api/v1/workflows/{workflow_id}` (Backend)

**Actions:**
- Verifies template exists in database
- Verifies workflow exists with correct template reference
- Validates tenant isolation

**Assertions:**
- Template and workflow are properly persisted
- Relationships are correctly established
- Multi-tenant security is enforced

### Phase 5: NiFi Deployment
**APIs Called:**
- `POST /api/v1/workflows/{workflow_id}/deploy` (Backend)
- `GET /api/v1/workflows/{workflow_id}/status` (Backend)

**Backend Internal Actions:**
- Creates NiFi parameter context with workflow parameters
- Associates parameter context with process group
- Creates processors with proper configuration (component.config.properties)
- Creates connections between processors
- Re-validates processors after wiring

**Assertions:**
- Deployment returns 200 OK
- Process group ID is assigned
- Workflow status becomes ACTIVE
- `is_deployed` flag is true

### Phase 5.5: Processor Restart & Validation
**APIs Called:**
- `POST /api/v1/workflows/{workflow_id}/restart-processors` (Backend)

**Actions:**
- Restarts all processors to force parameter re-evaluation
- Waits for validation status to refresh

**Assertions:**
- Processor restart returns 200 OK
- All 3 processors are restarted successfully

### Phase 6: Workflow Startup
**APIs Called:**
- `POST /api/v1/workflows/{workflow_id}/start` (Backend)

**Actions:**
- Starts all processors in the workflow
- Sets workflow status to RUNNING

**Assertions:**
- Start operation returns 200 OK
- Workflow status becomes ACTIVE/RUNNING

### Phase 7: Workflow Execution
**APIs Called:**
- `POST /api/v1/workflows/{workflow_id}/execute` (Backend)

**Actions:**
- Creates test input file: `/e2e_test_files/.../input/test_input.txt`
- File content: "This is test content for EDI Lens E2E testing.\nLine 2 of test data.\nFinal line."
- Triggers workflow execution with execution_id: `e2e-test-{test_run_id}`

**Assertions:**
- Execution returns 200 OK
- Execution ID is returned
- Health check shows healthy status
- Processing time is reported

### Phase 8: File Processing Validation (Primary)
**Validation Method**: Directory-based (black-box)

**Actions:**
- Polls output directory for processed files (max 10 seconds)
- Validates file naming pattern: `processed_*.txt`
- Verifies file content integrity
- Confirms input file consumption

**Assertions:**
- Output file appears within 10 seconds
- Output filename starts with "processed_"
- Output file size matches input (111 bytes)
- File content is preserved exactly
- Input file is consumed (deleted by GetFile with Keep Source File=false)

### Phase 8.5: Provenance Verification (Secondary)
**APIs Called:**
- `GET /api/v1/workflows/{workflow_id}/provenance?filename={processed_filename}&max_results=50&wait_seconds=15` (Backend)

**Backend Internal Actions:**
- Submits NiFi provenance query with multiple format fallbacks:
  1. Simple DTO format
  2. DTO with date constraints  
  3. ProvenanceEntity wrapper format
- Polls query results with 404/409 conflict handling
- Correlates events with workflow's process group processors

**Assertions (Best Effort)**:
- If successful: Provenance events found for the processed file
- If 409 Conflict: Logs warning about NiFi being busy (acceptable)
- If 500/404: Logs warning about provenance configuration (acceptable)
- **Primary validation (directory-based) takes precedence**

### Phase 9: NiFi Integration Validation (Optional)
**Actions:**
- Direct NiFi API calls to verify deployment state
- Validates processor configurations
- Checks parameter context association

**Assertions:**
- Process group exists in NiFi
- Parameter context is properly associated
- Processors are in expected state

### Phase 10: Performance & Health Metrics
**Validation:**
- Workflow execution time (typically 250-300ms)
- File processing latency (typically 2 seconds)
- Resource utilization monitoring
- Health check responses

### Phase 11: Stop & Cleanup Verification
**APIs Called:**
- `POST /api/v1/workflows/{workflow_id}/stop` (Backend)
- `GET /api/v1/workflows/{workflow_id}/status` (Backend)
- `DELETE /api/v1/workflows/{workflow_id}/deployment` (Backend)
- `GET /api/v1/workflows/{workflow_id}/status` (Backend) (Final verification)

**Actions:**
1. **Stop Processors**: Stops all workflow processors
2. **Verify Stop**: Confirms processors are stopped and workflow status is STOPPED
3. **Undeploy**: Removes workflow from NiFi (deletes process group and parameter context)
4. **Verify Undeploy**: Confirms `is_deployed` is false and NiFi resources are cleaned
5. **Wait**: 5-second delay for complete NiFi cleanup
6. **Directory Cleanup**: Removes test directories from shared volume

**Assertions:**
- Stop returns 200 OK with processor count details
- Workflow status becomes STOPPED
- Undeploy returns 200 OK
- `is_deployed` becomes false
- Process group ID is cleared or preserved for audit
- No lingering NiFi resources
- Directory cleanup succeeds

## Error Handling & Resilience

### NiFi API Resilience
- **Provenance conflicts**: Handles 409 "too many queries" gracefully
- **Processor validation**: Expects INVALID state before wiring, re-validates after connections
- **Parameter context timing**: Waits for association before creating processors
- **Cleanup sequencing**: Proper stop → undeploy → wait → cleanup ordering

### Permission Management
- **Volume init service**: Ensures deterministic permissions before NiFi starts
- **Race condition prevention**: e2e-test-volume-init runs before services start
- **Multi-container access**: Both backend and NiFi can read/write shared volumes

### Backend Error Recovery
- **Template validation**: Graceful handling of missing or invalid templates
- **Workflow lifecycle**: Comprehensive state management and error reporting
- **Multi-tenant security**: Strict tenant isolation throughout test

## Key Technical Details

### Processor Configuration
```json
{
  "component": {
    "config": {
      "properties": {
        "Input Directory": "#{input_directory}",
        "Directory": "#{output_directory}",
        "filename": "processed_${filename}"
      },
      "schedulingPeriod": "0 sec",
      "schedulingStrategy": "TIMER_DRIVEN",
      "concurrentlySchedulableTaskCount": 1
    }
  }
}
```

### Parameter Context
```json
{
  "input_directory": "/e2e_test_files/edi_lens_e2e_{test_run_id}/input",
  "output_directory": "/e2e_test_files/edi_lens_e2e_{test_run_id}/output",
  "error_directory": "/e2e_test_files/edi_lens_e2e_{test_run_id}/error"
}
```

### Validation Hierarchy
1. **Primary (Required)**: Directory-based file processing validation
2. **Secondary (Best Effort)**: NiFi provenance verification
3. **Tertiary (Optional)**: Direct NiFi API state validation
4. **Health Metrics**: Performance and resource monitoring

## Infrastructure Requirements

### Docker Services
- **NiFi**: Latest with Registry client configured
- **NiFi Registry**: PostgreSQL-backed with proper permissions
- **Backend**: EDI Lens API with NiFi client authentication
- **Database**: PostgreSQL with test database setup
- **Keycloak**: Configured realm with test users
- **MinIO**: Object storage for configurations

### Network Configuration
- All services on `edi_lens_network`
- Backend can reach NiFi at `https://nifi:8443`
- NiFi can reach Registry at `http://nifi-registry:18080`

### Authentication
- **NiFi**: Username/password authentication
- **Backend**: JWT tokens from Keycloak
- **Multi-tenant**: Tenant isolation via JWT claims

## Troubleshooting Guide

### Common Issues

**File Permission Errors:**
- Symptoms: "Directory does not have sufficient permissions"
- Solution: Ensure e2e-test-volume-init service runs and sets 1000:1000 ownership

**Provenance Conflicts:**
- Symptoms: 409 "too many queries" 
- Solution: NiFi auto-cleans old queries; test handles this gracefully

**Processor Validation:**
- Symptoms: Processors remain INVALID after deployment
- Solution: Check parameter context association and property mapping

**Deployment Timeouts:**
- Symptoms: Workflow deploy takes too long
- Solution: Check NiFi health and Registry connectivity

**Cleanup Issues:**
- Symptoms: Resources not cleaned up between tests
- Solution: Verify stop/undeploy sequence and wait times

### Debug Information

**Enable Debug Logging:**
```python
# In test setup
logging.getLogger().setLevel(logging.DEBUG)
```

**Check Service Health:**
```bash
# Via run.sh
bash ./run.sh dev:test e2e --verbose

# Manual health checks
curl http://backend:8000/api/v1/health
curl https://nifi:8443/nifi-api/system-diagnostics
```

**Inspect NiFi State:**
```bash
# View process groups
curl -k https://nifi:8443/nifi-api/flow/process-groups/root

# View parameter contexts  
curl -k https://nifi:8443/nifi-api/parameter-contexts
```

## Success Metrics

### Test Performance
- **Total test time**: ~18-20 seconds
- **File processing latency**: 2-3 seconds
- **Workflow deployment**: 2-3 seconds
- **Cleanup time**: 5-7 seconds

### Coverage Validation
- ✅ Complete workflow lifecycle (create → deploy → execute → cleanup)
- ✅ Real file processing with NiFi
- ✅ Parameter context and template integration
- ✅ Multi-tenant security enforcement
- ✅ Error handling and resilience
- ✅ Resource cleanup and leak prevention
- ✅ Performance and health monitoring

The E2E tests provide comprehensive validation that the EDI Lens system works correctly in a production-like environment with real NiFi integration, file processing, and proper resource management.