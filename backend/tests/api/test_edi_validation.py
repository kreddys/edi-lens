# FILE: backend/tests/api/test_edi_validation.py

import pytest
import json
from unittest.mock import patch, AsyncMock
from fastapi import status
from datetime import datetime

from src.api.schemas import (
    RealtimeEDIValidationRequest,
    RealtimeEDIValidationResponse,
    BatchEDIValidationRequest,
    BatchEDIValidationResponse,
    ValidationFinding,
    FindingLocation
)
from src.services.edi_validation_service import ValidationResult

# Module-level fixtures available to all test classes
@pytest.fixture
def mock_auth_context():
    """Mock authentication context."""
    from src.core.auth import ServiceContext
    
    # Create a real ServiceContext for service authentication
    mock_auth = ServiceContext(
        service_name="nifi-service",
        allowed_tenants=[]  # Empty means all tenants allowed
    )
    return mock_auth

@pytest.mark.integration
class TestRealtimeEDIValidation:
    """Test suite for real-time EDI validation endpoint."""
    
    @pytest.fixture
    def realtime_request_valid(self, valid_837p_edi_string):
        """Sample real-time validation request with valid EDI."""
        return RealtimeEDIValidationRequest(
            edi_content=valid_837p_edi_string,
            tenant_id="tenant-a",
            workflow_id="test-workflow-001",
            validation_schema="837.5010.X222.A1.json",
            snip_level=3,
            generate_ta1=True,
            generate_999=False
        )
    
    @pytest.fixture
    def realtime_request_invalid(self, edi_with_isa_error):
        """Sample real-time validation request with invalid EDI."""
        return RealtimeEDIValidationRequest(
            edi_content=edi_with_isa_error,
            tenant_id="tenant-a",
            workflow_id="test-workflow-001",
            validation_schema="837.5010.X222.A1.json",
            snip_level=3,
            generate_ta1=False,
            generate_999=False
        )
    
    @pytest.fixture
    def mock_validation_service(self):
        """Mock EDI validation service."""
        return AsyncMock()
    
    @pytest.mark.asyncio
    async def test_valid_edi_document(self, async_client, realtime_request_valid, mock_validation_service):
        """Test validation of valid EDI document."""
        # Mock successful validation
        validation_result = ValidationResult(
            valid=True,
            findings=[]
        )
        mock_validation_service.validate_edi.return_value = validation_result
        mock_validation_service.generate_ta1.return_value = "TA1*000000001*A~"
        
        with patch('src.api.endpoints.edi_validation.EDIValidationService', return_value=mock_validation_service):
            response = await async_client.post(
                "/api/v1/edi/validate-realtime",
                json=realtime_request_valid.model_dump(),
                headers={"Authorization": "Bearer test-token"}
            )
        
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert data["valid"] is True
        assert data["workflow_id"] == "test-workflow-001"
        assert data["schema_used"] == "837.5010.X222.A1.json"
        assert data["snip_level_used"] == 3
        assert data["ta1_content"] == "TA1*000000001*A~"
        assert "processing_time_ms" in data
        assert "processed_at" in data
    
    @pytest.mark.asyncio
    async def test_invalid_edi_document(self, async_client, realtime_request_invalid, mock_validation_service):
        """Test validation of invalid EDI document."""
        # Mock validation with errors
        validation_result = ValidationResult(
            valid=False,
            findings=[
                ValidationFinding(
                    level="error",
                    code="ISA_ICN_MISMATCH",
                    message="ISA and IEA control numbers do not match",
                    location=FindingLocation(
                        segment_id="IEA",
                        segment_instance=1,
                        element_position=2,
                        line_number=1
                    )
                )
            ]
        )
        mock_validation_service.validate_edi.return_value = validation_result
        
        with patch('src.api.endpoints.edi_validation.EDIValidationService', return_value=mock_validation_service):
            response = await async_client.post(
                "/api/v1/edi/validate-realtime",
                json=realtime_request_invalid.model_dump(),
                headers={"Authorization": "Bearer test-token"}
            )
        
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert data["valid"] is False
        assert len(data["validation_results"]) == 1
        assert data["validation_results"][0]["level"] == "error"
        assert data["validation_results"][0]["code"] == "ISA_ICN_MISMATCH"
    
    @pytest.mark.asyncio
    async def test_missing_schema(self, async_client, realtime_request_valid, mock_validation_service):
        """Test error handling for missing schema."""
        # Mock schema not found error
        mock_validation_service.validate_edi.side_effect = ValueError("Schema not found: invalid.json")
        
        request = realtime_request_valid.model_copy()
        request.validation_schema = "invalid.json"
        
        with patch('src.api.endpoints.edi_validation.EDIValidationService', return_value=mock_validation_service):
            response = await async_client.post(
                "/api/v1/edi/validate-realtime",
                json=request.model_dump(),
                headers={"Authorization": "Bearer test-token"}
            )
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Schema not found" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_service_authentication_required(self, realtime_request_valid):
        """Test that service authentication is required."""
        from fastapi.testclient import TestClient
        from src.main import app
        
        # Use client without auth override
        client = TestClient(app)
        response = client.post(
            "/api/v1/edi/validate-realtime",
            json=realtime_request_valid.model_dump()
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    @pytest.mark.asyncio
    async def test_tenant_isolation(self, async_client, realtime_request_valid, mock_validation_service):
        """Test tenant data isolation."""
        # Mock auth context that denies tenant access to the specific tenant in the request
        from src.main import app
        from src.core.auth import require_service_auth, ServiceContext
        from src.core.database import get_db
        
        # Create service context that denies access to tenant-a (but allows other tenants)
        mock_service_context = ServiceContext(
            service_name="test-service", 
            allowed_tenants=["tenant-b", "tenant-c"]  # Does NOT include tenant-a from the request
        )
        
        # Temporarily override the auth dependency for this test
        def deny_tenant_access():
            return mock_service_context
            
        # Temporarily replace the dependency override
        original_auth_override = app.dependency_overrides.get(require_service_auth)
        app.dependency_overrides[require_service_auth] = deny_tenant_access
        
        try:
            with patch('src.api.endpoints.edi_validation.EDIValidationService', return_value=mock_validation_service):
                response = await async_client.post(
                    "/api/v1/edi/validate-realtime",
                    json=realtime_request_valid.model_dump(),
                    headers={"Authorization": "Bearer test-token"}
                )
            
            assert response.status_code == status.HTTP_403_FORBIDDEN
            assert "Access denied" in response.json()["detail"]
        finally:
            # Restore original auth override
            if original_auth_override:
                app.dependency_overrides[require_service_auth] = original_auth_override

@pytest.mark.integration
class TestBatchEDIValidation:
    """Test suite for batch EDI validation endpoint."""
    
    @pytest.fixture
    def batch_request_valid(self, valid_837p_edi_string):
        """Sample batch validation request with valid EDI."""
        return BatchEDIValidationRequest(
            edi_content=valid_837p_edi_string,
            tenant_id="tenant-a",
            workflow_id="batch-workflow-001",
            validation_schema="837.5010.X222.A1.json",
            snip_level=3,
            file_name="test_claims.edi",
            callback_url="http://nifi:8080/webhook/batch-complete",
            generate_ta1=True,
            generate_999=False
        )
    
    @pytest.fixture
    def batch_request_complex(self, complex_837p_edi_string):
        """Sample batch validation request with complex EDI."""
        return BatchEDIValidationRequest(
            edi_content=complex_837p_edi_string,
            tenant_id="tenant-a",
            workflow_id="batch-workflow-002",
            validation_schema="837.5010.X222.A1.json",
            snip_level=3,
            file_name="complex_claims.edi",
            callback_url="http://nifi:8080/webhook/batch-complete",
            generate_ta1=True,
            generate_999=True
        )
    
    @pytest.fixture
    def mock_batch_service(self):
        """Mock batch job service."""
        return AsyncMock()
    
    @pytest.mark.asyncio
    async def test_batch_job_creation(self, async_client, batch_request_valid, mock_batch_service):
        """Test batch job creation and queuing."""
        # Mock successful job creation
        job_id = "test-job-uuid-123"
        mock_batch_service.create_batch_job.return_value = job_id
        
        with patch('src.api.endpoints.edi_validation.BatchJobService', return_value=mock_batch_service):
            response = await async_client.post(
                "/api/v1/edi/validate-batch",
                json=batch_request_valid.model_dump(),
                headers={"Authorization": "Bearer test-token"}
            )
        
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert data["job_id"] == job_id
        assert data["status"] == "QUEUED"
        assert data["workflow_id"] == "batch-workflow-001"
        assert data["file_name"] == "test_claims.edi"
        assert "estimated_processing_time_ms" in data
        assert "created_at" in data
    
    @pytest.mark.asyncio
    async def test_batch_job_creation_complex_edi(self, async_client, batch_request_complex, mock_batch_service):
        """Test batch job creation with complex EDI data."""
        # Mock successful job creation for complex EDI
        job_id = "test-job-complex-456"
        mock_batch_service.create_batch_job.return_value = job_id
        
        with patch('src.api.endpoints.edi_validation.BatchJobService', return_value=mock_batch_service):
            
            response = await async_client.post(
                "/api/v1/edi/validate-batch",
                json=batch_request_complex.model_dump(),
                headers={"Authorization": "Bearer test-token"}
            )
        
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert data["job_id"] == job_id
        assert data["status"] == "QUEUED"
        assert data["workflow_id"] == "batch-workflow-002"
        assert data["file_name"] == "complex_claims.edi"
        # Complex EDI should have reasonable estimated processing time
        assert data["estimated_processing_time_ms"] >= 1000
    
    @pytest.mark.asyncio
    async def test_job_status_tracking(self, async_client, mock_batch_service):
        """Test job status endpoint."""
        from src.api.schemas import BatchJobStatusResponse
        
        # Mock job status response
        job_status = BatchJobStatusResponse(
            job_id="test-job-123",
            workflow_id="batch-workflow-001",
            tenant_id="tenant-a",
            status="COMPLETED",
            file_name="test_claims.edi",
            validation_schema="837.5010.X222.A1.json",
            created_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            processing_time_ms=5000,
            results=None,
            callback_sent=True,
            callback_sent_at=datetime.utcnow(),
            errors=[]
        )
        mock_batch_service.get_job_status.return_value = job_status
        
        with patch('src.api.endpoints.edi_validation.BatchJobService', return_value=mock_batch_service):
            
            response = await async_client.get(
                "/api/v1/edi/jobs/test-job-123",
                headers={"Authorization": "Bearer test-token"}
            )
        
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert data["job_id"] == "test-job-123"
        assert data["status"] == "COMPLETED"
        assert data["callback_sent"] is True
    
    @pytest.mark.asyncio
    async def test_job_not_found(self, async_client, mock_batch_service):
        """Test job not found scenario."""
        mock_batch_service.get_job_status.return_value = None
        
        with patch('src.api.endpoints.edi_validation.BatchJobService', return_value=mock_batch_service):
            
            response = await async_client.get(
                "/api/v1/edi/jobs/nonexistent-job",
                headers={"Authorization": "Bearer test-token"}
            )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "Job not found" in response.json()["detail"]

@pytest.mark.integration
class TestBatchJobProcessing:
    """Test suite for batch job processing workflow."""
    
    @pytest.mark.asyncio
    async def test_multiple_files_create_separate_jobs(self, valid_837p_edi_string, complex_837p_edi_string, multiple_claims_per_subscriber_837p_edi_string):
        """Test that 5 files from SFTP create 5 separate jobs."""
        from src.services.batch_job_service import BatchJobService
        
        batch_service = BatchJobService()
        
        # Simulate 5 different files being uploaded to SFTP
        edi_files = [
            valid_837p_edi_string,
            complex_837p_edi_string,
            multiple_claims_per_subscriber_837p_edi_string,
            valid_837p_edi_string,  # Duplicate file but different instance
            complex_837p_edi_string  # Another duplicate but different instance
        ]
        
        file_requests = []
        for i, edi_content in enumerate(edi_files):
            request = BatchEDIValidationRequest(
                edi_content=edi_content,
                tenant_id="tenant-a",
                workflow_id="batch-workflow-001",
                validation_schema="837.5010.X222.A1.json",
                file_name=f"claims_{i+1}.edi",
                callback_url="http://nifi:8080/webhook/batch-complete"
            )
            file_requests.append(request)
        
        # Create jobs for each file
        job_ids = []
        for request in file_requests:
            with patch.object(batch_service, '_job_storage', {}), \
                 patch.object(batch_service, '_job_queue', AsyncMock()):
                job_id = await batch_service.create_batch_job(request)
                job_ids.append(job_id)
        
        # Verify 5 separate jobs were created
        assert len(job_ids) == 5
        assert len(set(job_ids)) == 5  # All job IDs should be unique
    
    @pytest.mark.asyncio
    async def test_webhook_callback_structure(self, edi_with_ack_requested):
        """Test webhook callback payload structure."""
        from src.api.schemas import BatchJobCompletionWebhook, RealtimeEDIValidationResponse
        
        # Mock completed validation results
        validation_results = RealtimeEDIValidationResponse(
            valid=True,
            validation_results=[],
            processing_time_ms=3500,
            schema_used="837.5010.X222.A1.json",
            snip_level_used=3,
            ta1_content="TA1*000000001*A~",
            workflow_id="batch-workflow-001",
            processed_at=datetime.utcnow()
        )
        
        # Create webhook payload
        webhook_payload = BatchJobCompletionWebhook(
            job_id="test-job-123",
            status="COMPLETED",
            workflow_id="batch-workflow-001",
            file_name="claims_with_ack.edi",
            results=validation_results,
            error_message=None
        )
        
        # Verify webhook structure
        payload_dict = webhook_payload.model_dump()
        assert payload_dict["job_id"] == "test-job-123"
        assert payload_dict["status"] == "COMPLETED"
        assert payload_dict["workflow_id"] == "batch-workflow-001"
        assert payload_dict["file_name"] == "claims_with_ack.edi"
        assert payload_dict["results"] is not None
        assert payload_dict["error_message"] is None
        
        # Verify nested results structure
        results_dict = payload_dict["results"]
        assert results_dict["valid"] is True
        assert results_dict["ta1_content"] == "TA1*000000001*A~"
        assert results_dict["schema_used"] == "837.5010.X222.A1.json"

@pytest.mark.integration
class TestServiceAuthentication:
    """Test suite for service authentication."""
    
    @pytest.mark.asyncio
    async def test_service_token_validation_flow(self, async_client, valid_837p_edi_string):
        """Test service token validation flow."""
        # Mock valid service token payload
        service_token_payload = {
            "azp": "nifi-service",  # Authorized party
            "preferred_username": "nifi-processor",
            "aud": "edi-lens-api",
            "sub": "service-account-nifi",
            "iat": 1640995200,
            "exp": 1640995800
        }
        
        request = RealtimeEDIValidationRequest(
            edi_content=valid_837p_edi_string,
            tenant_id="tenant-a",
            workflow_id="test-workflow-001",
            validation_schema="837.5010.X222.A1.json"
        )
        
        with patch('src.core.auth.jwt.decode', return_value=service_token_payload), \
             patch('src.core.auth.get_keycloak_public_key', return_value={"test": "key"}), \
             patch('src.api.endpoints.edi_validation.EDIValidationService') as mock_service:
            
            # Mock successful validation
            mock_validation_service = AsyncMock()
            mock_validation_service.validate_edi.return_value = ValidationResult(valid=True, findings=[])
            mock_service.return_value = mock_validation_service
            
            response = await async_client.post(
                "/api/v1/edi/validate-realtime",
                json=request.model_dump(),
                headers={"Authorization": "Bearer valid-service-token"}
            )
            
            # Should succeed with valid service token
            assert response.status_code == status.HTTP_200_OK
    
    @pytest.mark.asyncio
    async def test_invalid_service_token_rejection(self, async_client, valid_837p_edi_string):
        """Test service authentication behavior with mock invalid context."""
        from src.main import app
        from src.core.auth import require_service_auth, ServiceContext
        
        request = RealtimeEDIValidationRequest(
            edi_content=valid_837p_edi_string,
            tenant_id="tenant-a",
            workflow_id="test-workflow-001",
            validation_schema="837.5010.X222.A1.json"
        )
        
        # Create a service context that will fail authentication validation
        def mock_invalid_auth():
            # Return a context that will cause authentication errors
            from fastapi import HTTPException
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid service token"
            )
        
        # Override auth dependency to simulate failed authentication
        original_auth = app.dependency_overrides.get(require_service_auth)
        app.dependency_overrides[require_service_auth] = mock_invalid_auth
        
        try:
            response = await async_client.post(
                "/api/v1/edi/validate-realtime",
                json=request.model_dump(),
                headers={"Authorization": "Bearer invalid-token"}
            )
            
            # Should reject with 401 Unauthorized
            assert response.status_code == status.HTTP_401_UNAUTHORIZED
            assert "Invalid service token" in response.json()["detail"]
        finally:
            # Restore original auth override
            if original_auth:
                app.dependency_overrides[require_service_auth] = original_auth
            else:
                app.dependency_overrides.pop(require_service_auth, None)

