# Phase 1.2 Implementation Guide

## Overview

Based on the successful completion of Phase 1.1 and the architectural learnings, this guide provides a detailed roadmap for implementing **Phase 1.2: TA1 Generation API**.

## Phase 1.2 Objectives

### Primary Goal
Create a dedicated TA1 Generation API that allows NiFi workflows to generate TA1 acknowledgments independently of the validation process.

### Success Criteria
- ✅ Standalone TA1 generation endpoint
- ✅ Support for both acceptance and rejection TA1s
- ✅ Integration with existing TA1Generator infrastructure
- ✅ Comprehensive test coverage
- ✅ Consistent authentication and error handling

## API Design

### Endpoint Specification

```http
POST /api/v1/edi/generate-ta1
Content-Type: application/json
Authorization: Bearer <service-token>

{
  "edi_content": "ISA*00*...",
  "tenant_id": "tenant-a",
  "workflow_id": "ta1-generation-001",
  "acknowledgment_code": "A",  // A=Accept, R=Reject, E=Error
  "error_code": null,          // Optional: IK901 error code if needed
  "error_note": null           // Optional: Error description
}
```

### Response Format

```json
{
  "ta1_content": "ISA*00*...*TA1*000000001*A~IEA*1*000000001~",
  "control_number": "000000001",
  "acknowledgment_code": "A",
  "workflow_id": "ta1-generation-001",
  "generated_at": "2025-08-14T12:34:56Z"
}
```

## Implementation Steps

### Step 1: Create Request/Response Schemas

```python
# File: backend/src/api/schemas.py

class TA1GenerationRequest(BaseModel):
    """Request schema for TA1 generation."""
    edi_content: str = Field(..., description="Original EDI content containing ISA header")
    tenant_id: str = Field(..., description="Tenant identifier")
    workflow_id: str = Field(..., description="NiFi workflow identifier")
    acknowledgment_code: str = Field(
        ..., 
        regex="^[ARE]$", 
        description="A=Accept, R=Reject, E=Error"
    )
    error_code: Optional[str] = Field(
        None, 
        description="IK901 error code (required if acknowledgment_code=E)"
    )
    error_note: Optional[str] = Field(
        None, 
        description="Human-readable error description"
    )

class TA1GenerationResponse(BaseModel):
    """Response schema for TA1 generation."""
    ta1_content: str = Field(..., description="Generated TA1 acknowledgment")
    control_number: str = Field(..., description="TA1 control number")
    acknowledgment_code: str = Field(..., description="Acknowledgment code used")
    workflow_id: str = Field(..., description="Original workflow identifier")
    generated_at: datetime = Field(..., description="Generation timestamp")
    processing_time_ms: int = Field(..., description="Processing time in milliseconds")
```

### Step 2: Create TA1 Generation Service

