from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from src.core.database import Base


class ProcessingSchedule(Base):
    __tablename__ = 'processing_schedules'
    __table_args__ = (
        UniqueConstraint('name', name='_schedule_name_uc'),
        {'schema': 'public'}
    )

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    description = Column(Text, nullable=True)
    cron_expression = Column(String, nullable=False)  # "*/5 * * * *", "0 9 * * MON-FRI"
    is_active = Column(Boolean, nullable=False, default=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    sftp_configurations = relationship("SftpConfiguration", back_populates="schedule")


def get_default_schedules():
    """Returns the default processing schedules to insert during migration"""
    return [
        {
            'name': 'Every 5 minutes',
            'description': 'Continuous polling every 5 minutes',
            'cron_expression': '*/5 * * * *',
            'is_active': True
        },
        {
            'name': 'Every 15 minutes', 
            'description': 'Every 15 minutes',
            'cron_expression': '*/15 * * * *',
            'is_active': True
        },
        {
            'name': 'Every hour',
            'description': 'Top of every hour',
            'cron_expression': '0 * * * *',
            'is_active': True
        },
        {
            'name': 'Business hours only',
            'description': 'Every 15 minutes, 9 AM - 5 PM, weekdays',
            'cron_expression': '*/15 9-17 * * MON-FRI',
            'is_active': True
        },
        {
            'name': 'Once daily at 9 AM',
            'description': 'Daily at 9:00 AM',
            'cron_expression': '0 9 * * *',
            'is_active': True
        },
        {
            'name': 'Manual only',
            'description': 'Disable automatic polling',
            'cron_expression': '',
            'is_active': True
        }
    ]