# FILE: backend/tests/api/test_edi.py

import pytest
from fastapi import status
from unittest.mock import patch, AsyncMock
import uuid
import time
from datetime import datetime

from src.api.schemas import (
    RealtimeEDIValidationRequest,
    BatchEDIValidationRequest,
    EdiParsingRequest,
    TA1GenerationRequest,
    ValidationFinding,
    FindingLocation,
    EdiSegment,
    EdiElement,
    TA1GenerationResponse
)
from src.services.edi_validation_service import ValidationResult


@pytest.mark.integration
class TestEDIValidation:
    """Test suite for the consolidated EDI validation endpoints."""

    @pytest.fixture
    def realtime_validation_request(self, valid_837p_edi_string):
        """Sample real-time EDI validation request."""
        return RealtimeEDIValidationRequest(
            edi_content=valid_837p_edi_string,
            tenant_id="tenant-a",
            workflow_id="test-workflow-001",
            validation_schema="837.5010.X222.A1.json"
        )

    @pytest.fixture
    def batch_validation_request(self, valid_837p_edi_string):
        """Sample batch EDI validation request."""
        return BatchEDIValidationRequest(
            edi_content=valid_837p_edi_string,
            tenant_id="tenant-a",
            workflow_id="test-workflow-001",
            validation_schema="837.5010.X222.A1.json",
            callback_url="https://example.com/webhook"
        )

    @pytest.mark.asyncio
    async def test_realtime_validation_successful(self, async_client, realtime_validation_request):
        """Test successful real-time EDI validation."""
        # Mock the validation service
        with patch('src.api.endpoints.edi.EDIValidationService') as mock_service:
            mock_validation_result = ValidationResult(
                valid=True,
                findings=[]
            )
            mock_service.return_value.validate_edi = AsyncMock(return_value=mock_validation_result)

            response = await async_client.post(
                "/api/v1/edi/validate-realtime",
                json=realtime_validation_request.model_dump()
            )

            assert response.status_code == status.HTTP_200_OK

    @pytest.mark.asyncio
    async def test_realtime_validation_with_errors(self, async_client, realtime_validation_request):
        """Test real-time EDI validation with validation errors."""
        with patch('src.api.endpoints.edi.EDIValidationService') as mock_service:
            mock_validation_result = ValidationResult(
                valid=False,
                findings=[ValidationFinding(
                    level="error",
                    code="EDI001",
                    message="Invalid segment",
                    location=FindingLocation(
                        segment_id="ISA",
                        segment_instance=1,
                        element_position=1,
                        line_number=1
                    )
                )]
            )
            mock_service.return_value.validate_edi = AsyncMock(return_value=mock_validation_result)

            response = await async_client.post(
                "/api/v1/edi/validate-realtime",
                json=realtime_validation_request.model_dump()
            )

            assert response.status_code == status.HTTP_200_OK

    @pytest.mark.asyncio
    async def test_batch_validation_job_creation(self, async_client, batch_validation_request):
        """Test batch EDI validation job creation."""
        with patch('src.api.endpoints.edi.BatchJobService') as mock_service:
            job_id = str(uuid.uuid4())
            mock_service.return_value.create_batch_job = AsyncMock(return_value=job_id)

            response = await async_client.post(
                "/api/v1/edi/validate-batch",
                json=batch_validation_request.model_dump()
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["job_id"] == job_id
            assert data["status"] == "QUEUED"

    @pytest.mark.asyncio
    async def test_batch_job_status_retrieval(self, async_client):
        """Test batch job status retrieval."""
        job_id = str(uuid.uuid4())
        
        with patch('src.api.endpoints.edi.BatchJobService') as mock_service:
            from src.api.schemas import BatchJobStatusResponse
            from datetime import datetime
            
            mock_status = BatchJobStatusResponse(
                job_id=job_id,
                workflow_id="test-workflow-001",
                tenant_id="tenant-a",
                status="COMPLETED",
                validation_schema="837.5010.X222.A1.json",
                created_at=datetime.utcnow()
            )
            mock_service.return_value.get_job_status = AsyncMock(return_value=mock_status)

            response = await async_client.get(f"/api/v1/edi/jobs/{job_id}/status")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["job_id"] == job_id
            assert data["status"] == "COMPLETED"

    @pytest.mark.asyncio
    async def test_tenant_access_control(self, async_client, realtime_validation_request):
        """Test tenant access control enforcement."""
        # Mock limited tenant access - we'll simulate this by overriding the auth context
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
                "/api/v1/edi/validate-realtime",
                json=realtime_validation_request.model_dump()
            )

            assert response.status_code == status.HTTP_403_FORBIDDEN
        finally:
            if original_override:
                app.dependency_overrides[require_service_auth] = original_override
            else:
                app.dependency_overrides.pop(require_service_auth, None)


