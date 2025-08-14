# Testing Framework and Best Practices

## Overview

This document captures the testing framework, patterns, and best practices established during Phase 1.1. These practices ensure high-quality, maintainable tests that provide confidence in the system's reliability.

## Testing Architecture

### 1. **Test Organization Structure**

```
backend/tests/
├── conftest.py                     # Global fixtures and configuration
├── api/
│   ├── conftest.py                 # API-specific fixtures  
│   ├── test_edi_validation.py      # Main API test suite
│   ├── test_ta1_generation.py      # Phase 1.2 tests (future)
│   └── test_999_generation.py      # Phase 1.3 tests (future)
├── services/
│   ├── test_edi_validation_service.py
│   ├── test_ta1_generation_service.py
│   └── test_batch_job_service.py
├── core/
│   ├── test_edi_parser.py
│   ├── test_ta1_generator.py
│   └── test_schema_manager.py
└── data/
    └── test_files/                 # Realistic EDI test data
        ├── valid_837p.edi
        ├── complex_837p.edi
        └── invalid_edi.edi
```

### 2. **Test Categories**

#### **Unit Tests** (`tests/services/`, `tests/core/`)
- Test individual components in isolation
- Mock external dependencies
- Fast execution (< 1ms per test)
- High coverage of edge cases

#### **Integration Tests** (`tests/api/`)
- Test API endpoints with real dependencies
- Use test database and authentication
- Medium execution time (< 100ms per test)
- Test complete request/response cycles

#### **End-to-End Tests** (Future)
- Test complete workflows from NiFi perspective
- Use real EDI data and scenarios
- Longer execution time (< 5s per test)
- Validate business workflows

## Fixture Patterns

### 1. **Module-Level Fixtures**

```python
# backend/tests/api/test_edi_validation.py

@pytest.fixture
def mock_auth_context():
    """Module-level auth context available to all test classes."""
    from src.core.auth import ServiceContext
    return ServiceContext(
        service_name="nifi-service",
        allowed_tenants=[]  # Empty means all tenants allowed
    )

@pytest.fixture  
def valid_edi_request(valid_837p_edi_string):
    """Standard EDI validation request."""
    return RealtimeEDIValidationRequest(
        edi_content=valid_837p_edi_string,
        tenant_id="tenant-a",
        workflow_id="test-workflow-001",
        validation_schema="837.5010.X222.A1.json"
    )
```

### 2. **Class-Level Fixtures**

```python
class TestRealtimeEDIValidation:
    @pytest.fixture
    def mock_validation_service(self):
        """Mock service specific to this test class."""
        return AsyncMock()
    
    @pytest.fixture
    def complex_request(self, complex_837p_edi_string):
        """Test-class-specific request fixture."""
        return RealtimeEDIValidationRequest(
            edi_content=complex_837p_edi_string,
            tenant_id="tenant-a",
            workflow_id="complex-test-001",
            validation_schema="837.5010.X222.A1.json",
            snip_level=5
        )
```

### 3. **Dynamic Fixtures**

```python
@pytest.fixture(params=["A", "R", "E"])
def acknowledgment_code(request):
    """Parameterized fixture for testing different ack codes."""
    return request.param

@pytest.fixture
def ta1_request(valid_837p_edi_string, acknowledgment_code):
    """Dynamic fixture based on acknowledgment code."""
    base_request = {
        "edi_content": valid_837p_edi_string,
        "tenant_id": "tenant-a",
        "workflow_id": f"ta1-{acknowledgment_code.lower()}-001",
        "acknowledgment_code": acknowledgment_code
    }
    
    if acknowledgment_code == "E":
        base_request["error_code"] = "IK901"
        base_request["error_note"] = "Test error"
    
    return TA1GenerationRequest(**base_request)
```

## Authentication Testing Patterns

### 1. **Standard Authentication Tests**

```python
@pytest.mark.asyncio
async def test_authentication_required(self):
    """Test that endpoints require authentication."""
    from fastapi.testclient import TestClient
    from src.main import app
    
    # Use client without dependency overrides
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/edi/validate-realtime",
            json={"some": "data"}
            # No Authorization header
        )
        
        assert response.status_code in [401, 422]
```

### 2. **Tenant Isolation Testing**