```python
# File: backend/src/services/ta1_generation_service.py

import logging
import time
from datetime import datetime
from typing import Optional

from src.core.acknowledgements.ta1_generator import TA1Generator
from src.core.cdm import CdmSegment, CdmElement
from src.api.schemas import TA1GenerationRequest, TA1GenerationResponse

logger = logging.getLogger(__name__)

class TA1GenerationService:
    """Service for generating TA1 acknowledgments."""
    
    def __init__(self):
        self.ta1_generator = TA1Generator()
    
    async def generate_ta1(self, request: TA1GenerationRequest) -> TA1GenerationResponse:
        """
        Generate TA1 acknowledgment based on request parameters.
        
        Args:
            request: TA1 generation request
            
        Returns:
            TA1GenerationResponse containing generated acknowledgment
        """
        start_time = time.time()
        
        try:
            logger.info(f"Generating TA1 for workflow: {request.workflow_id}")
            
            # Extract ISA header from EDI content
            isa_segment = self._extract_isa_segment(request.edi_content)
            if not isa_segment:
                raise ValueError("Invalid EDI content: ISA segment not found or malformed")
            
            # Create interchange errors based on request
            interchange_errors = self._create_interchange_errors(
                acknowledgment_code=request.acknowledgment_code,
                error_code=request.error_code,
                error_note=request.error_note
            )
            
            # Generate TA1 using existing infrastructure
            ta1_content = self.ta1_generator.generate(
                isa_header=isa_segment,
                errors=interchange_errors
            )
            
            # Extract control number from generated TA1
            control_number = self._extract_ta1_control_number(ta1_content)
            
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            logger.info(f"TA1 generated successfully: control_number={control_number}")
            
            return TA1GenerationResponse(
                ta1_content=ta1_content,
                control_number=control_number,
                acknowledgment_code=request.acknowledgment_code,
                workflow_id=request.workflow_id,
                generated_at=datetime.utcnow(),
                processing_time_ms=processing_time_ms
            )
            
        except Exception as e:
            logger.error(f"TA1 generation failed: {e}", exc_info=True)
            raise
    
    def _extract_isa_segment(self, edi_content: str) -> Optional[CdmSegment]:
        """Extract ISA header as CdmSegment from EDI content."""
        try:
            lines = edi_content.strip().split('\n')
            if not lines:
                return None
                
            first_line = lines[0].strip()
            if not first_line.startswith('ISA'):
                return None
            
            # Store raw segment
            raw_segment = first_line
            
            # Remove segment terminator if present
            if first_line.endswith('~'):
                first_line = first_line[:-1]
            
            # Split ISA elements
            elements = first_line.split('*')
            if len(elements) < 17:  # ISA + 16 elements
                logger.error(f"ISA segment incomplete: expected 17 parts, got {len(elements)}")
                return None
            
            # Create CDM elements (skip segment ID)
            cdm_elements = []
            for i, element_value in enumerate(elements[1:], 1):
                cdm_elements.append(CdmElement(
                    element_id=f"ISA{i:02d}",
                    value=element_value,
                    position=i
                ))
            
            return CdmSegment(
                segment_id="ISA",
                elements=cdm_elements,
                line_number=1,
                raw_segment=raw_segment
            )
            
        except Exception as e:
            logger.error(f"ISA segment extraction failed: {e}", exc_info=True)
            return None
    
    def _create_interchange_errors(
        self, 
        acknowledgment_code: str,
        error_code: Optional[str] = None,
        error_note: Optional[str] = None
    ) -> list:
        """Create interchange errors based on acknowledgment parameters."""
        # For acceptance (A), return empty error list
        if acknowledgment_code == "A":
            return []
        
        # For rejection (R) or error (E), create appropriate error
        errors = []
        
        # Implementation depends on your InterchangeError structure
        # This is a placeholder - adjust based on actual error class
        if acknowledgment_code in ["R", "E"]:
            error = {
                "error_code": error_code or "IK901",
                "error_note": error_note or "Interchange rejected",
                "acknowledgment_code": acknowledgment_code
            }
            errors.append(error)
        
        return errors
    
    def _extract_ta1_control_number(self, ta1_content: str) -> str:
        """Extract control number from generated TA1."""
        try:
            # TA1 format: TA1*<control_number>*<ack_code>~
            lines = ta1_content.strip().split('\n')
            for line in lines:
                if line.startswith('TA1*'):
                    elements = line.split('*')
                    if len(elements) >= 2:
                        return elements[1]
            
            logger.warning("Could not extract control number from TA1")
            return "UNKNOWN"
            
        except Exception as e:
            logger.error(f"TA1 control number extraction failed: {e}")
            return "UNKNOWN"
```

### Step 3: Create API Endpoint