@pytest.mark.integration
class TestEDIParsing:
    """Test suite for the EDI parsing endpoint."""

    @pytest.fixture
    def parsing_request(self, valid_837p_edi_string):
        """Sample EDI parsing request."""
        return EdiParsingRequest(
            edi_content=valid_837p_edi_string,
            tenant_id="tenant-a",
            schema_name="837.5010.X222.A1.json"
        )

    @pytest.mark.asyncio
    async def test_successful_parsing(self, async_client, parsing_request):
        """Test successful EDI parsing."""
        with patch('src.api.endpoints.edi.EdiParsingService') as mock_service:
            mock_segments = [
                EdiSegment(
                    id="ISA",
                    elements=[EdiElement(value="00"), EdiElement(value=""), EdiElement(value="00"), EdiElement(value="")],
                    line_number=1
                ),
                EdiSegment(
                    id="GS",
                    elements=[EdiElement(value="HC"), EdiElement(value="SENDER"), EdiElement(value="RECEIVER")],
                    line_number=2
                )
            ]
            mock_service.return_value.parse_edi = AsyncMock(return_value=mock_segments)

            response = await async_client.post(
                "/api/v1/edi/parse",
                json=parsing_request.model_dump()
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert len(data) == 2
            assert data[0]["id"] == "ISA"

    @pytest.mark.asyncio
    async def test_parsing_with_invalid_edi(self, async_client):
        """Test EDI parsing with invalid EDI content."""
        invalid_request = EdiParsingRequest(
            edi_content="INVALID EDI CONTENT",
            tenant_id="tenant-a",
            schema_name="837.5010.X222.A1.json"
        )

        with patch('src.api.endpoints.edi.EdiParsingService') as mock_service:
            mock_service.return_value.parse_edi = AsyncMock(side_effect=Exception("Invalid EDI format"))

            response = await async_client.post(
                "/api/v1/edi/parse",
                json=invalid_request.model_dump()
            )

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


@pytest.mark.integration
class TestTA1Generation:
    """Test suite for the TA1 generation endpoint."""

    @pytest.fixture
    def ta1_request(self, valid_837p_edi_string):
        """Sample TA1 generation request."""
        return TA1GenerationRequest(
            edi_content=valid_837p_edi_string,
            tenant_id="tenant-a",
            workflow_id="test-workflow-001",
            acknowledgment_code="A",
            error_code=None
        )

    @pytest.mark.asyncio
    async def test_generate_acceptance_ta1(self, async_client, ta1_request):
        """Test generating an acceptance TA1."""
        with patch('src.api.endpoints.edi.TA1GenerationService') as mock_service:
            mock_response = TA1GenerationResponse(
                ta1_content="ISA*00* *00* *ZZ*RECEIVER *ZZ*SENDER *240715*1200*^*00501*000000001*0*P*>~TA1*000000001*20240715*1200*A*000~IEA*1*000000001~",
                control_number="000000001",
                acknowledgment_code="A",
                workflow_id="test-workflow-001",
                generated_at=datetime.utcnow(),
                processing_time_ms=45
            )
            mock_service.return_value.generate_ta1 = AsyncMock(return_value=mock_response)

            response = await async_client.post(
                "/api/v1/edi/generate-ta1",
                json=ta1_request.model_dump()
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["acknowledgment_code"] == "A"
            assert "ta1_content" in data

    @pytest.mark.asyncio
    async def test_generate_rejection_ta1(self, async_client, valid_837p_edi_string):
        """Test generating a rejection TA1."""
        rejection_request = TA1GenerationRequest(
            edi_content=valid_837p_edi_string,
            tenant_id="tenant-a",
            workflow_id="test-workflow-001",
            acknowledgment_code="R",
            error_code="023"
        )

        with patch('src.api.endpoints.edi.TA1GenerationService') as mock_service:
            mock_response = TA1GenerationResponse(
                ta1_content="ISA*00* *00* *ZZ*RECEIVER *ZZ*SENDER *240715*1200*^*00501*000000001*0*P*>~TA1*000000001*20240715*1200*R*023~IEA*1*000000001~",
                control_number="000000001",
                acknowledgment_code="R",
                workflow_id="test-workflow-001",
                generated_at=datetime.utcnow(),
                processing_time_ms=50
            )
            mock_service.return_value.generate_ta1 = AsyncMock(return_value=mock_response)

            response = await async_client.post(
                "/api/v1/edi/generate-ta1",
                json=rejection_request.model_dump()
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["acknowledgment_code"] == "R"


@pytest.mark.integration 
class TestServiceAuthentication:
    """Test suite for service authentication requirements."""

    @pytest.mark.asyncio
    async def test_service_authentication_required(self, db_session, valid_837p_edi_string):
        """Test that service authentication is required for all endpoints."""
        from httpx import AsyncClient, ASGITransport
        from src.main import app
        
        # Create a client without authentication overrides
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            request_data = RealtimeEDIValidationRequest(
                edi_content=valid_837p_edi_string,
                tenant_id="tenant-a",
                workflow_id="test-workflow-001",
                validation_schema="837.5010.X222.A1.json"
            )

            # Test with empty Authorization header (should fail authentication)
            headers = {"Authorization": ""}
            response = await client.post(
                "/api/v1/edi/validate-realtime",
                json=request_data.model_dump(),
                headers=headers
            )

            assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_invalid_service_token_rejection(self, db_session, valid_837p_edi_string):
        """Test rejection of invalid service tokens."""
        from httpx import AsyncClient, ASGITransport
        from src.main import app
        
        # Create a client without authentication overrides
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            request_data = RealtimeEDIValidationRequest(
                edi_content=valid_837p_edi_string,
                tenant_id="tenant-a",
                workflow_id="test-workflow-001",
                validation_schema="837.5010.X222.A1.json"
            )

            headers = {"Authorization": "Bearer invalid_token"}
            response = await client.post(
                "/api/v1/edi/validate-realtime",
                json=request_data.model_dump(),
                headers=headers
            )

            assert response.status_code == status.HTTP_401_UNAUTHORIZED