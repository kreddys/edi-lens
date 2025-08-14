# FILE: backend/tests/api/test_ta1_generation.py

import pytest
from fastapi import status
from unittest.mock import AsyncMock, patch

from src.api.schemas import TA1GenerationRequest, TA1GenerationResponse


# Module-level fixtures available to all test classes
@pytest.fixture
def mock_auth_context():
    """Module-level auth context available to all test classes."""
    from src.core.auth import ServiceContext
    return ServiceContext(
        service_name="nifi-service",
        allowed_tenants=[]  # Empty means all tenants allowed
    )

@pytest.fixture
def ta1_request_accept(valid_837p_edi_string):
    """TA1 generation request for acceptance."""
    return TA1GenerationRequest(
        edi_content=valid_837p_edi_string,
        tenant_id="tenant-a",
        workflow_id="ta1-accept-001",
        acknowledgment_code="A"
    )

@pytest.fixture
def ta1_request_reject(valid_837p_edi_string):
    """TA1 generation request for rejection."""
    return TA1GenerationRequest(
        edi_content=valid_837p_edi_string,
        tenant_id="tenant-a",
        workflow_id="ta1-reject-001", 
        acknowledgment_code="R",
        error_code="IK901",
        error_note="Interchange rejected due to syntax errors"
    )

@pytest.fixture
def ta1_request_error(valid_837p_edi_string):
    """TA1 generation request for error acknowledgment."""
    return TA1GenerationRequest(
        edi_content=valid_837p_edi_string,
        tenant_id="tenant-a",
        workflow_id="ta1-error-001",
        acknowledgment_code="E",
        error_code="IK903",
        error_note="Interchange control number mismatch"
    )


