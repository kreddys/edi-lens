# Debugging and Troubleshooting Guide

## Overview

This document captures the debugging steps, common issues, and solutions encountered during Phase 1.1 implementation. These learnings will be invaluable for implementing future phases.

## Major Issues Encountered and Solutions

### 1. **Test Authentication Setup Issues**

#### Problem
Tests were failing with authentication errors despite proper FastAPI dependency override setup.

#### Root Cause
Tests were using `patch()` to mock authentication, which doesn't work with FastAPI's dependency injection system. The dependency overrides take precedence over `patch()`.

#### Solution
```python
# ❌ Wrong approach - using patch
with patch('src.api.endpoints.edi_validation.require_service_auth', return_value=mock_auth):
    response = await client.post(...)

# ✅ Correct approach - using dependency override
app.dependency_overrides[require_service_auth] = lambda: mock_service_context
```

#### Key Learning
- **FastAPI dependency injection overrides are more powerful than unittest.patch**
- **Always use `app.dependency_overrides` for mocking FastAPI dependencies in tests**
- **Create module-level fixtures for shared authentication contexts**

### 2. **ValidationFinding Schema Format Issues**

#### Problem
Tests were failing with Pydantic validation errors for `ValidationFinding` objects.

```
ValidationError: 4 validation errors for ValidationFinding
location.segment_id: Field required
location.segment_instance: Field required  
location.element_position: Field required
location.line_number: Field required
```

#### Root Cause
Tests were using old dictionary format for location instead of the new `FindingLocation` schema.

#### Solution
```python
# ❌ Old format
ValidationFinding(
    level="error",
    code="MISSING_REQUIRED",
    message="Segment missing",
    location={"segment": "ST", "element": 2}  # Dictionary format
)

# ✅ New format  
ValidationFinding(
    level="error", 
    code="MISSING_REQUIRED",
    message="Segment missing",
    location=FindingLocation(
        segment_id="ST",
        segment_instance=1,
        element_position=2,
        line_number=1
    )
)
```

#### Key Learning
- **Always check schema definitions when tests fail with validation errors**
- **Use proper Pydantic models instead of dictionaries for nested schemas**
- **Import and use `FindingLocation` for ValidationFinding location data**

### 3. **EDI Validation Service Integration**

#### Problem
The `EDIValidationService` had basic validation logic that only checked ISA segments instead of using the robust `EdiParser`.

#### Root Cause
The service was implemented with placeholder validation code rather than integrating with existing infrastructure.

#### Solution
```python
# ❌ Basic validation approach
def _parse_edi_content(self, edi_content: str):
    # Simplified parsing logic
    segments = edi_content.split('\n')
    # Basic ISA validation only
    
# ✅ Robust integration
def validate_edi(self, edi_content: str, schema_name: str, tenant_id: str):
    # Use existing robust EdiParser
    parser = EdiParser(edi_content, schema)
    interchange = parser.parse()
    
    # Convert parser errors to ValidationFindings
    findings = []
    for error in parser.errors:
        finding = ValidationFinding(...)
        findings.append(finding)
```

#### Key Learning
- **Always integrate with existing robust infrastructure instead of reimplementing**
- **Check what components already exist before writing new validation logic**
- **Use the established patterns and data structures**

### 4. **CdmSegment Constructor Requirements**

#### Problem
TA1 generation failed with missing required fields in `CdmSegment` construction.

#### Root Cause
`CdmSegment` requires specific fields (`line_number`, `raw_segment`, etc.) that weren't being provided.

#### Solution
```python
# ❌ Incomplete CdmSegment creation
isa_segment = CdmSegment(segment_id="ISA", elements=elements)

# ✅ Complete CdmSegment creation
cdm_elements = []
for i, element_value in enumerate(elements[1:], 1):
    cdm_elements.append(CdmElement(
        element_id=f"ISA{i:02d}",
        value=element_value,
        position=i
    ))

isa_segment = CdmSegment(
    segment_id="ISA",
    elements=cdm_elements,
    line_number=1,
    raw_segment=raw_segment
)
```

#### Key Learning
- **Always check constructor requirements for complex objects**
- **Use proper CDM element structure with position and ID information**
- **Preserve raw data for debugging and logging purposes**

### 5. **Missing Test Fixtures**

#### Problem
Tests were failing with "fixture not found" errors for `mock_auth_context` and `mock_batch_service`.

#### Root Cause
Fixtures were defined within specific test classes but used by other test classes.

#### Solution
```python
# ❌ Class-level fixture (only available within class)
class TestRealtimeEDIValidation:
    @pytest.fixture
    def mock_auth_context(self):
        return ServiceContext(...)

# ✅ Module-level fixture (available to all test classes)
@pytest.fixture
def mock_auth_context():
    return ServiceContext(
        service_name="nifi-service",
        allowed_tenants=[]
    )
```

#### Key Learning
- **Define shared fixtures at module level, not class level**
- **Remove unused fixture parameters from test function signatures**
- **Use consistent fixture naming across test files**

