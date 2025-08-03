"""
SFTP Management API Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List

from src.core.database import get_db
from src.core.auth import get_current_user, require_permission, AuthContext
from src.models.sftp_configuration import SftpConfiguration
from src.models.file_processing_log import FileProcessingLog
from src.models.processing_schedule import ProcessingSchedule
from src.services.sftp_scheduler import get_scheduler
from src.api.schemas import MessageResponse
from pydantic import BaseModel, Field
from pathlib import Path
from datetime import datetime
from src.models.trading_partner import TradingPartner

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
    created_at: datetime
    updated_at: datetime | None
    
    # Multi-tenant helper fields
    tenant_partner_username: str | None = None
    partner_directory_path: str | None = None
    inbound_directory_path: str | None = None
    outbound_directory_path: str | None = None

    class Config:
        from_attributes = True


class CreateSftpConfigurationRequest(BaseModel):
    partner_id: int
    sftp_enabled: bool = True
    sftp_username: str = Field(..., min_length=3, max_length=50)
    authentication_type: str = Field(default="PASSWORD", pattern="^(PASSWORD|SSH_KEY|BOTH)$")
    password: str | None = Field(None, min_length=8)
    ssh_public_key: str | None = None
    file_name_patterns: str | None = Field(default='["*.edi", "*.x12"]')
    poll_schedule_id: int | None = None
    poll_enabled: bool = True
    response_filename_template: str | None = None
    response_timeout_minutes: int = Field(default=5, ge=1, le=60)
    max_file_size_bytes: int = Field(default=52428800, ge=1024, le=104857600)  # 1KB to 100MB


class UpdateSftpConfigurationRequest(BaseModel):
    sftp_enabled: bool | None = None
    authentication_type: str | None = Field(None, pattern="^(PASSWORD|SSH_KEY|BOTH)$")
    password: str | None = Field(None, min_length=8)
    ssh_public_key: str | None = None
    file_name_patterns: str | None = None
    poll_schedule_id: int | None = None
    poll_enabled: bool | None = None
    response_filename_template: str | None = None
    response_timeout_minutes: int | None = Field(None, ge=1, le=60)
    max_file_size_bytes: int | None = Field(None, ge=1024, le=104857600)


class MultiTenantDirectoryInfo(BaseModel):
    tenant_id: str
    partner_name: str
    tenant_partner_username: str
    partner_directory_path: str
    inbound_directory_path: str
    outbound_directory_path: str
    directory_exists: bool
    user_exists: bool


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
    auth: AuthContext = Depends(require_permission("sftp:read")),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("sftp:read"))
):
    """List all SFTP configurations for the current tenant."""
    tenant_id = auth.tenant_id
    
    result = await db.execute(
        select(SftpConfiguration).where(SftpConfiguration.tenant_id == tenant_id)
    )
    configurations = result.scalars().all()
    
    return [SftpConfigurationResponse.model_validate(config) for config in configurations]


@router.get("/configurations/{partner_id}", response_model=SftpConfigurationResponse)
async def get_sftp_configuration(
    partner_id: int,
    auth: AuthContext = Depends(require_permission("sftp:read")),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("sftp:read"))
):
    """Get SFTP configuration for a specific partner."""
    tenant_id = auth.tenant_id
    
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
    auth: AuthContext = Depends(require_permission("sftp:read")),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("sftp:read"))
):
    """List file processing logs with optional filters."""
    tenant_id = auth.tenant_id
    
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
    auth: AuthContext = Depends(require_permission("sftp:read")),
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
    auth: AuthContext = Depends(require_permission("sftp:write")),
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
    auth: AuthContext = Depends(require_permission("sftp:read")),
    _: None = Depends(require_permission("sftp:read"))
):
    """Get current status of the SFTP scheduler."""
    scheduler = await get_scheduler()
    status_info = await scheduler.get_processing_status()
    
    return SchedulerStatusResponse(**status_info)


@router.post("/scheduler/start", response_model=MessageResponse)
async def start_scheduler(
    auth: AuthContext = Depends(require_permission("sftp:write")),
    _: None = Depends(require_permission("sftp:admin"))
):
    """Start the SFTP scheduler service."""
    scheduler = await get_scheduler()
    await scheduler.start()
    
    return MessageResponse(message="SFTP scheduler started")


@router.post("/scheduler/stop", response_model=MessageResponse)
async def stop_scheduler(
    auth: AuthContext = Depends(require_permission("sftp:write")),
    _: None = Depends(require_permission("sftp:admin"))
):
    """Stop the SFTP scheduler service."""
    scheduler = await get_scheduler()
    await scheduler.stop()
    
    return MessageResponse(message="SFTP scheduler stopped")


@router.post("/configurations", response_model=SftpConfigurationResponse)
async def create_sftp_configuration(
    request: CreateSftpConfigurationRequest,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(require_permission("sftp:write"))
):
    """Create a new SFTP configuration for a partner."""
    tenant_id = auth.tenant_id
    
    # Verify partner exists and belongs to current tenant
    partner_result = await db.execute(
        select(TradingPartner).where(
            and_(
                TradingPartner.tenant_id == tenant_id,
                TradingPartner.id == request.partner_id
            )
        )
    )
    partner = partner_result.scalar_one_or_none()
    if not partner:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Partner not found"
        )
    
    # Check if SFTP configuration already exists for this partner
    existing_result = await db.execute(
        select(SftpConfiguration).where(
            and_(
                SftpConfiguration.tenant_id == tenant_id,
                SftpConfiguration.partner_id == request.partner_id
            )
        )
    )
    if existing_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="SFTP configuration already exists for this partner"
        )
    
    # Create SFTP configuration
    config = SftpConfiguration(
        tenant_id=tenant_id,
        partner_id=request.partner_id,
        sftp_enabled=request.sftp_enabled,
        sftp_username=request.sftp_username,
        authentication_type=request.authentication_type,
        password_hash=request.password,  # TODO: Hash the password properly
        ssh_public_key=request.ssh_public_key,
        inbound_directory="/dummy",  # Will be generated by helper methods
        outbound_directory="/dummy",
        file_name_patterns=request.file_name_patterns,
        poll_schedule_id=request.poll_schedule_id,
        poll_enabled=request.poll_enabled,
        response_filename_template=request.response_filename_template,
        response_timeout_minutes=request.response_timeout_minutes,
        max_file_size_bytes=request.max_file_size_bytes
    )
    
    db.add(config)
    await db.commit()
    await db.refresh(config)
    
    # Enhance response with multi-tenant helper fields
    response = SftpConfigurationResponse.model_validate(config)
    response.tenant_partner_username = config.get_tenant_partner_username()
    response.partner_directory_path = config.get_partner_directory_path()
    response.inbound_directory_path = config.get_inbound_directory_path()
    response.outbound_directory_path = config.get_outbound_directory_path()
    
    return response


@router.put("/configurations/{partner_id}", response_model=SftpConfigurationResponse)
async def update_sftp_configuration(
    partner_id: int,
    request: UpdateSftpConfigurationRequest,
    auth: AuthContext = Depends(require_permission("sftp:write")),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("sftp:write"))
):
    """Update SFTP configuration for a specific partner."""
    tenant_id = auth.tenant_id
    
    # Get existing configuration
    result = await db.execute(
        select(SftpConfiguration).where(
            and_(
                SftpConfiguration.tenant_id == tenant_id,
                SftpConfiguration.partner_id == partner_id
            )
        )
    )
    config = result.scalar_one_or_none()
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SFTP configuration not found"
        )
    
    # Update fields if provided
    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        # Map API field names to model field names
        if field == "password":
            setattr(config, "password_hash", value)  # TODO: Hash the password properly
        else:
            setattr(config, field, value)
    
    await db.commit()
    await db.refresh(config)
    
    # Enhance response with multi-tenant helper fields
    response = SftpConfigurationResponse.model_validate(config)
    response.tenant_partner_username = config.get_tenant_partner_username()
    response.partner_directory_path = config.get_partner_directory_path()
    response.inbound_directory_path = config.get_inbound_directory_path()
    response.outbound_directory_path = config.get_outbound_directory_path()
    
    return response


@router.delete("/configurations/{partner_id}", response_model=MessageResponse)
async def delete_sftp_configuration(
    partner_id: int,
    auth: AuthContext = Depends(require_permission("sftp:write")),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("sftp:write"))
):
    """Delete SFTP configuration for a specific partner."""
    tenant_id = auth.tenant_id
    
    # Get existing configuration
    result = await db.execute(
        select(SftpConfiguration).where(
            and_(
                SftpConfiguration.tenant_id == tenant_id,
                SftpConfiguration.partner_id == partner_id
            )
        )
    )
    config = result.scalar_one_or_none()
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SFTP configuration not found"
        )
    
    await db.delete(config)
    await db.commit()
    
    return MessageResponse(message=f"SFTP configuration deleted for partner {partner_id}")


@router.get("/directories/{partner_id}", response_model=MultiTenantDirectoryInfo)
async def validate_partner_directories(
    partner_id: int,
    auth: AuthContext = Depends(require_permission("sftp:read")),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("sftp:read"))
):
    """Validate and get information about partner's SFTP directories."""
    tenant_id = auth.tenant_id
    
    # Get SFTP configuration
    config_result = await db.execute(
        select(SftpConfiguration).where(
            and_(
                SftpConfiguration.tenant_id == tenant_id,
                SftpConfiguration.partner_id == partner_id
            )
        )
    )
    config = config_result.scalar_one_or_none()
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SFTP configuration not found"
        )
    
    # Get partner information
    partner_result = await db.execute(
        select(TradingPartner).where(
            and_(
                TradingPartner.tenant_id == tenant_id,
                TradingPartner.id == partner_id
            )
        )
    )
    partner = partner_result.scalar_one_or_none()
    
    if not partner:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Partner not found"
        )
    
    # Generate directory paths
    partner_directory_path = config.get_partner_directory_path()
    inbound_directory_path = config.get_inbound_directory_path()
    outbound_directory_path = config.get_outbound_directory_path()
    tenant_partner_username = config.get_tenant_partner_username()
    
    # Check if directories exist
    partner_dir = Path(partner_directory_path)
    inbound_dir = Path(inbound_directory_path)
    outbound_dir = Path(outbound_directory_path)
    
    directory_exists = (
        partner_dir.exists() and 
        inbound_dir.exists() and 
        outbound_dir.exists()
    )
    
    # Check if user exists (this would require system-level access)
    # For now, we'll assume user exists if config exists
    user_exists = True  # This could be enhanced with actual user validation
    
    return MultiTenantDirectoryInfo(
        tenant_id=tenant_id,
        partner_name=partner.name,
        tenant_partner_username=tenant_partner_username,
        partner_directory_path=partner_directory_path,
        inbound_directory_path=inbound_directory_path,
        outbound_directory_path=outbound_directory_path,
        directory_exists=directory_exists,
        user_exists=user_exists
    )