@pytest.mark.integration
class TestTA1Generation:
    """Test suite for TA1 generation API."""
    
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
        
        # Validate response structure
        required_fields = [
            "ta1_content", "control_number", "acknowledgment_code", 
            "workflow_id", "generated_at", "processing_time_ms"
        ]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        
        # Validate response content
        assert data["acknowledgment_code"] == "A"
        assert data["workflow_id"] == "ta1-accept-001"
        assert data["ta1_content"] is not None
        assert data["control_number"] is not None
        assert isinstance(data["processing_time_ms"], int)
        
        # Validate TA1 content format
        ta1_content = data["ta1_content"]
        assert "TA1*" in ta1_content, "TA1 content should contain TA1 segment"
        assert "ISA*" in ta1_content, "TA1 content should contain ISA segment"
        assert "IEA*" in ta1_content, "TA1 content should contain IEA segment"
    
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
        
        # Validate rejection-specific content
        assert data["acknowledgment_code"] == "R"
        assert data["workflow_id"] == "ta1-reject-001"
        assert data["ta1_content"] is not None
        assert data["control_number"] is not None
        
        # For rejection, TA1 should contain rejection indicator
        ta1_content = data["ta1_content"]
        assert "TA1*" in ta1_content, "TA1 content should contain TA1 segment"
    
    @pytest.mark.asyncio
    async def test_generate_error_ta1(self, async_client, ta1_request_error):
        """Test successful TA1 error acknowledgment generation."""
        response = await async_client.post(
            "/api/v1/edi/generate-ta1",
            json=ta1_request_error.model_dump(),
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        
        # Validate error-specific content
        assert data["acknowledgment_code"] == "E"
        assert data["workflow_id"] == "ta1-error-001"
        assert data["ta1_content"] is not None
        assert data["control_number"] is not None
    
    @pytest.mark.asyncio
    async def test_invalid_edi_content(self, async_client):
        """Test TA1 generation with invalid EDI content."""
        request = TA1GenerationRequest(
            edi_content="INVALID EDI CONTENT WITHOUT ISA HEADER",
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
        error_detail = response.json()["detail"]
        assert "ISA segment not found" in error_detail or "malformed" in error_detail
    
    @pytest.mark.asyncio
    async def test_empty_edi_content(self, async_client):
        """Test TA1 generation with empty EDI content."""
        request = TA1GenerationRequest(
            edi_content="",
            tenant_id="tenant-a",
            workflow_id="ta1-empty-001",
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
            workflow_id="ta1-error-missing-code-001",
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
    async def test_invalid_acknowledgment_code(self, async_client, valid_837p_edi_string):
        """Test validation of acknowledgment_code field."""
        request_data = {
            "edi_content": valid_837p_edi_string,
            "tenant_id": "tenant-a",
            "workflow_id": "ta1-invalid-ack-001",
            "acknowledgment_code": "X"  # Invalid acknowledgment code
        }
        
        response = await async_client.post(
            "/api/v1/edi/generate-ta1",
            json=request_data,
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    @pytest.mark.asyncio
    async def test_missing_required_fields(self, async_client):
        """Test validation of required fields."""
        incomplete_request = {
            "edi_content": "some content",
            # Missing tenant_id, workflow_id, acknowledgment_code
        }
        
        response = await async_client.post(
            "/api/v1/edi/generate-ta1",
            json=incomplete_request,
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        
        error_data = response.json()
        assert "detail" in error_data


@pytest.mark.integration  
class TestTA1GenerationAuthentication:
    """Test authentication and authorization for TA1 generation API."""
    
    @pytest.mark.asyncio
    async def test_authentication_required(self):
        """Test that the endpoint requires authentication."""
        from fastapi.testclient import TestClient
        from src.main import app
        
        # Use client without dependency overrides
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/edi/generate-ta1",
                json={"some": "data"}
                # No Authorization header
            )
            
            assert response.status_code in [401, 422]
    
    @pytest.mark.asyncio
    async def test_tenant_isolation(self, async_client, ta1_request_accept):
        """Test tenant access control."""
        from src.main import app
        from src.core.auth import require_service_auth, ServiceContext
        
        # Create auth context that denies access to tenant-a
        mock_context = ServiceContext(
            service_name="test-service",
            allowed_tenants=["tenant-b", "tenant-c"]  # Does NOT include tenant-a
        )
        
        # Temporarily override auth
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
            # Always restore original override
            if original_override:
                app.dependency_overrides[require_service_auth] = original_override
    
    @pytest.mark.asyncio
    async def test_service_with_limited_tenants(self, async_client, ta1_request_accept):
        """Test service with specific tenant restrictions."""
        from src.main import app
        from src.core.auth import require_service_auth, ServiceContext
        
        # Modify request to use allowed tenant
        ta1_request_accept.tenant_id = "tenant-b"
        
        # Override auth to allow only tenant-b
        mock_context = ServiceContext(
            service_name="restricted-service",
            allowed_tenants=["tenant-b"]
        )
        
        original_override = app.dependency_overrides.get(require_service_auth)
        app.dependency_overrides[require_service_auth] = lambda: mock_context
        
        try:
            response = await async_client.post(
                "/api/v1/edi/generate-ta1",
                json=ta1_request_accept.model_dump(),
                headers={"Authorization": "Bearer test-token"}
            )
            
            assert response.status_code == status.HTTP_200_OK
        finally:
            if original_override:
                app.dependency_overrides[require_service_auth] = original_override


@pytest.mark.integration
class TestTA1GenerationErrorHandling:
    """Test error handling scenarios for TA1 generation API."""
    
    @pytest.mark.asyncio
    async def test_malformed_request_body(self, async_client):
        """Test handling of malformed JSON."""
        response = await async_client.post(
            "/api/v1/edi/generate-ta1",
            data="invalid json{",  # Malformed JSON
            headers={
                "Authorization": "Bearer test-token",
                "Content-Type": "application/json"
            }
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    @pytest.mark.asyncio
    async def test_service_error_handling(self, async_client, ta1_request_accept):
        """Test proper error handling when service fails."""
        with patch('src.api.endpoints.ta1_generation.TA1GenerationService') as mock_service_class:
            mock_service = AsyncMock()
            mock_service.generate_ta1.side_effect = ValueError("TA1 generation failed")
            mock_service_class.return_value = mock_service
            
            response = await async_client.post(
                "/api/v1/edi/generate-ta1",
                json=ta1_request_accept.model_dump(),
                headers={"Authorization": "Bearer test-token"}
            )
            
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert "TA1 generation failed" in response.json()["detail"]
    
    @pytest.mark.asyncio 
    async def test_malformed_isa_segment(self, async_client):
        """Test handling of malformed ISA segment."""
        request = TA1GenerationRequest(
            edi_content="ISA*incomplete*segment",  # Malformed ISA
            tenant_id="tenant-a",
            workflow_id="ta1-malformed-isa-001",
            acknowledgment_code="A"
        )
        
        response = await async_client.post(
            "/api/v1/edi/generate-ta1", 
            json=request.model_dump(),
            headers={"Authorization": "Bearer test-token"}
        )
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        error_detail = response.json()["detail"]
        assert "ISA segment" in error_detail


@pytest.mark.integration
class TestTA1GenerationPerformance:
    """Test performance characteristics of TA1 generation API."""
    
    @pytest.mark.asyncio
    async def test_response_time_performance(self, async_client, ta1_request_accept):
        """Test API response time meets requirements."""
        import time
        
        start_time = time.time()
        
        response = await async_client.post(
            "/api/v1/edi/generate-ta1",
            json=ta1_request_accept.model_dump(),
            headers={"Authorization": "Bearer test-token"}
        )
        
        end_time = time.time()
        response_time_ms = (end_time - start_time) * 1000
        
        assert response.status_code == status.HTTP_200_OK
        assert response_time_ms < 1000, f"Response time {response_time_ms}ms exceeds 1000ms threshold"
        
        # Also check the reported processing time
        data = response.json()
        assert data["processing_time_ms"] < 500, f"Processing time {data['processing_time_ms']}ms exceeds 500ms threshold"
    
    @pytest.mark.asyncio
    async def test_concurrent_requests(self, async_client, ta1_request_accept):
        """Test handling of concurrent TA1 generation requests."""
        import asyncio
        
        async def make_request(workflow_suffix):
            """Make a single TA1 generation request."""
            request = ta1_request_accept.model_copy()
            request.workflow_id = f"ta1-concurrent-{workflow_suffix}"
            
            return await async_client.post(
                "/api/v1/edi/generate-ta1",
                json=request.model_dump(),
                headers={"Authorization": "Bearer test-token"}
            )
        
        # Make 5 concurrent requests
        tasks = [make_request(i) for i in range(5)]
        responses = await asyncio.gather(*tasks)
        
        # All should succeed
        for i, response in enumerate(responses):
            assert response.status_code == status.HTTP_200_OK, f"Request {i} failed"
        
        # Verify unique workflow IDs in responses
        response_data = [r.json() for r in responses]
        workflow_ids = [data["workflow_id"] for data in response_data]
        assert len(set(workflow_ids)) == 5, "All responses should have unique workflow IDs"
        
        # Verify all responses have valid TA1 content
        for data in response_data:
            assert data["ta1_content"] is not None
            assert data["control_number"] is not None
            assert data["acknowledgment_code"] == "A"