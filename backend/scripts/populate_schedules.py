#!/usr/bin/env python3
"""
Script to populate default processing schedules for SFTP functionality.
This is a temporary script to help with testing until migration data insertion is fixed.
"""

import asyncio
import sys
import os

# Add the parent directory to the path to import src modules
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from src.models.processing_schedule import ProcessingSchedule, get_default_schedules
from src.core.config import settings


async def populate_default_schedules():
    """Populate default processing schedules if they don't exist."""
    
    # Create async engine
    engine = create_async_engine(settings.DATABASE_URL, echo=True)
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        try:
            # Check if schedules already exist
            result = await session.execute(select(ProcessingSchedule))
            existing_schedules = result.scalars().all()
            
            if existing_schedules:
                print(f"Found {len(existing_schedules)} existing schedules:")
                for schedule in existing_schedules:
                    print(f"  - {schedule.name}")
                return
            
            # Insert default schedules
            default_schedules = get_default_schedules()
            print(f"Inserting {len(default_schedules)} default schedules...")
            
            for schedule_data in default_schedules:
                schedule = ProcessingSchedule(**schedule_data)
                session.add(schedule)
            
            await session.commit()
            print("Successfully inserted default processing schedules.")
            
        except Exception as e:
            print(f"Error populating schedules: {e}")
            await session.rollback()
        finally:
            await engine.dispose()


if __name__ == "__main__":
    asyncio.run(populate_default_schedules())