```python
# File: backend/src/api/endpoints/ta1_generation.py

from fastapi import APIRouter, Depends, HTTPException, status
import logging
import time
from datetime import datetime

from src.api.schemas import TA1GenerationRequest, TA1GenerationResponse
from src.core.auth import require_service_auth, ServiceContext
from src.services.ta1_generation_service import TA1GenerationService

router = APIRouter(prefix="/edi", tags=["TA1 Generation"])
logger = logging.getLogger(__name__)

@router.post("/generate-ta1", response_model=TA1GenerationResponse)
async def generate_ta1(
    request: TA1GenerationRequest,
    auth: ServiceContext = Depends(require_service_auth)
):
    """
    Generate TA1 acknowledgment from EDI content.
    
    This endpoint allows NiFi workflows to generate TA1 acknowledgments
    independently of the validation process. Supports acceptance, rejection,
    and error acknowledgments.
    """
    start_time = time.time()
    
    try:
        # Validate tenant access
        logger.debug(f"Checking tenant access for tenant_id: {request.tenant_id}")
        
        if not auth.has_tenant_access(request.tenant_id):
            logger.info(f"Access denied for tenant '{request.tenant_id}' - service '{auth.service_name}' not authorized")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to specified tenant"
            )
        
        # Validate acknowledgment code and error requirements
        if request.acknowledgment_code == "E" and not request.error_code:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="error_code is required when acknowledgment_code is 'E'"
            )
        
        # Initialize TA1 generation service
        ta1_service = TA1GenerationService()
        
        # Generate TA1
        result = await ta1_service.generate_ta1(request)
        
        logger.info(f"TA1 generation completed: workflow_id={request.workflow_id}, control_number={result.control_number}")
        
        return result
        
    except HTTPException:
        # Re-raise HTTP exceptions (like 403 Forbidden) as-is
        raise
    except Exception as e:
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        # Log error for monitoring
        logger.error(f"TA1 generation failed: {str(e)}", exc_info=True)
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"TA1 generation failed: {str(e)}"
        )
```

### Step 4: Register Router

```python
# File: backend/src/main.py

# Add import
from src.api.endpoints import ta1_generation

# Register router
app.include_router(ta1_generation.router, prefix="/api/v1")
```

### Step 5: Create Comprehensive Tests

```python
# File: backend/tests/api/test_ta1_generation.py

import pytest
from fastapi import status
from unittest.mock import AsyncMock, patch

from src.api.schemas import TA1GenerationRequest, TA1GenerationResponse


@pytest.mark.integration
class TestTA1Generation:
    """Test suite for TA1 generation API."""
    
    @pytest.fixture
    def ta1_request_accept(self, valid_837p_edi_string):
        """TA1 generation request for acceptance."""
        return TA1GenerationRequest(
            edi_content=valid_837p_edi_string,
            tenant_id="tenant-a",
            workflow_id="ta1-accept-001",
            acknowledgment_code="A"
        )
    
    @pytest.fixture
    def ta1_request_reject(self, valid_837p_edi_string):
        """TA1 generation request for rejection."""
        return TA1GenerationRequest(
            edi_content=valid_837p_edi_string,
            tenant_id="tenant-a", 
            workflow_id="ta1-reject-001",
            acknowledgment_code="R",
            error_code="IK901",
            error_note="Interchange rejected due to syntax errors"
        )
    
    @pytest.mark.asyncio
    async def test_generate_acceptance_ta1(self, async_client, ta1_request_accept):
        """Test successful TA1 acceptance generation."""
        response = await async_client.post(
            "/api/v1/edi/generate-ta1",
            json=ta1_request_accept.model_dump(),
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert data["acknowledgment_code"] == "A"
        assert data["workflow_id"] == "ta1-accept-001"
        assert data["ta1_content"] is not None
        assert data["control_number"] is not None
        assert "generated_at" in data
        assert "processing_time_ms" in data
    
    @pytest.mark.asyncio
    async def test_generate_rejection_ta1(self, async_client, ta1_request_reject):
        """Test successful TA1 rejection generation."""
        response = await async_client.post(
            "/api/v1/edi/generate-ta1",
            json=ta1_request_reject.model_dump(),
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert data["acknowledgment_code"] == "R"
        assert data["workflow_id"] == "ta1-reject-001"
        assert data["ta1_content"] is not None
        assert data["control_number"] is not None
    
    @pytest.mark.asyncio
    async def test_invalid_edi_content(self, async_client):
        """Test TA1 generation with invalid EDI content."""
        request = TA1GenerationRequest(
            edi_content="INVALID EDI CONTENT",
            tenant_id="tenant-a",
            workflow_id="ta1-invalid-001",
            acknowledgment_code="A"
        )
        
        response = await async_client.post(
            "/api/v1/edi/generate-ta1",
            json=request.model_dump(),
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "ISA segment not found" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_error_code_required_for_error_ack(self, async_client, valid_837p_edi_string):
        """Test that error_code is required when acknowledgment_code is 'E'."""
        request = TA1GenerationRequest(
            edi_content=valid_837p_edi_string,
            tenant_id="tenant-a",
            workflow_id="ta1-error-001",
            acknowledgment_code="E"
            # Missing error_code
        )
        
        response = await async_client.post(
            "/api/v1/edi/generate-ta1",
            json=request.model_dump(),
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "error_code is required" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_tenant_isolation(self, async_client, ta1_request_accept):
        """Test tenant access control."""
        from src.main import app
        from src.core.auth import require_service_auth, ServiceContext
        
        # Create auth context that denies access to tenant-a
        mock_context = ServiceContext(
            service_name="test-service",
            allowed_tenants=["tenant-b"]  # Does not include tenant-a
        )
        
        original_override = app.dependency_overrides.get(require_service_auth)
        app.dependency_overrides[require_service_auth] = lambda: mock_context
        
        try:
            response = await async_client.post(
                "/api/v1/edi/generate-ta1",
                json=ta1_request_accept.model_dump(),
                headers={"Authorization": "Bearer test-token"}
            )
            
            assert response.status_code == status.HTTP_403_FORBIDDEN
            assert "Access denied" in response.json()["detail"]
        finally:
            if original_override:
                app.dependency_overrides[require_service_auth] = original_override
```

