# FILE: backend/tests/api/test_edi.py

import pytest
from fastapi import status
from unittest.mock import patch, AsyncMock
import uuid
import time

from src.api.schemas import (
    RealtimeEDIValidationRequest,
    BatchEDIValidationRequest,
    EdiParsingRequest,
    TA1GenerationRequest
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
            schema_name="837.5010.X222.A1.json"
        )

    @pytest.fixture
    def batch_validation_request(self, valid_837p_edi_string):
        """Sample batch EDI validation request."""
        return BatchEDIValidationRequest(
            edi_content=valid_837p_edi_string,
            tenant_id="tenant-a",
            schema_name="837.5010.X222.A1.json",
            callback_url="https://example.com/webhook"
        )

    async def test_realtime_validation_successful(self, async_client, realtime_validation_request, mock_service_context):
        """Test successful real-time EDI validation."""
        # Mock the validation service
        with patch('src.api.endpoints.edi.EDIValidationService') as mock_service:
            mock_validation_result = ValidationResult(
                is_valid=True,
                errors=[],
                segments=[],
                processing_time_ms=150,
                schema_used="837.5010.X222.A1.json"
            )
            mock_service.return_value.validate_edi_realtime = AsyncMock(return_value=mock_validation_result)

            response = await async_client.post(
                "/api/v1/edi/validate-realtime",
                json=realtime_validation_request.model_dump()
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["is_valid"] is True
            assert "processing_time_ms" in data

    async def test_realtime_validation_with_errors(self, async_client, realtime_validation_request, mock_service_context):
        """Test real-time EDI validation with validation errors."""
        with patch('src.api.endpoints.edi.EDIValidationService') as mock_service:
            mock_validation_result = ValidationResult(
                is_valid=False,
                errors=[{"code": "EDI001", "message": "Invalid segment", "severity": "error"}],
                segments=[],
                processing_time_ms=120,
                schema_used="837.5010.X222.A1.json"
            )
            mock_service.return_value.validate_edi_realtime = AsyncMock(return_value=mock_validation_result)

            response = await async_client.post(
                "/api/v1/edi/validate-realtime",
                json=realtime_validation_request.model_dump()
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["is_valid"] is False
            assert len(data["errors"]) > 0

    async def test_batch_validation_job_creation(self, async_client, batch_validation_request, mock_service_context):
        """Test batch EDI validation job creation."""
        with patch('src.api.endpoints.edi.BatchJobService') as mock_service:
            job_id = str(uuid.uuid4())
            mock_service.return_value.create_validation_job = AsyncMock(return_value=job_id)

            response = await async_client.post(
                "/api/v1/edi/validate-batch",
                json=batch_validation_request.model_dump()
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["job_id"] == job_id
            assert data["status"] == "QUEUED"

    async def test_batch_job_status_retrieval(self, async_client, mock_service_context):
        """Test batch job status retrieval."""
        job_id = str(uuid.uuid4())
        
        with patch('src.api.endpoints.edi.BatchJobService') as mock_service:
            mock_status = {
                "job_id": job_id,
                "tenant_id": "tenant-a",
                "status": "COMPLETED",
                "progress": 100
            }
            mock_service.return_value.get_job_status = AsyncMock(return_value=type('obj', (object,), mock_status)())

            response = await async_client.get(f"/api/v1/edi/jobs/{job_id}/status")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["job_id"] == job_id
            assert data["status"] == "COMPLETED"

    async def test_tenant_access_control(self, async_client, realtime_validation_request, mock_service_context_limited):
        """Test tenant access control enforcement."""
        # Mock limited tenant access
        with patch('src.api.endpoints.edi.EDIValidationService'):
            response = await async_client.post(
                "/api/v1/edi/validate-realtime",
                json=realtime_validation_request.model_dump()
            )

            assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.integration
class TestEDIParsing:
    """Test suite for the EDI parsing endpoint."""

    @pytest.fixture
    def parsing_request(self, valid_837p_edi_string):
        """Sample EDI parsing request."""
        return EdiParsingRequest(
            edi_content=valid_837p_edi_string,
            tenant_id="tenant-a",
            schema_name="837.5010.X222.A1.json",
        )

    async def test_successful_parsing(self, async_client, parsing_request, mock_service_context):
        """Test successful EDI parsing."""
        with patch('src.api.endpoints.edi.EdiParsingService') as mock_service:
            mock_segments = [
                {"tag": "ISA", "elements": ["00", "", "00", ""]},
                {"tag": "GS", "elements": ["HC", "SENDER", "RECEIVER"]}
            ]
            mock_service.return_value.parse_edi = AsyncMock(return_value=mock_segments)

            response = await async_client.post(
                "/api/v1/edi/parse",
                json=parsing_request.model_dump()
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert len(data) == 2
            assert data[0]["tag"] == "ISA"

    async def test_parsing_with_invalid_edi(self, async_client, mock_service_context):
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
            acknowledgment_code="A",
            error_code=None
        )

    async def test_generate_acceptance_ta1(self, async_client, ta1_request, mock_service_context):
        """Test generating an acceptance TA1."""
        with patch('src.api.endpoints.edi.TA1GenerationService') as mock_service:
            mock_response = {
                "ta1_content": "ISA*00* *00* *ZZ*RECEIVER *ZZ*SENDER *240715*1200*^*00501*000000001*0*P*>~TA1*000000001*20240715*1200*A*000~IEA*1*000000001~",
                "control_number": "000000001",
                "acknowledgment_code": "A",
                "generated_at": "2024-07-15T12:00:00Z",
                "processing_time_ms": 45
            }
            mock_service.return_value.generate_ta1 = AsyncMock(return_value=type('obj', (object,), mock_response)())

            response = await async_client.post(
                "/api/v1/edi/generate-ta1",
                json=ta1_request.model_dump()
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["acknowledgment_code"] == "A"
            assert "ta1_content" in data

    async def test_generate_rejection_ta1(self, async_client, valid_837p_edi_string, mock_service_context):
        """Test generating a rejection TA1."""
        rejection_request = TA1GenerationRequest(
            edi_content=valid_837p_edi_string,
            tenant_id="tenant-a",
            acknowledgment_code="R",
            error_code="023"
        )

        with patch('src.api.endpoints.edi.TA1GenerationService') as mock_service:
            mock_response = {
                "ta1_content": "ISA*00* *00* *ZZ*RECEIVER *ZZ*SENDER *240715*1200*^*00501*000000001*0*P*>~TA1*000000001*20240715*1200*R*023~IEA*1*000000001~",
                "control_number": "000000001",
                "acknowledgment_code": "R",
                "error_code": "023",
                "generated_at": "2024-07-15T12:00:00Z",
                "processing_time_ms": 50
            }
            mock_service.return_value.generate_ta1 = AsyncMock(return_value=type('obj', (object,), mock_response)())

            response = await async_client.post(
                "/api/v1/edi/generate-ta1",
                json=rejection_request.model_dump()
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["acknowledgment_code"] == "R"
            assert data["error_code"] == "023"


@pytest.mark.integration 
class TestServiceAuthentication:
    """Test suite for service authentication requirements."""

    async def test_service_authentication_required(self, async_client, valid_837p_edi_string):
        """Test that service authentication is required for all endpoints."""
        request_data = RealtimeEDIValidationRequest(
            edi_content=valid_837p_edi_string,
            tenant_id="tenant-a",
            schema_name="837.5010.X222.A1.json"
        )

        # Test without authentication
        response = await async_client.post(
            "/api/v1/edi/validate-realtime",
            json=request_data.model_dump()
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_invalid_service_token_rejection(self, async_client, valid_837p_edi_string):
        """Test rejection of invalid service tokens."""
        request_data = RealtimeEDIValidationRequest(
            edi_content=valid_837p_edi_string,
            tenant_id="tenant-a",
            schema_name="837.5010.X222.A1.json"
        )

        headers = {"Authorization": "Bearer invalid_token"}
        response = await async_client.post(
            "/api/v1/edi/validate-realtime",
            json=request_data.model_dump(),
            headers=headers
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED