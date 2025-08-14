import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from src.services.batch_job_service import BatchJobService, BatchJob
from src.api.schemas import BatchEDIValidationRequest, RealtimeEDIValidationResponse, ValidationFinding

pytestmark = pytest.mark.unit

@pytest.fixture
def batch_job_service():
    """Fixture to create a new BatchJobService for each test."""
    return BatchJobService()

@pytest.fixture
def sample_request():
    """Fixture for a sample BatchEDIValidationRequest."""
    return BatchEDIValidationRequest(
        tenant_id="test_tenant",
        workflow_id="test_workflow",
        validation_schema="837p",
        edi_content="test_edi_content",
        file_name="test.x12",
        callback_url="http://test.com/callback"
    )

@pytest.mark.asyncio
async def test_create_batch_job_success(batch_job_service: BatchJobService, sample_request: BatchEDIValidationRequest):
    """Test successful creation of a batch job."""
    try:
        job_id = await batch_job_service.create_batch_job(sample_request)

        # Assert a job ID was returned
        assert job_id is not None

        # Assert job is in storage
        assert job_id in batch_job_service._job_storage

        # Assert job is in the queue
        assert await batch_job_service._job_queue.get() == job_id

        # Assert job status is QUEUED
        job_data = batch_job_service._job_storage[job_id]
        assert job_data['job'].status == "QUEUED"

        # Assert that the worker is started
        assert batch_job_service._worker_task is not None
    finally:
        await batch_job_service.cancel_worker()

@pytest.mark.asyncio
async def test_get_job_status_found(batch_job_service: BatchJobService, sample_request: BatchEDIValidationRequest):
    """Test retrieving the status of an existing job."""
    try:
        job_id = await batch_job_service.create_batch_job(sample_request)
        status_response = await batch_job_service.get_job_status(job_id)

        assert status_response is not None
        assert status_response.job_id == job_id
        assert status_response.status == "QUEUED"
    finally:
        await batch_job_service.cancel_worker()

@pytest.mark.asyncio
async def test_get_job_status_not_found(batch_job_service: BatchJobService):
    """Test retrieving the status of a non-existent job."""
    try:
        status_response = await batch_job_service.get_job_status("non_existent_id")
        assert status_response is None
    finally:
        await batch_job_service.cancel_worker()

@pytest.mark.asyncio
async def test_get_job_status_missing_job_key(batch_job_service: BatchJobService):
    """Test get_job_status when job data is malformed (missing 'job' key)."""
    try:
        job_id = "malformed_job"
        batch_job_service._job_storage[job_id] = {'request': 'some_request'}
        status_response = await batch_job_service.get_job_status(job_id)
        assert status_response is None
    finally:
        await batch_job_service.cancel_worker()

@pytest.mark.asyncio
@patch('src.services.batch_job_service.EDIValidationService')
@patch('httpx.AsyncClient')
async def test_process_batch_job_success(
    mock_async_client, mock_edi_service, batch_job_service: BatchJobService, sample_request: BatchEDIValidationRequest
):
    """Test the successful processing of a batch job."""
    try:
        # Mock EDIValidationService
        mock_validation_result = MagicMock()
        mock_validation_result.valid = True
        mock_validation_result.findings = []
        mock_edi_service.return_value.validate_edi = AsyncMock(return_value=mock_validation_result)
        mock_edi_service.return_value.generate_ta1 = AsyncMock(return_value="TA1_CONTENT")
        batch_job_service.edi_service = mock_edi_service()

        # Mock httpx.AsyncClient
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_async_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)

        # Create and process job
        job_id = await batch_job_service.create_batch_job(sample_request)
        await batch_job_service._process_batch_job(job_id)

        # Assert job status is COMPLETED
        job = batch_job_service._job_storage[job_id]['job']
        assert job.status == "COMPLETED"
        assert job.results is not None
        assert job.results.valid is True
        assert job.callback_sent is True
    finally:
        await batch_job_service.cancel_worker()

@pytest.mark.asyncio
@patch('uuid.uuid4', side_effect=Exception("UUID Error"))
async def test_create_batch_job_uuid_exception(mock_uuid, batch_job_service: BatchJobService, sample_request: BatchEDIValidationRequest):
    """Test create_batch_job handles exceptions during job ID generation."""
    try:
        with pytest.raises(Exception) as excinfo:
            await batch_job_service.create_batch_job(sample_request)
        assert "UUID Error" in str(excinfo.value)
    finally:
        await batch_job_service.cancel_worker()