## Integration Points

### 1. **NiFi Workflow Integration**

```xml
<!-- NiFi processor configuration -->
<processor>
    <name>GenerateTA1</name>
    <class>org.apache.nifi.processors.standard.InvokeHTTP</class>
    <properties>
        <property name="HTTP Method">POST</property>
        <property name="Remote URL">http://backend:8000/api/v1/edi/generate-ta1</property>
        <property name="Content-Type">application/json</property>
        <property name="Authorization">Bearer ${service.token}</property>
    </properties>
</processor>
```

### 2. **Request Body Template**

```json
{
  "edi_content": "${flowfile.content}",
  "tenant_id": "${tenant.id}",
  "workflow_id": "${uuid}",
  "acknowledgment_code": "${ack.code}",
  "error_code": "${error.code:null}",
  "error_note": "${error.note:null}"
}
```

## Testing Strategy

### 1. **Unit Tests**
- TA1GenerationService methods
- ISA segment extraction
- Error creation logic
- Control number extraction

### 2. **Integration Tests**
- API endpoint functionality
- Authentication and authorization
- Error handling scenarios
- Response format validation

### 3. **End-to-End Tests**
- Complete NiFi workflow simulation
- Real EDI content processing
- TA1 format validation
- Performance benchmarks

## Error Handling

### 1. **Client Errors (4xx)**
- `400`: Invalid request format
- `403`: Tenant access denied
- `422`: Validation errors (missing error_code, etc.)

### 2. **Server Errors (5xx)**
- `500`: TA1 generation failures
- `500`: ISA segment extraction errors
- `500`: Internal service errors

## Performance Considerations

### 1. **Response Time Targets**
- Target: < 100ms for typical TA1 generation
- Acceptable: < 500ms for complex scenarios
- Timeout: 30 seconds maximum

### 2. **Scalability**
- Stateless service design
- No external dependencies for generation
- Memory-efficient ISA parsing

## Monitoring and Observability

### 1. **Logging**
- Request/response logging
- Error tracking with stack traces
- Performance metrics
- Tenant access auditing

### 2. **Metrics**
- Generation success rate
- Response time distribution
- Error rate by type
- Tenant usage patterns

## Deployment Checklist

- [ ] API endpoint implemented and tested
- [ ] Service layer with robust error handling
- [ ] Comprehensive test suite (unit + integration)
- [ ] Documentation and API specs updated
- [ ] Performance testing completed
- [ ] Security review passed
- [ ] NiFi integration tested
- [ ] Monitoring and logging configured

## Success Metrics

### 1. **Functional Metrics**
- 100% test coverage
- All test scenarios passing
- API response time < 100ms
- Zero critical security findings

### 2. **Integration Metrics**
- Successful NiFi workflow integration
- TA1 format compliance validation
- Proper error propagation
- Tenant isolation verification

## Next Steps After Phase 1.2

1. **Phase 1.3**: 999 Generation API (similar patterns)
2. **Phase 2**: Batch processing workflows
3. **Phase 3**: Advanced monitoring and metrics
4. **Phase 4**: Performance optimization and caching

This implementation guide provides a complete roadmap for Phase 1.2, leveraging all the patterns and learnings from Phase 1.1 while maintaining consistency with the established architecture.