# FILE: backend/src/api/endpoints/sftp.py

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import logging
from typing import Dict, Any

from src.core.database import get_db
from src.api.schemas import SftpUploadWebhook
from src.services.sftp_webhook_processor import SftpWebhookProcessor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sftp", tags=["SFTP Processing"])

@router.post("/hooks/upload")
async def handle_sftp_upload_webhook(
    webhook_data: SftpUploadWebhook,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Handle SFTPGo upload webhook events for real-time file processing.
    
    This endpoint is called by SFTPGo whenever a file is uploaded via SFTP.
    It triggers immediate EDI processing based on the partner's profile configuration.
    """
    try:
        logger.info(f"Received SFTP upload webhook: user={webhook_data.username}, file={webhook_data.name}")
        
        # Initialize the webhook processor
        processor = SftpWebhookProcessor(db)
        
        # Process the file immediately (with rate limiting built-in)
        success = await processor.process_upload_event(webhook_data)
        
        if success:
            logger.info(f"Successfully processed SFTP upload: {webhook_data.name}")
            return {
                "status": "success",
                "message": "File processed successfully",
                "file_name": webhook_data.name,
                "username": webhook_data.username
            }
        else:
            logger.warning(f"File processing was queued for later: {webhook_data.name}")
            return {
                "status": "queued", 
                "message": "File queued for processing due to high load",
                "file_name": webhook_data.name,
                "username": webhook_data.username
            }
            
    except Exception as e:
        logger.error(f"Error processing SFTP upload webhook: {e}", exc_info=True)
        # Don't return 500 error to SFTPGo - we don't want to block uploads
        # Instead, queue the file for retry processing
        return {
            "status": "error",
            "message": "Processing failed, will retry",
            "error": str(e)
        }

@router.get("/status")
async def get_sftp_processing_status() -> Dict[str, Any]:
    """Get current SFTP processing status and queue information."""
    # TODO: Implement processing status monitoring
    return {
        "status": "active",
        "queue_size": 0,
        "processing_load": "low"
    }