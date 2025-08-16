# NiFi Workflow System - Debugging Cheat Sheet

**Date**: August 16, 2025
**Author**: Qwen Code Assistant

## Common Issues and Quick Fixes

### 1. Test Environment Issues

**Symptom**: `ModuleNotFoundError: No module named 'asgi_lifespan'`
**Quick Fix**: 
```bash
# In the backend container
pip install asgi-lifespan
```

**Prevention**: Ensure dev dependencies are properly installed in test environment

### 2. URL Path Mismatches

**Symptom**: `404 Not Found` errors when calling API endpoints
**Quick Fix**: 
- Check that tests use `/api/v1/` prefix (not `/api/`)
- Verify URL construction matches actual API routes

**Example**:
```python
# ❌ Wrong
response = await async_client.post(f"/api/workflows/{workflow_id}/process")

# ✅ Correct
response = await async_client.post(f"/api/v1/workflows/{workflow_id}/process")
```

### 3. UUID Serialization Errors

**Symptom**: Pydantic validation errors for UUID fields
**Quick Fix**: Convert UUID objects to strings when creating response objects

**Example**:
```python
# ❌ Wrong
return WorkflowExecutionResponse(
    workflow_id=workflow.workflow_id,  # UUID object
    # ... other fields
)

# ✅ Correct
return WorkflowExecutionResponse(
    workflow_id=str(workflow.workflow_id),  # String conversion
    # ... other fields
)
```

### 4. Audit Logging Primary Key Issues

**Symptom**: `AttributeError: 'Model' object has no attribute 'id'` or `AttributeError: __table__`
**Quick Fix**: Make audit logging system flexible to handle different primary key names and mock objects

**Solution**:
```python
def _get_primary_key_value(obj) -> str:
    """Get the primary key value of an object, regardless of the column name."""
    # Handle mock objects in tests
    if hasattr(obj, 'id'):
        return str(obj.id)
    
    # Handle real SQLAlchemy models
    if hasattr(obj, '__table__') and hasattr(obj.__table__, 'columns'):
        primary_key_value = None
        for column in obj.__table__.columns:
            if column.primary_key:
                primary_key_value = getattr(obj, column.name)
                break
        return str(primary_key_value) if primary_key_value else None
    
    # Fallback for other object types
    return None
```

### 5. Object Type Confusion

**Symptom**: `TypeError` or `AttributeError` when accessing object properties
**Quick Fix**: Ensure endpoints work with actual model objects, not response objects

**Example**:
```python
# ❌ Wrong - Trying to modify response object
workflow = await get_workflow(workflow_id, session, auth_context)
workflow.status = "PAUSED"
session.add(workflow)  # Error: workflow is a response object

# ✅ Correct - Work with model object directly
query = select(Workflow).where(Workflow.workflow_id == workflow_id)
result = await session.execute(query)
workflow = result.scalar_one_or_none()
workflow.status = "PAUSED"
session.add(workflow)
```

## Testing Commands

### Run All Workflow Execution Tests
```bash
./run.sh dev:test integration tests/api/test_workflow_execution_endpoints.py -v
```

### Run Single Test with Verbose Output
```bash
./run.sh dev:test integration tests/api/test_workflow_execution_endpoints.py::test_pause_workflow -v -s
```

### Run Tests with Debug Logging
```bash
./run.sh dev:test integration tests/api/test_workflow_execution_endpoints.py -v --log-cli-level=DEBUG
```

### Rebuild Backend Service
```bash
./run.sh dev:build backend
```

## Common File Locations

### Workflow Models
- `backend/src/models/workflow_template.py` - Contains `WorkflowTemplate`, `TemplateVersion`, `TemplateUsage`, and `Workflow` models

### Workflow Endpoints
- `backend/src/api/endpoints/workflows.py` - Contains all workflow-related API endpoints

### Workflow Services
- `backend/src/services/workflow_execution_service.py` - Contains `WorkflowExecutionService` and `WorkflowStatusService`

### Test Files
- `backend/tests/api/test_workflow_execution_endpoints.py` - Integration tests for workflow execution
- `backend/tests/conftest.py` - Test configuration and fixtures

### Audit Logging
- `backend/src/core/audit.py` - Audit logging system implementation

## Debugging Checklist

### 1. Environment Verification
- [ ] Check that all dependencies are installed
- [ ] Verify container health status
- [ ] Confirm database connectivity

### 2. API Contract Compliance
- [ ] Verify URL paths match API routes
- [ ] Check HTTP methods and status codes
- [ ] Confirm request/response data structures

### 3. Data Type Consistency
- [ ] Ensure UUIDs are properly converted to strings
- [ ] Verify enum values match expected types
- [ ] Check that datetime objects are properly serialized

### 4. Database Operations
- [ ] Confirm session management (commit/flush)
- [ ] Verify primary key handling for all models
- [ ] Check foreign key relationships

### 5. Authentication and Authorization
- [ ] Ensure proper permission requirements
- [ ] Verify tenant isolation
- [ ] Confirm user context propagation

### 6. Error Handling
- [ ] Check for proper HTTP status codes
- [ ] Verify error message consistency
- [ ] Confirm exception handling patterns

## Useful Debugging Techniques

### 1. Add Temporary Debug Logging
```python
import logging
log = logging.getLogger(__name__)

# Add debug statements
log.debug(f"[DEBUG] Variable value: {variable}")
```

### 2. Inspect Object Properties
```python
# Print object attributes
print(f"Object type: {type(obj)}")
print(f"Object attributes: {dir(obj)}")
print(f"Object dict: {obj.__dict__}")
```

### 3. Check Database State
```python
# In test or endpoint
result = await session.execute(select(Workflow))
workflows = result.scalars().all()
for workflow in workflows:
    print(f"Workflow ID: {workflow.workflow_id}, Status: {workflow.status}")
```

### 4. Verify Session Sharing
```python
# Add to both test and endpoint
print(f"Session ID (test): {id(session)}")
print(f"Session ID (endpoint): {id(session)}")
```

## Common Pitfalls to Avoid

### 1. Hardcoded Assumptions
- ❌ Assuming all models use `id` as primary key
- ❌ Expecting specific column names or data types
- ❌ Relying on fixed URL structures

### 2. Mixed Object Types
- ❌ Mixing response objects with model objects
- ❌ Confusing DTOs with domain entities
- ❌ Passing UI data directly to services

### 3. Inconsistent Data Handling
- ❌ Returning raw database objects in API responses
- ❌ Not converting UUIDs to strings
- ❌ Inconsistent datetime serialization

### 4. Poor Session Management
- ❌ Forgetting to commit database transactions
- ❌ Mixing flush/commit operations inconsistently
- ❌ Not handling session cleanup properly

## Emergency Recovery Procedures

### 1. Reset Test Environment
```bash
# Stop and remove containers
./run.sh dev:clean

# Rebuild and restart
./run.sh dev:start
```

### 2. Force Reinstall Dependencies
```bash
# Enter backend container
docker exec -it backend bash

# Reinstall dependencies
pip install --force-reinstall -e .
```

### 3. Clear Test Cache
```bash
# In project root
rm -rf .pytest_cache
rm -rf backend/.pytest_cache
```

### 4. Reset Database
```bash
# Using run.sh commands
./run.sh dev:db:reset
./run.sh dev:migrate:run
```

This cheat sheet provides a quick reference for common issues and their solutions when working with the NiFi workflow system. Regular updates to this document based on new issues encountered will help improve debugging efficiency over time.