```python
@pytest.mark.asyncio  
async def test_tenant_isolation(self, async_client, valid_request):
    """Test tenant access control."""
    from src.main import app
    from src.core.auth import require_service_auth, ServiceContext
    
    # Create auth context that denies tenant access
    mock_context = ServiceContext(
        service_name="test-service",
        allowed_tenants=["tenant-b", "tenant-c"]  # Does NOT include tenant-a
    )
    
    # Temporarily override auth
    original_override = app.dependency_overrides.get(require_service_auth)
    app.dependency_overrides[require_service_auth] = lambda: mock_context
    
    try:
        response = await async_client.post(
            "/api/v1/edi/validate-realtime",
            json=valid_request.model_dump(),
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 403
        assert "Access denied" in response.json()["detail"]
    finally:
        # Always restore original override
        if original_override:
            app.dependency_overrides[require_service_auth] = original_override
```

### 3. **Custom Authentication Scenarios**

```python
@pytest.mark.asyncio
async def test_service_with_limited_tenants(self, async_client, valid_request):
    """Test service with specific tenant restrictions."""
    # Modify request to use allowed tenant
    valid_request.tenant_id = "tenant-b"
    
    # Override auth to allow only tenant-b
    mock_context = ServiceContext(
        service_name="restricted-service",
        allowed_tenants=["tenant-b"]
    )
    
    app.dependency_overrides[require_service_auth] = lambda: mock_context
    
    try:
        response = await async_client.post(
            "/api/v1/edi/validate-realtime",
            json=valid_request.model_dump(),
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
    finally:
        # Cleanup handled by conftest.py
        pass
```

## Data Structure Testing

### 1. **Schema Validation Testing**

```python
def test_validation_finding_structure():
    """Test ValidationFinding schema compliance."""
    finding = ValidationFinding(
        level="error",
        code="TEST_ERROR",
        message="Test error message",
        location=FindingLocation(
            segment_id="ST",
            segment_instance=1,
            element_position=2,
            line_number=5
        )
    )
    
    # Validate serialization/deserialization
    json_data = finding.model_dump()
    reconstructed = ValidationFinding(**json_data)
    
    assert reconstructed.level == "error"
    assert reconstructed.location.segment_id == "ST"
    assert reconstructed.location.line_number == 5
```

### 2. **Request/Response Validation**

```python
@pytest.mark.asyncio
async def test_request_response_structure(self, async_client, valid_request):
    """Test complete request/response structure."""
    response = await async_client.post(
        "/api/v1/edi/validate-realtime",
        json=valid_request.model_dump(),
        headers={"Authorization": "Bearer test-token"}
    )
    
    assert response.status_code == 200
    
    # Validate response structure
    data = response.json()
    required_fields = [
        "valid", "validation_results", "ta1_content", 
        "workflow_id", "processed_at", "processing_time_ms"
    ]
    
    for field in required_fields:
        assert field in data, f"Missing required field: {field}"
    
    # Validate types
    assert isinstance(data["valid"], bool)
    assert isinstance(data["validation_results"], list)
    assert isinstance(data["processing_time_ms"], int)
```

## Service Integration Testing

### 1. **Service Mock Patterns**

```python
@pytest.fixture
def mock_edi_validation_service():
    """Mock EDI validation service with realistic responses."""
    service = AsyncMock()
    
    # Configure realistic return values
    service.validate_edi.return_value = ValidationResult(
        valid=True,
        findings=[]
    )
    
    service.generate_ta1.return_value = "ISA*00*...*TA1*000000001*A~"
    
    return service

@pytest.mark.asyncio
async def test_with_service_mock(self, async_client, valid_request, mock_edi_validation_service):
    """Test endpoint with mocked service."""
    with patch('src.api.endpoints.edi_validation.EDIValidationService', 
               return_value=mock_edi_validation_service):
        
        response = await async_client.post(
            "/api/v1/edi/validate-realtime",
            json=valid_request.model_dump(),
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 200
        
        # Verify service was called correctly
        mock_edi_validation_service.validate_edi.assert_called_once_with(
            edi_content=valid_request.edi_content,
            schema_name=valid_request.validation_schema,
            tenant_id=valid_request.tenant_id,
            snip_level=valid_request.snip_level
        )
```

### 2. **Error Scenario Testing**

```python
@pytest.mark.asyncio
async def test_service_error_handling(self, async_client, valid_request):
    """Test proper error handling when service fails."""
    mock_service = AsyncMock()
    mock_service.validate_edi.side_effect = ValueError("Schema not found")
    
    with patch('src.api.endpoints.edi_validation.EDIValidationService',
               return_value=mock_service):
        
        response = await async_client.post(
            "/api/v1/edi/validate-realtime", 
            json=valid_request.model_dump(),
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 500
        assert "Schema not found" in response.json()["detail"]
```

