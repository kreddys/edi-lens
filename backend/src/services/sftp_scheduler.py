"""
SFTP Scheduler Service
This service manages the scheduling and coordination of SFTP file processing.
"""

import asyncio
import logging
from datetime import datetime
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

try:
    from croniter import croniter
except ImportError:
    croniter = None
    logging.warning("croniter not available, cron scheduling will be disabled")

from src.models.sftp_configuration import SftpConfiguration
from src.models.processing_schedule import ProcessingSchedule
from src.services.sftp_file_processor import SftpFileProcessor
from src.core.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


class SftpSchedulerService:
    """Service for scheduling and coordinating SFTP file processing."""
    
    def __init__(self, check_interval: int = 60):
        self.check_interval = check_interval  # seconds between schedule checks
        self.file_processor = SftpFileProcessor()
        self.running = False
        self._tasks: List[asyncio.Task] = []
    
    async def start(self):
        """Start the scheduler service."""
        if self.running:
            logger.warning("Scheduler is already running")
            return
        
        self.running = True
        logger.info("Starting SFTP Scheduler Service")
        
        # Start the main scheduler loop
        scheduler_task = asyncio.create_task(self._scheduler_loop())
        self._tasks.append(scheduler_task)
        
        logger.info("SFTP Scheduler Service started successfully")
    
    async def stop(self):
        """Stop the scheduler service."""
        if not self.running:
            return
        
        logger.info("Stopping SFTP Scheduler Service")
        self.running = False
        
        # Cancel all running tasks
        for task in self._tasks:
            if not task.done():
                task.cancel()
        
        # Wait for tasks to complete
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        
        self._tasks.clear()
        logger.info("SFTP Scheduler Service stopped")
    
    async def _scheduler_loop(self):
        """Main scheduler loop that checks for due processing jobs."""
        while self.running:
            try:
                await self._check_and_process_due_configs()
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
            
            # Wait before next check
            await asyncio.sleep(self.check_interval)
    
    async def _check_and_process_due_configs(self):
        """Check for SFTP configurations that are due for processing."""
        async with AsyncSessionLocal() as db_session:
            # Get all active SFTP configurations with polling enabled
            result = await db_session.execute(
                select(SftpConfiguration, ProcessingSchedule).join(
                    ProcessingSchedule, 
                    SftpConfiguration.poll_schedule_id == ProcessingSchedule.id
                ).where(
                    and_(
                        SftpConfiguration.sftp_enabled == True,
                        SftpConfiguration.poll_enabled == True,
                        ProcessingSchedule.is_active == True
                    )
                )
            )
            configs_and_schedules = result.all()
            
            logger.debug(f"Found {len(configs_and_schedules)} active SFTP configurations")
            
            current_time = datetime.utcnow()
            
            for config, schedule in configs_and_schedules:
                try:
                    if await self._is_due_for_processing(config, schedule, current_time):
                        logger.info(f"Processing files for partner {config.partner_id} (schedule: {schedule.name})")
                        
                        # Create a task to process files for this configuration
                        process_task = asyncio.create_task(
                            self._process_config_with_error_handling(config)
                        )
                        self._tasks.append(process_task)
                        
                        # Update last processed time
                        await self._update_last_processed_time(db_session, config, current_time)
                
                except Exception as e:
                    logger.error(f"Error checking schedule for partner {config.partner_id}: {e}")
    
    async def _is_due_for_processing(
        self, 
        config: SftpConfiguration, 
        schedule: ProcessingSchedule, 
        current_time: datetime
    ) -> bool:
        """Check if a configuration is due for processing based on its schedule."""
        
        # Manual-only schedule (empty cron expression)
        if not schedule.cron_expression.strip():
            return False
        
        # If croniter is not available, fall back to simple time-based checking
        if croniter is None:
            logger.warning("croniter not available, using simple time-based processing")
            # Simple fallback: process every check interval for active schedules
            return True
        
        try:
            # Parse the cron expression
            cron = croniter(schedule.cron_expression, current_time)
            
            # Check if we've passed the last scheduled time
            # We look back up to our check interval to see if we missed a scheduled run
            last_run_window = current_time.timestamp() - self.check_interval
            previous_run = cron.get_prev()
            
            # If the previous scheduled run was within our check window and after
            # the last processed time, then we should process
            if previous_run >= last_run_window:
                # Check against last processed time if available
                # For now, we'll use a simple approach - process if the previous 
                # scheduled time was recent
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error parsing cron expression '{schedule.cron_expression}': {e}")
            return False
    
    async def _update_last_processed_time(
        self, 
        db_session: AsyncSession, 
        config: SftpConfiguration, 
        processed_time: datetime
    ):
        """Update the last processed timestamp for a configuration."""
        # Note: We could add a last_processed_at field to SftpConfiguration
        # For now, we'll rely on the file processing logs to track processing
        pass
    
    async def _process_config_with_error_handling(self, config: SftpConfiguration):
        """Process files for a configuration with error handling."""
        try:
            await self.file_processor.process_files_for_config(config)
        except Exception as e:
            logger.error(f"Error processing files for partner {config.partner_id}: {e}")
        finally:
            # Remove this task from the active tasks list
            current_task = asyncio.current_task()
            if current_task in self._tasks:
                self._tasks.remove(current_task)
    
    async def process_partner_manually(self, partner_id: int) -> bool:
        """Manually trigger processing for a specific partner."""
        try:
            async with AsyncSessionLocal() as db_session:
                result = await db_session.execute(
                    select(SftpConfiguration).where(
                        and_(
                            SftpConfiguration.partner_id == partner_id,
                            SftpConfiguration.sftp_enabled == True
                        )
                    )
                )
                config = result.scalar_one_or_none()
                
                if not config:
                    logger.warning(f"No active SFTP configuration found for partner {partner_id}")
                    return False
                
                logger.info(f"Manually processing files for partner {partner_id}")
                await self.file_processor.process_files_for_config(config)
                return True
                
        except Exception as e:
            logger.error(f"Error manually processing partner {partner_id}: {e}")
            return False
    
    async def get_processing_status(self) -> dict:
        """Get current status of the scheduler and active processing tasks."""
        active_tasks = len([task for task in self._tasks if not task.done()])
        
        return {
            "running": self.running,
            "check_interval": self.check_interval,
            "active_processing_tasks": active_tasks,
            "total_tasks": len(self._tasks)
        }


# Global scheduler instance
_scheduler_instance: Optional[SftpSchedulerService] = None


async def get_scheduler() -> SftpSchedulerService:
    """Get or create the global scheduler instance."""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = SftpSchedulerService()
    return _scheduler_instance


async def start_scheduler():
    """Start the global scheduler service."""
    scheduler = await get_scheduler()
    await scheduler.start()


async def stop_scheduler():
    """Stop the global scheduler service."""
    global _scheduler_instance
    if _scheduler_instance:
        await _scheduler_instance.stop()
        _scheduler_instance = None