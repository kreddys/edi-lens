"""
SFTP Management API Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List

from src.core.database import get_db
from src.core.auth import get_current_user, require_permission
from src.models.sftp_configuration import SftpConfiguration
from src.models.file_processing_log import FileProcessingLog
from src.models.processing_schedule import ProcessingSchedule
from src.services.sftp_scheduler import get_scheduler
from src.api.schemas import MessageResponse
from pydantic import BaseModel

router = APIRouter()


class SftpConfigurationResponse(BaseModel):
    id: int
    tenant_id: str
    partner_id: int
    sftp_enabled: bool
    sftp_username: str
    authentication_type: str
    inbound_directory: str
    outbound_directory: str
    archive_directory: str | None
    file_name_patterns: str | None
    poll_schedule_id: int | None
    poll_enabled: bool
    response_filename_template: str | None
    response_timeout_minutes: int
    max_file_size_bytes: int
    created_at: str
    updated_at: str | None

    class Config:
        from_attributes = True


class FileProcessingLogResponse(BaseModel):
    id: str
    tenant_id: str
    partner_id: int
    source_filename: str
    source_directory: str
    source_file_size: int | None
    status: str
    processing_started_at: str | None
    processing_completed_at: str | None
    response_filename: str | None
    response_delivered_at: str | None
    error_message: str | None
    retry_count: int
    created_at: str

    class Config:
        from_attributes = True


class ProcessingScheduleResponse(BaseModel):
    id: int
    name: str
    description: str | None
    cron_expression: str
    is_active: bool
    created_at: str

    class Config:
        from_attributes = True


class SchedulerStatusResponse(BaseModel):
    running: bool
    check_interval: int
    active_processing_tasks: int
    total_tasks: int


@router.get("/configurations", response_model=List[SftpConfigurationResponse])
async def list_sftp_configurations(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("sftp:read"))
):
    """List all SFTP configurations for the current tenant."""
    tenant_id = current_user["tenant_id"]
    
    result = await db.execute(
        select(SftpConfiguration).where(SftpConfiguration.tenant_id == tenant_id)
    )
    configurations = result.scalars().all()
    
    return [SftpConfigurationResponse.model_validate(config) for config in configurations]


@router.get("/configurations/{partner_id}", response_model=SftpConfigurationResponse)
async def get_sftp_configuration(
    partner_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("sftp:read"))
):
    """Get SFTP configuration for a specific partner."""
    tenant_id = current_user["tenant_id"]
    
    result = await db.execute(
        select(SftpConfiguration).where(
            and_(
                SftpConfiguration.tenant_id == tenant_id,
                SftpConfiguration.partner_id == partner_id
            )
        )
    )
    configuration = result.scalar_one_or_none()
    
    if not configuration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SFTP configuration not found"
        )
    
    return SftpConfigurationResponse.model_validate(configuration)


@router.get("/processing-logs", response_model=List[FileProcessingLogResponse])
async def list_processing_logs(
    partner_id: int | None = None,
    status: str | None = None,
    limit: int = 100,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("sftp:read"))
):
    """List file processing logs with optional filters."""
    tenant_id = current_user["tenant_id"]
    
    query = select(FileProcessingLog).where(FileProcessingLog.tenant_id == tenant_id)
    
    if partner_id:
        query = query.where(FileProcessingLog.partner_id == partner_id)
    
    if status:
        query = query.where(FileProcessingLog.status == status)
    
    query = query.order_by(FileProcessingLog.created_at.desc()).limit(limit)
    
    result = await db.execute(query)
    logs = result.scalars().all()
    
    return [FileProcessingLogResponse.model_validate(log) for log in logs]


@router.get("/schedules", response_model=List[ProcessingScheduleResponse])
async def list_processing_schedules(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("sftp:read"))
):
    """List all available processing schedules."""
    result = await db.execute(select(ProcessingSchedule))
    schedules = result.scalars().all()
    
    return [ProcessingScheduleResponse.model_validate(schedule) for schedule in schedules]


@router.post("/process/{partner_id}", response_model=MessageResponse)
async def process_partner_files(
    partner_id: int,
    current_user: dict = Depends(get_current_user),
    _: None = Depends(require_permission("sftp:process"))
):
    """Manually trigger file processing for a specific partner."""
    scheduler = await get_scheduler()
    
    success = await scheduler.process_partner_manually(partner_id)
    
    if success:
        return MessageResponse(message=f"File processing triggered for partner {partner_id}")
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Partner not found or SFTP not configured"
        )


@router.get("/scheduler/status", response_model=SchedulerStatusResponse)
async def get_scheduler_status(
    current_user: dict = Depends(get_current_user),
    _: None = Depends(require_permission("sftp:read"))
):
    """Get current status of the SFTP scheduler."""
    scheduler = await get_scheduler()
    status_info = await scheduler.get_processing_status()
    
    return SchedulerStatusResponse(**status_info)


@router.post("/scheduler/start", response_model=MessageResponse)
async def start_scheduler(
    current_user: dict = Depends(get_current_user),
    _: None = Depends(require_permission("sftp:admin"))
):
    """Start the SFTP scheduler service."""
    scheduler = await get_scheduler()
    await scheduler.start()
    
    return MessageResponse(message="SFTP scheduler started")


@router.post("/scheduler/stop", response_model=MessageResponse)
async def stop_scheduler(
    current_user: dict = Depends(get_current_user),
    _: None = Depends(require_permission("sftp:admin"))
):
    """Stop the SFTP scheduler service."""
    scheduler = await get_scheduler()
    await scheduler.stop()
    
    return MessageResponse(message="SFTP scheduler stopped")