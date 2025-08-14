import pytest
from fastapi import status, HTTPException
from unittest.mock import patch, AsyncMock, MagicMock
import uuid
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
    TA1GenerationResponse,
    BatchJobStatusResponse,
)
from src.services.edi_validation_service import ValidationResult
from src.core.auth import ServiceContext
from src.api.endpoints import edi

pytestmark = pytest.mark.unit

@pytest.fixture
def mock_auth():
    """Fixture for a mocked AuthContext."""
    auth_context = ServiceContext("test-service", ["tenant-a"])
    return auth_context

@pytest.mark.asyncio
async def test_validate_realtime_edi_success(mock_auth):
    """Test successful real-time EDI validation."""
    with patch('src.api.endpoints.edi.EDIValidationService') as mock_service:
        mock_validation_result = ValidationResult(valid=True, findings=[])
        mock_service.return_value.validate_edi = AsyncMock(return_value=mock_validation_result)

        request = RealtimeEDIValidationRequest(
            edi_content="test", tenant_id="tenant-a", workflow_id="test", validation_schema="test"
        )
        response = await edi.validate_realtime_edi(request, mock_auth)
        assert response.valid

@pytest.mark.asyncio
async def test_validate_realtime_edi_tenant_denied(mock_auth):
    """Test real-time EDI validation with tenant access denied."""
    request = RealtimeEDIValidationRequest(
        edi_content="test", tenant_id="tenant-b", workflow_id="test", validation_schema="test"
    )
    with pytest.raises(HTTPException) as exc_info:
        await edi.validate_realtime_edi(request, mock_auth)
    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.asyncio
async def test_validate_batch_edi_success(mock_auth):
    """Test successful batch EDI validation job creation."""
    with patch('src.api.endpoints.edi.BatchJobService') as mock_service:
        job_id = str(uuid.uuid4())
        mock_service.return_value.create_batch_job = AsyncMock(return_value=job_id)

        request = BatchEDIValidationRequest(
            edi_content="test", tenant_id="tenant-a", workflow_id="test", validation_schema="test", callback_url="http://test.com"
        )
        response = await edi.validate_batch_edi(request, MagicMock(), mock_auth)
        assert response.job_id == job_id
        assert response.status == "QUEUED"

@pytest.mark.asyncio
async def test_get_batch_job_status_success(mock_auth):
    """Test successful retrieval of batch job status."""
    with patch('src.api.endpoints.edi.BatchJobService') as mock_service:
        job_id = str(uuid.uuid4())
        mock_status = BatchJobStatusResponse(
            job_id=job_id,
            workflow_id="test-workflow-001",
            tenant_id="tenant-a",
            status="COMPLETED",
            validation_schema="837.5010.X222.A1.json",
            created_at=datetime.utcnow()
        )
        mock_service.return_value.get_job_status = AsyncMock(return_value=mock_status)

        response = await edi.get_batch_job_status(job_id, mock_auth)
        assert response.job_id == job_id
        assert response.status == "COMPLETED"

@pytest.mark.asyncio
async def test_parse_edi_success(mock_auth):
    """Test successful EDI parsing."""
    with patch('src.api.endpoints.edi.EdiParsingService') as mock_service:
        mock_segments = [EdiSegment(id="ISA", elements=[], line_number=1)]
        mock_service.return_value.parse_edi = AsyncMock(return_value=mock_segments)

        request = EdiParsingRequest(
            edi_content="test", tenant_id="tenant-a", schema_name="test"
        )
        response = await edi.parse_edi(request, mock_auth)
        assert len(response) == 1
        assert response[0].id == "ISA"

@pytest.mark.asyncio
async def test_generate_ta1_success(mock_auth):
    """Test successful TA1 generation."""
    with patch('src.api.endpoints.edi.TA1GenerationService') as mock_service:
        mock_ta1_response = TA1GenerationResponse(
            ta1_content="test_ta1", control_number="123", acknowledgment_code="A", workflow_id="test", generated_at=datetime.utcnow(), processing_time_ms=10
        )
        mock_service.return_value.generate_ta1 = AsyncMock(return_value=mock_ta1_response)

        request = TA1GenerationRequest(
            edi_content="test", tenant_id="tenant-a", workflow_id="test", acknowledgment_code="A"
        )
        response = await edi.generate_ta1(request, mock_auth)
        assert response.ta1_content == "test_ta1"

@pytest.mark.asyncio
async def test_get_batch_job_status_not_found(mock_auth):
    """Test getting status for a non-existent batch job."""
    job_id = str(uuid.uuid4())
    with patch('src.api.endpoints.edi.BatchJobService') as mock_service:
        mock_service.return_value.get_job_status = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as exc_info:
            await edi.get_batch_job_status(job_id, mock_auth)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

@pytest.mark.asyncio
async def test_validate_batch_edi_tenant_denied(mock_auth):
    """Test batch EDI validation with tenant access denied."""
    request = BatchEDIValidationRequest(
        edi_content="test", tenant_id="tenant-b", workflow_id="test", validation_schema="test", callback_url="http://test.com"
    )
    with pytest.raises(HTTPException) as exc_info:
        await edi.validate_batch_edi(request, MagicMock(), mock_auth)
    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.asyncio
async def test_get_batch_job_status_tenant_denied(mock_auth):
    """Test getting batch job status with tenant access denied."""
    job_id = str(uuid.uuid4())
    mock_status = BatchJobStatusResponse(
        job_id=job_id,
        workflow_id="test-workflow-001",
        tenant_id="tenant-b", # Belongs to a different tenant
        status="COMPLETED",
        validation_schema="837.5010.X222.A1.json",
        created_at=datetime.utcnow()
    )
    with patch('src.api.endpoints.edi.BatchJobService') as mock_service:
        mock_service.return_value.get_job_status = AsyncMock(return_value=mock_status)

        with pytest.raises(HTTPException) as exc_info:
            await edi.get_batch_job_status(job_id, mock_auth)

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.asyncio
async def test_parse_edi_tenant_denied(mock_auth):
    """Test EDI parsing with tenant access denied."""
    request = EdiParsingRequest(
        edi_content="test", tenant_id="tenant-b", schema_name="test"
    )
    with pytest.raises(HTTPException) as exc_info:
        await edi.parse_edi(request, mock_auth)
    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.asyncio
async def test_generate_ta1_tenant_denied(mock_auth):
    """Test TA1 generation with tenant access denied."""
    request = TA1GenerationRequest(
        edi_content="test", tenant_id="tenant-b", workflow_id="test", acknowledgment_code="A"
    )
    with pytest.raises(HTTPException) as exc_info:
        await edi.generate_ta1(request, mock_auth)
    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