## Test Data Management

### 1. **Realistic EDI Test Data**

```python
# backend/tests/conftest.py

@pytest.fixture
def valid_837p_edi_string():
    """Valid 837P EDI document for testing."""
    return """ISA*00*          *00*          *ZZ*123456789012345*ZZ*SUBMITTERID1234*251231*1234*^*00501*000000001*0*P*>~
GS*HC*123456789012345*SUBMITTERID1234*20251231*1234*1*X*005010X222A1~
ST*837*0001*005010X222A1~
BHT*0019*00*1234567890*20251231*1234*CH~
NM1*41*2*SUBMITTER NAME*****46*123456789~
PER*IC*CONTACT NAME*TE*1234567890~
NM1*40*2*RECEIVER NAME*****46*987654321~
HL*1**20*1~
NM1*85*2*BILLING PROVIDER*****XX*1234567890~
N3*123 MAIN ST~
N4*ANYTOWN*ST*12345~
REF*EI*123456789~
HL*2*1*22*0~
SBR*P*18*GROUP123*GROUP NAME*CI***CI~
NM1*IL*1*PATIENT*JOHN****MI*123456789~
N3*456 ELM ST~
N4*ANYTOWN*ST*12345~
DMG*D8*19800101*M~
REF*SY*123456789~
HL*3*2*23*0~
PAT*19~
NM1*QC*1*PATIENT*JOHN~
CLM*CLAIM123*100.00***11:B:1*Y*A*Y*I~
DTP*431*D8*20251201~
CL1*1*1*01~
REF*D9*CLAIM123~
HI*BK:Z1234~
LX*1~
SV1*HC:99213*75.00*UN*1***1~
DTP*472*D8*20251201~
LX*2~
SV1*HC:99214*25.00*UN*1***1~
DTP*472*D8*20251201~
SE*32*0001~
GE*1*1~
IEA*1*000000001~"""

@pytest.fixture
def invalid_edi_string():
    """Invalid EDI document for error testing."""
    return """INVALID EDI CONTENT
THIS IS NOT A VALID EDI DOCUMENT
MISSING ISA HEADER AND PROPER STRUCTURE"""

@pytest.fixture
def complex_837p_edi_string():
    """Complex 837P with multiple claims and providers."""
    # Return more complex EDI document with multiple HL loops,
    # multiple claims, various segment types, etc.
    pass
```

### 2. **Test Data Organization**

```python
# Load test data from files
@pytest.fixture
def test_data_loader():
    """Utility for loading test data files."""
    import os
    from pathlib import Path
    
    test_data_dir = Path(__file__).parent / "data" / "test_files"
    
    def load_file(filename):
        file_path = test_data_dir / filename
        if not file_path.exists():
            raise FileNotFoundError(f"Test data file not found: {filename}")
        return file_path.read_text()
    
    return load_file

@pytest.fixture
def valid_837p_from_file(test_data_loader):
    """Load valid 837P from test data file."""
    return test_data_loader("valid_837p.edi")
```

## Performance Testing

### 1. **Response Time Testing**

```python
@pytest.mark.asyncio
async def test_response_time_performance(self, async_client, valid_request):
    """Test API response time meets requirements."""
    import time
    
    start_time = time.time()
    
    response = await async_client.post(
        "/api/v1/edi/validate-realtime",
        json=valid_request.model_dump(),
        headers={"Authorization": "Bearer test-token"}
    )
    
    end_time = time.time()
    response_time_ms = (end_time - start_time) * 1000
    
    assert response.status_code == 200
    assert response_time_ms < 1000, f"Response time {response_time_ms}ms exceeds 1000ms threshold"
    
    # Also check the reported processing time
    data = response.json()
    assert data["processing_time_ms"] < 500
```

### 2. **Load Testing Patterns**

```python
@pytest.mark.asyncio
async def test_concurrent_requests(self, async_client, valid_request):
    """Test handling of concurrent requests."""
    import asyncio
    
    async def make_request():
        return await async_client.post(
            "/api/v1/edi/validate-realtime",
            json=valid_request.model_dump(),
            headers={"Authorization": "Bearer test-token"}
        )
    
    # Make 10 concurrent requests
    tasks = [make_request() for _ in range(10)]
    responses = await asyncio.gather(*tasks)
    
    # All should succeed
    for response in responses:
        assert response.status_code == 200
    
    # Verify no resource conflicts
    response_data = [r.json() for r in responses]
    workflow_ids = [data["workflow_id"] for data in response_data]
    assert len(set(workflow_ids)) == 1  # All should have same workflow_id
```

## Error Testing Patterns

### 1. **Comprehensive Error Scenarios**

```python
class TestErrorHandling:
    """Dedicated test class for error scenarios."""
    
    @pytest.mark.asyncio
    async def test_malformed_request_body(self, async_client):
        """Test handling of malformed JSON."""
        response = await async_client.post(
            "/api/v1/edi/validate-realtime",
            data="invalid json{",  # Malformed JSON
            headers={
                "Authorization": "Bearer test-token",
                "Content-Type": "application/json"
            }
        )
        
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_missing_required_fields(self, async_client):
        """Test validation of required fields."""
        incomplete_request = {
            "edi_content": "some content",
            # Missing tenant_id, workflow_id, validation_schema
        }
        
        response = await async_client.post(
            "/api/v1/edi/validate-realtime",
            json=incomplete_request,
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 422
        
        error_data = response.json()
        assert "detail" in error_data
        # Validate that error details mention missing fields
    
    @pytest.mark.asyncio
    async def test_invalid_field_values(self, async_client, valid_request):
        """Test validation of field value constraints."""
        # Test invalid SNIP level
        valid_request.snip_level = 10  # Max is 5
        
        response = await async_client.post(
            "/api/v1/edi/validate-realtime",
            json=valid_request.model_dump(),
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == 422
```

### 2. **Service Failure Testing**

```python
@pytest.mark.asyncio
async def test_service_timeout_handling(self, async_client, valid_request):
    """Test handling of service timeouts."""
    import asyncio
    
    async def slow_validation(*args, **kwargs):
        await asyncio.sleep(30)  # Simulate timeout
        return ValidationResult(valid=True, findings=[])
    
    mock_service = AsyncMock()
    mock_service.validate_edi = slow_validation
    
    with patch('src.api.endpoints.edi_validation.EDIValidationService',
               return_value=mock_service):
        
        # This should timeout and be handled gracefully
        response = await async_client.post(
            "/api/v1/edi/validate-realtime",
            json=valid_request.model_dump(),
            headers={"Authorization": "Bearer test-token"}
        )
        
        # Should get a timeout error, not hang indefinitely
        assert response.status_code in [500, 504]
```

## Test Execution Strategies

### 1. **Running Tests**

```bash
# Run all tests
./run.sh dev:test integration tests/api/test_edi_validation.py

# Run specific test class
./run.sh dev:test integration tests/api/test_edi_validation.py::TestRealtimeEDIValidation

# Run specific test with verbose output
./run.sh dev:test integration tests/api/test_edi_validation.py::TestRealtimeEDIValidation::test_valid_edi_document -v

# Run with debug logging
./run.sh dev:test integration tests/api/test_edi_validation.py -v -s --log-cli-level=DEBUG

# Run specific pattern
./run.sh dev:test integration tests/api/test_edi_validation.py -k "authentication"
```

### 2. **Test Organization for CI/CD**

```bash
# Fast unit tests (< 1 minute)
pytest tests/services/ tests/core/ -v

# Integration tests (< 5 minutes)  
./run.sh dev:test integration tests/api/

# Full test suite (< 10 minutes)
./run.sh dev:test integration tests/
```

## Best Practices Summary

### 1. **Test Design Principles**
- **Isolation**: Each test should be independent
- **Repeatability**: Tests should produce consistent results
- **Clarity**: Test names and structure should be self-documenting
- **Coverage**: Test both happy path and error scenarios
- **Performance**: Tests should execute quickly

### 2. **Fixture Management**
- Use module-level fixtures for shared setup
- Use class-level fixtures for test-specific setup
- Always clean up resources in fixture teardown
- Keep fixtures focused and single-purpose
- Document fixture purpose and usage

### 3. **Authentication Testing**
- Test all authentication scenarios
- Verify tenant isolation thoroughly
- Use proper dependency override patterns
- Always restore original state in cleanup
- Test both valid and invalid auth scenarios

### 4. **Data Management**
- Use realistic test data
- Include both valid and invalid scenarios
- Organize test data in dedicated files/directories
- Keep test data up-to-date with schema changes
- Use parameterized tests for data variations

### 5. **Error Handling**
- Test all error scenarios comprehensively
- Verify proper HTTP status codes
- Check error message content and structure
- Test error propagation through layers
- Validate error logging and monitoring

This testing framework provides a solid foundation for maintaining high-quality, reliable tests throughout all phases of the NiFi integration project.