@pytest.mark.asyncio
async def test_process_batch_job_not_found(batch_job_service: BatchJobService):
    """Test _process_batch_job with a job_id that doesn't exist."""
    try:
        await batch_job_service._process_batch_job("non_existent_id")
        # No assertions needed, just ensuring no exceptions are raised for a non-existent job
    finally:
        await batch_job_service.cancel_worker()

@pytest.mark.asyncio
@patch('httpx.AsyncClient', side_effect=Exception("HTTP Client Error"))
async def test_send_webhook_callback_exception(mock_async_client, batch_job_service: BatchJobService, sample_request: BatchEDIValidationRequest):
    """Test _send_webhook_callback handles exceptions."""
    try:
        job = BatchJob(job_id="test_job", tenant_id="test_tenant", workflow_id="test_workflow", validation_schema="837p")
        await batch_job_service._send_webhook_callback(job, sample_request, None)
        assert "Webhook error: HTTP Client Error" in job.errors
    finally:
        await batch_job_service.cancel_worker()

@pytest.mark.asyncio
@patch('src.services.batch_job_service.EDIValidationService')
@patch('httpx.AsyncClient')
async def test_process_batch_job_validation_failure(
    mock_async_client, mock_edi_service, batch_job_service: BatchJobService, sample_request: BatchEDIValidationRequest
):
    """Test processing a job that fails EDI validation."""
    try:
        # Mock EDIValidationService to raise an exception
        mock_edi_service.return_value.validate_edi = AsyncMock(side_effect=Exception("Validation Error"))
        batch_job_service.edi_service = mock_edi_service()

        # Mock httpx.AsyncClient
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_async_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)

        # Create and process job
        job_id = await batch_job_service.create_batch_job(sample_request)
        await batch_job_service._process_batch_job(job_id)

        # Assert job status is FAILED
        job = batch_job_service._job_storage[job_id]['job']
        assert job.status == "FAILED"
        assert "Validation Error" in job.errors
        assert job.callback_sent is True
    finally:
        await batch_job_service.cancel_worker()

@pytest.mark.asyncio
@patch('src.services.batch_job_service.EDIValidationService')
@patch('httpx.AsyncClient')
async def test_process_batch_job_webhook_failure(
    mock_async_client, mock_edi_service, batch_job_service: BatchJobService, sample_request: BatchEDIValidationRequest
):
    """Test processing a job where the webhook callback fails."""
    try:
        # Mock EDIValidationService
        mock_validation_result = MagicMock()
        mock_validation_result.valid = True
        mock_validation_result.findings = []
        mock_edi_service.return_value.validate_edi = AsyncMock(return_value=mock_validation_result)
        mock_edi_service.return_value.generate_ta1 = AsyncMock(return_value=None)
        batch_job_service.edi_service = mock_edi_service()

        # Mock httpx.AsyncClient to simulate a failure
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_async_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)

        # Create and process job
        job_id = await batch_job_service.create_batch_job(sample_request)
        await batch_job_service._process_batch_job(job_id)

        # Assert job status is COMPLETED but callback failed
        job = batch_job_service._job_storage[job_id]['job']
        assert job.status == "COMPLETED"
        assert job.callback_sent is False
        assert "Webhook failed: HTTP 500" in job.errors
    finally:
        await batch_job_service.cancel_worker()

@pytest.mark.asyncio
@patch('src.services.batch_job_service.EDIValidationService')
@patch('httpx.AsyncClient')
async def test_process_batch_job_no_ta1_generation(
    mock_async_client, mock_edi_service, batch_job_service: BatchJobService, sample_request: BatchEDIValidationRequest
):
    """Test successful processing of a batch job without TA1 generation."""
    try:
        # Update request to not generate TA1
        sample_request.generate_ta1 = False

        # Mock EDIValidationService
        mock_validation_result = MagicMock()
        mock_validation_result.valid = True
        mock_validation_result.findings = []
        mock_edi_service.return_value.validate_edi = AsyncMock(return_value=mock_validation_result)
        mock_edi_service.return_value.generate_ta1 = AsyncMock(return_value=None)
        batch_job_service.edi_service = mock_edi_service()

        # Mock httpx.AsyncClient
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_async_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)

        # Create and process job
        job_id = await batch_job_service.create_batch_job(sample_request)
        await batch_job_service._process_batch_job(job_id)

        # Assert job status is COMPLETED
        job = batch_job_service._job_storage[job_id]['job']
        assert job.status == "COMPLETED"
        assert job.results is not None
        assert job.results.ta1_content is None
        assert job.callback_sent is True
    finally:
        await batch_job_service.cancel_worker()