@router.post("/directories/{partner_id}/create", response_model=MessageResponse)
async def create_partner_directories(
    partner_id: int,
    auth: AuthContext = Depends(require_permission("sftp:write")),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("sftp:admin"))
):
    """Create SFTP directories for a partner (admin only)."""
    tenant_id = auth.tenant_id
    
    # Get SFTP configuration
    config_result = await db.execute(
        select(SftpConfiguration).where(
            and_(
                SftpConfiguration.tenant_id == tenant_id,
                SftpConfiguration.partner_id == partner_id
            )
        )
    )
    config = config_result.scalar_one_or_none()
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SFTP configuration not found"
        )
    
    # Generate directory paths
    partner_directory_path = config.get_partner_directory_path()
    inbound_directory_path = config.get_inbound_directory_path()
    outbound_directory_path = config.get_outbound_directory_path()
    
    try:
        # Create directories
        partner_dir = Path(partner_directory_path)
        inbound_dir = Path(inbound_directory_path)
        outbound_dir = Path(outbound_directory_path)
        
        partner_dir.mkdir(parents=True, exist_ok=True)
        inbound_dir.mkdir(parents=True, exist_ok=True)
        outbound_dir.mkdir(parents=True, exist_ok=True)
        
        # Create welcome file
        welcome_file = inbound_dir / "README.txt"
        welcome_content = f"""Welcome to EDI Lens SFTP Server
Tenant: {tenant_id}
Partner: {config.sftp_username}

Upload your EDI files to this 'in' directory.
Processed acknowledgments will be placed in the 'out' directory.

You have access only to:
- in/  (for uploading files)
- out/ (for downloading responses)
"""
        welcome_file.write_text(welcome_content)
        
        return MessageResponse(
            message=f"SFTP directories created successfully for partner {partner_id}"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create directories: {str(e)}"
        )


@router.get("/configurations/{partner_id}/enhanced", response_model=SftpConfigurationResponse)
async def get_enhanced_sftp_configuration(
    partner_id: int,
    auth: AuthContext = Depends(require_permission("sftp:read")),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("sftp:read"))
):
    """Get SFTP configuration with enhanced multi-tenant information."""
    tenant_id = auth.tenant_id
    
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
    
    # Enhance response with multi-tenant helper fields
    response = SftpConfigurationResponse.model_validate(configuration)
    response.tenant_partner_username = configuration.get_tenant_partner_username()
    response.partner_directory_path = configuration.get_partner_directory_path()
    response.inbound_directory_path = configuration.get_inbound_directory_path()
    response.outbound_directory_path = configuration.get_outbound_directory_path()
    
    return response