## Debugging Methodology

### 1. **Test-Driven Debugging**

**Approach**: Run tests early and often to identify issues quickly.

```bash
# Run specific failing test with verbose output
./run.sh dev:test integration tests/api/test_edi_validation.py::TestName::test_method -v

# Run with debug logging
./run.sh dev:test integration tests/api/test_edi_validation.py::TestName::test_method -v -s --log-cli-level=DEBUG
```

**Benefits**:
- Immediate feedback on changes
- Isolated problem identification
- Clear error messages and stack traces

### 2. **Progressive Integration Testing**

**Approach**: Test individual components before full integration.

```bash
# Test single test class first
./run.sh dev:test integration tests/api/test_edi_validation.py::TestRealtimeEDIValidation -v

# Then test full suite
./run.sh dev:test integration tests/api/test_edi_validation.py -v
```

**Benefits**:
- Identify component-specific vs integration issues
- Faster feedback cycles
- Easier isolation of problems

### 3. **Debug Logging Strategy**

**Implementation**: Add comprehensive logging at key points.

```python
# Add debug logging in endpoints
logger.debug(f"Checking tenant access for tenant_id: {request.tenant_id}")
logger.debug(f"Tenant access check result: {has_access}")

# Add error logging with stack traces
logger.error(f"EDI validation failed: {str(e)}", exc_info=True)
```

**Benefits**:
- Permanent debugging infrastructure
- Production troubleshooting capability
- Clear audit trail of operations

## Common Patterns and Solutions

### 1. **FastAPI Dependency Testing Pattern**

```python
# Consistent pattern for testing with auth overrides
def test_with_custom_auth(self, async_client):
    from src.main import app
    from src.core.auth import require_service_auth
    
    # Custom auth context for this test
    mock_context = ServiceContext(
        service_name="test-service",
        allowed_tenants=["tenant-a"]  # Specific to test
    )
    
    # Temporarily override dependency
    original_override = app.dependency_overrides.get(require_service_auth)
    app.dependency_overrides[require_service_auth] = lambda: mock_context
    
    try:
        # Test execution
        response = await async_client.post(...)
        assert response.status_code == expected_status
    finally:
        # Restore original override
        if original_override:
            app.dependency_overrides[require_service_auth] = original_override
```

### 2. **Error Handling Pattern**

```python
# Consistent error handling in endpoints
try:
    # Business logic
    result = await service.process(request)
    return SuccessResponse(data=result)
    
except HTTPException:
    # Re-raise HTTP exceptions (like 403 Forbidden) as-is
    raise
except Exception as e:
    # Log error for monitoring
    logger.error(f"Operation failed: {str(e)}", exc_info=True)
    
    # Return user-friendly error
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Operation failed: {str(e)}"
    )
```

### 3. **Service Integration Pattern**

```python
# Consistent service integration approach
class SomeService:
    def __init__(self):
        # Use existing infrastructure components
        self.schema_manager = SchemaManager()
        self.edi_parser = EdiParser
        self.ta1_generator = TA1Generator()
    
    async def process(self, data: str, schema_name: str, tenant_id: str):
        # Load schema using existing manager
        schema = self.schema_manager.get_schema(schema_name, tenant_id)
        
        # Use robust parser
        parser = self.edi_parser(data, schema)
        result = parser.parse()
        
        # Convert results to API format
        return self._convert_to_api_format(result)
```

## Testing Best Practices

### 1. **Fixture Organization**
- Module-level fixtures for shared components
- Class-level fixtures for test-specific setup
- Use descriptive fixture names
- Document fixture purpose and usage

### 2. **Test Data Management**
- Use realistic EDI test data
- Include both valid and invalid scenarios
- Test edge cases and boundary conditions
- Maintain separate test data files

### 3. **Assertion Strategies**
- Test both success and failure scenarios
- Validate response structure and data
- Check HTTP status codes
- Verify error messages and codes

## Performance Considerations

### 1. **Test Execution Speed**
- Use async test patterns consistently
- Mock external dependencies
- Avoid unnecessary database operations
- Parallel test execution where possible

### 2. **Memory Management**
- Clean up resources in test teardown
- Avoid memory leaks in background tasks
- Monitor test resource usage

## Future Phase Considerations

### 1. **Scalability Patterns**
- Established service integration patterns
- Robust error handling framework
- Comprehensive test coverage methodology
- Debug logging infrastructure

### 2. **Maintenance Strategy**
- Keep tests focused and isolated
- Maintain clear documentation
- Regular dependency updates
- Continuous integration practices

### 3. **Extension Points**
- Authentication system ready for new services
- Schema management supports new EDI types
- Test framework supports new scenarios
- Logging system ready for production monitoring

## Conclusion

The debugging and troubleshooting process for Phase 1.1 has established solid patterns and practices that will accelerate development of future phases. The key learnings around FastAPI dependency injection, service integration, and test organization provide a strong foundation for Phase 1.2 and beyond.