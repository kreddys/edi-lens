from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Optional, List
import logging

from src.models.processing_log import ProcessingLog

logger = logging.getLogger(__name__)


class ProcessingLogRepository:
    def __init__(self, db_session: AsyncSession):
        self.db: AsyncSession = db_session

    async def create_log(
        self,
        tenant_id: str,
        source: str,
        file_name: Optional[str] = None,
        file_size_bytes: Optional[int] = None,
        validation_result: str = "PENDING",
        processing_time_ms: Optional[int] = None,
        error_count: int = 0,
        schema_name: Optional[str] = None,
        snip_level_used: Optional[str] = None,
        profile_id: Optional[int] = None,
        ta1_generated: bool = False,
        ta1_999_generated: bool = False,
        original_content_path: Optional[str] = None,
        ta1_content_path: Optional[str] = None,
        ta1_999_content_path: Optional[str] = None
    ) -> ProcessingLog:
        """Create a new processing log entry."""
        
        log_entry = ProcessingLog(
            tenant_id=tenant_id,
            source=source,
            file_name=file_name,
            file_size_bytes=file_size_bytes,
            validation_result=validation_result,
            processing_time_ms=processing_time_ms,
            error_count=error_count,
            schema_name=schema_name,
            snip_level_used=snip_level_used,
            profile_id=profile_id,
            ta1_generated=ta1_generated,
            ta1_999_generated=ta1_999_generated,
            original_content_path=original_content_path,
            ta1_content_path=ta1_content_path,
            ta1_999_content_path=ta1_999_content_path
        )
        
        self.db.add(log_entry)
        await self.db.flush()
        await self.db.commit()  # Ensure immediate commit for E2E test visibility
        
        logger.info(f"Created processing log entry id={log_entry.id} for tenant '{tenant_id}' "
                   f"source='{source}' result='{validation_result}'")
        
        return log_entry

    async def get_by_id(self, log_id: int, tenant_id: str) -> Optional[ProcessingLog]:
        """Get processing log by ID for a specific tenant."""
        query = select(ProcessingLog).filter_by(id=log_id, tenant_id=tenant_id)
        result = await self.db.execute(query)
        return result.scalars().first()

    async def get_recent_for_tenant(
        self, 
        tenant_id: str, 
        limit: int = 50,
        source: Optional[str] = None,
        validation_result: Optional[str] = None
    ) -> List[ProcessingLog]:
        """Get recent processing logs for a tenant with optional filtering."""
        query = select(ProcessingLog).filter_by(tenant_id=tenant_id)
        
        if source:
            query = query.filter_by(source=source)
        if validation_result:
            query = query.filter_by(validation_result=validation_result)
            
        query = query.order_by(ProcessingLog.timestamp.desc()).limit(limit)
        
        result = await self.db.execute(query)
        return result.scalars().all()