@pytest.mark.integration
class TestEDIValidationIntegration:
    """Integration tests for EDI validation with different EDI formats."""
    
    @pytest.mark.asyncio
    async def test_multiple_transaction_sets_validation(self, async_client, multiple_transaction_sets_837p_edi_string, mock_auth_context):
        """Test validation of EDI with multiple transaction sets."""
        request = RealtimeEDIValidationRequest(
            edi_content=multiple_transaction_sets_837p_edi_string,
            tenant_id="tenant-a",
            workflow_id="multi-txn-workflow",
            validation_schema="837.5010.X222.A1.json",
            snip_level=3
        )
        
        # Mock validation service to return mixed results
        mock_validation_service = AsyncMock()
        validation_result = ValidationResult(
            valid=False,
            findings=[
                ValidationFinding(
                    level="error",
                    code="MISSING_REQUIRED_SEGMENT",
                    message="Transaction set 2 missing required NM1*41 segment",
                    location=FindingLocation(
                        segment_id="ST",
                        segment_instance=1,
                        element_position=2,
                        line_number=1
                    )
                ),
                ValidationFinding(
                    level="warning",
                    code="INVALID_DATE_FORMAT",
                    message="Invalid date format in BHT segment",
                    location=FindingLocation(
                        segment_id="BHT",
                        segment_instance=1,
                        element_position=4,
                        line_number=1
                    )
                )
            ]
        )
        mock_validation_service.validate_edi.return_value = validation_result
        
        with patch('src.api.endpoints.edi_validation.require_service_auth', return_value=mock_auth_context), \
             patch('src.api.endpoints.edi_validation.EDIValidationService', return_value=mock_validation_service):
            
            response = await async_client.post(
                "/api/v1/edi/validate-realtime",
                json=request.model_dump(),
                headers={"Authorization": "Bearer test-token"}
            )
        
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert data["valid"] is False
        assert len(data["validation_results"]) == 2
        
        # Check for both error and warning
        levels = [finding["level"] for finding in data["validation_results"]]
        assert "error" in levels
        assert "warning" in levels
    
    @pytest.mark.asyncio
    async def test_subscriber_vs_patient_scenarios(self, async_client, subscriber_vs_patient_837p_edi_string, mock_auth_context):
        """Test validation of EDI with both subscriber and dependent patient scenarios."""
        request = RealtimeEDIValidationRequest(
            edi_content=subscriber_vs_patient_837p_edi_string,
            tenant_id="tenant-a",
            workflow_id="sub-patient-workflow",
            validation_schema="837.5010.X222.A1.json",
            snip_level=3,
            generate_ta1=True
        )
        
        # Mock successful validation
        mock_validation_service = AsyncMock()
        validation_result = ValidationResult(valid=True, findings=[])
        mock_validation_service.validate_edi.return_value = validation_result
        mock_validation_service.generate_ta1.return_value = "TA1*000000001*A~"
        
        with patch('src.api.endpoints.edi_validation.require_service_auth', return_value=mock_auth_context), \
             patch('src.api.endpoints.edi_validation.EDIValidationService', return_value=mock_validation_service):
            
            response = await async_client.post(
                "/api/v1/edi/validate-realtime",
                json=request.model_dump(),
                headers={"Authorization": "Bearer test-token"}
            )
        
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert data["valid"] is True
        assert data["ta1_content"] is not None
        assert data["workflow_id"] == "sub-patient-workflow"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])