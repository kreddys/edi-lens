# FILE: backend/src/services/batch_job_service.py

import uuid
import json
import asyncio
import httpx
from typing import Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
import logging

from src.api.schemas import (
    BatchEDIValidationRequest,
    BatchJobStatusResponse,
    BatchJobCompletionWebhook,
    RealtimeEDIValidationResponse
)
from src.services.edi_validation_service import EDIValidationService
from src.core.database import get_db

logger = logging.getLogger(__name__)

class BatchJob:
    """Data class for batch job information."""
    def __init__(
        self,
        job_id: str,
        tenant_id: str,
        workflow_id: str,
        validation_schema: str,
        status: str = "QUEUED",
        file_name: Optional[str] = None,
        created_at: Optional[datetime] = None,
        **kwargs
    ):
        self.job_id = job_id
        self.tenant_id = tenant_id
        self.workflow_id = workflow_id
        self.validation_schema = validation_schema
        self.status = status
        self.file_name = file_name
        self.created_at = created_at or datetime.utcnow()
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.processing_time_ms: Optional[int] = None
        self.results: Optional[RealtimeEDIValidationResponse] = None
        self.callback_sent: bool = False
        self.callback_sent_at: Optional[datetime] = None
        self.errors: list = []

class BatchJobService:
    """Service for managing batch EDI processing jobs."""
    
    def __init__(self):
        self.edi_service = EDIValidationService()
        self._job_storage = {}  # In-memory storage for demo - use Redis in production
        self._job_queue = asyncio.Queue()
        self._worker_running = False
    
    async def create_batch_job(self, request: BatchEDIValidationRequest) -> str:
        """
        Create a new batch processing job and queue it for processing.
        
        Args:
            request: Batch validation request
            
        Returns:
            Job ID for tracking
        """
        try:
            job_id = str(uuid.uuid4())
            
            # Create job record
            job = BatchJob(
                job_id=job_id,
                tenant_id=request.tenant_id,
                workflow_id=request.workflow_id,
                validation_schema=request.validation_schema,
                file_name=request.file_name,
                status="QUEUED"
            )
            
            # Store job information
            self._job_storage[job_id] = {
                'job': job,
                'request': request
            }
            
            # Queue for processing
            await self._job_queue.put(job_id)
            
            # Start worker if not running
            if not self._worker_running:
                asyncio.create_task(self._process_job_queue())
            
            logger.info(f"Created batch job {job_id} for workflow {request.workflow_id}")
            return job_id
            
        except Exception as e:
            logger.error(f"Failed to create batch job: {e}", exc_info=True)
            raise
    
    async def get_job_status(self, job_id: str) -> Optional[BatchJobStatusResponse]:
        """
        Get current status of a batch job.
        
        Args:
            job_id: Job identifier
            
        Returns:
            Job status information or None if not found
        """
        try:
            job_data = self._job_storage.get(job_id)
            if not job_data:
                return None
            
            job = job_data['job']
            
            return BatchJobStatusResponse(
                job_id=job.job_id,
                workflow_id=job.workflow_id,
                tenant_id=job.tenant_id,
                status=job.status,
                file_name=job.file_name,
                validation_schema=job.validation_schema,
                created_at=job.created_at,
                started_at=job.started_at,
                completed_at=job.completed_at,
                processing_time_ms=job.processing_time_ms,
                results=job.results,
                callback_sent=job.callback_sent,
                callback_sent_at=job.callback_sent_at,
                errors=job.errors
            )
            
        except Exception as e:
            logger.error(f"Failed to get job status for {job_id}: {e}", exc_info=True)
            return None
    
    async def _process_job_queue(self):
        """Background worker to process queued batch jobs."""
        self._worker_running = True
        logger.info("Batch job worker started")
        
        try:
            while True:
                try:
                    # Get next job from queue
                    job_id = await asyncio.wait_for(self._job_queue.get(), timeout=5.0)
                    await self._process_batch_job(job_id)
                    
                except asyncio.TimeoutError:
                    # Continue checking for jobs
                    continue
                except Exception as e:
                    logger.error(f"Error in job queue worker: {e}", exc_info=True)
                    await asyncio.sleep(1)  # Brief pause before retrying
                    
        except Exception as e:
            logger.error(f"Job queue worker crashed: {e}", exc_info=True)
        finally:
            self._worker_running = False
            logger.info("Batch job worker stopped")
    
    async def _process_batch_job(self, job_id: str):
        """
        Process a single batch job.
        
        Args:
            job_id: Job identifier to process
        """
        try:
            job_data = self._job_storage.get(job_id)
            if not job_data:
                logger.error(f"Job {job_id} not found in storage")
                return
            
            job = job_data['job']
            request = job_data['request']
            
            logger.info(f"Processing batch job {job_id}")
            
            # Update job status to processing
            job.status = "PROCESSING"
            job.started_at = datetime.utcnow()
            
            start_time = datetime.utcnow()
            
            try:
                # Perform EDI validation
                validation_result = await self.edi_service.validate_edi(
                    edi_content=request.edi_content,
                    schema_name=request.validation_schema,
                    snip_level=request.snip_level
                )
                
                # Generate TA1 if requested
                ta1_content = None
                if request.generate_ta1:
                    ta1_content = await self.edi_service.generate_ta1(
                        edi_content=request.edi_content,
                        validation_errors=validation_result.findings
                    )
                
                # Calculate processing time
                end_time = datetime.utcnow()
                processing_time_ms = int((end_time - start_time).total_seconds() * 1000)
                
                # Create validation response
                results = RealtimeEDIValidationResponse(
                    valid=validation_result.valid,
                    validation_results=validation_result.findings,
                    processing_time_ms=processing_time_ms,
                    schema_used=request.validation_schema,
                    snip_level_used=request.snip_level,
                    ta1_content=ta1_content,
                    workflow_id=request.workflow_id,
                    processed_at=end_time
                )
                
                # Update job with results
                job.status = "COMPLETED"
                job.completed_at = end_time
                job.processing_time_ms = processing_time_ms
                job.results = results
                
                logger.info(f"Batch job {job_id} completed successfully")
                
                # Send webhook callback
                await self._send_webhook_callback(job, request, results)
                
            except Exception as e:
                # Handle processing errors
                job.status = "FAILED"
                job.completed_at = datetime.utcnow()
                job.errors.append(str(e))
                
                logger.error(f"Batch job {job_id} failed: {e}", exc_info=True)
                
                # Send failure webhook
                await self._send_webhook_callback(job, request, None, str(e))
                
        except Exception as e:
            logger.error(f"Critical error processing batch job {job_id}: {e}", exc_info=True)
    
    async def _send_webhook_callback(
        self,
        job: BatchJob,
        request: BatchEDIValidationRequest,
        results: Optional[RealtimeEDIValidationResponse],
        error_message: Optional[str] = None
    ):
        """
        Send webhook callback for job completion.
        
        Args:
            job: Job information
            request: Original request
            results: Validation results if successful
            error_message: Error message if failed
        """
        try:
            # Create webhook payload
            webhook_payload = BatchJobCompletionWebhook(
                job_id=job.job_id,
                status=job.status,
                workflow_id=job.workflow_id,
                file_name=job.file_name,
                results=results,
                error_message=error_message
            )
            
            # Send webhook
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    request.callback_url,
                    json=webhook_payload.model_dump(),
                    headers={"Content-Type": "application/json"},
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    job.callback_sent = True
                    job.callback_sent_at = datetime.utcnow()
                    logger.info(f"Webhook callback sent successfully for job {job.job_id}")
                else:
                    logger.error(
                        f"Webhook callback failed for job {job.job_id}: "
                        f"HTTP {response.status_code} - {response.text}"
                    )
                    job.errors.append(f"Webhook failed: HTTP {response.status_code}")
                    
        except Exception as e:
            logger.error(f"Failed to send webhook for job {job.job_id}: {e}", exc_info=True)
            job.errors.append(f"Webhook error: {str(e)}")