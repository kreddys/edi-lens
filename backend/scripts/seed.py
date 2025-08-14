import asyncio
import argparse
import yaml
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

from src.core.config import settings

from src.api.schemas import TradingPartnerCreate
from src.models.processing_schedule import ProcessingSchedule
from src.services.sftp_user_manager import SftpUserManager

# --- THIS IS THE FIX ---
# Path now correctly points to the top-level 'seed_data' directory
# __file__ is /.../backend/scripts/seed.py
# .parent is /.../backend/scripts/
# .parent is /.../backend/
SEED_DATA_DIR = Path(__file__).parent.parent / "data" / "seed"

# --- Database Setup ---
engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# --- Seeder Functions ---

async def clear_data(session: AsyncSession):
    """Wipes data from relevant tables before seeding."""
    print("🧹 Clearing existing seed data...")
    # Clear in dependency order (due to foreign key constraints)
    await session.execute(text("DELETE FROM sftp_configurations"))
    await session.execute(text("DELETE FROM profile_criteria"))  # Clear criteria first
    
    
    await session.execute(text("DELETE FROM processing_schedules"))
    await session.commit()
    print("✅ Data cleared.")



async def seed_processing_schedules(session: AsyncSession):
    """Seeds processing schedules for SFTP polling."""
    print("🌱 Seeding Processing Schedules...")
    
    schedules = [
        {
            "name": "Every 5 minutes",
            "description": "High frequency polling for critical partners",
            "cron_expression": "*/5 * * * *",
            "is_active": True
        },
        {
            "name": "Every 15 minutes",
            "description": "Standard polling frequency",
            "cron_expression": "*/15 * * * *",
            "is_active": True
        },
        {
            "name": "Hourly",
            "description": "Low frequency polling",
            "cron_expression": "0 * * * *",
            "is_active": True
        },
        {
            "name": "Business Hours Only",
            "description": "Every 30 minutes during business hours (9 AM - 5 PM)",
            "cron_expression": "*/30 9-17 * * 1-5",
            "is_active": True
        },
        {
            "name": "Daily",
            "description": "Once per day at 6 AM",
            "cron_expression": "0 6 * * *",
            "is_active": True
        },
        {
            "name": "Manual Only",
            "description": "No automatic polling - manual trigger only",
            "cron_expression": "",
            "is_active": False
        }
    ]
    
    for schedule_data in schedules:
        # Check if schedule already exists
        existing = await session.execute(
            text("SELECT id FROM processing_schedules WHERE name = :name"),
            {"name": schedule_data["name"]}
        )
        if existing.fetchone():
            print(f"   - Skipping '{schedule_data['name']}' (already exists).")
            continue
        
        print(f"   - Creating schedule '{schedule_data['name']}'...")
        schedule = ProcessingSchedule(**schedule_data)
        session.add(schedule)
    
    await session.commit()
    print("✅ Processing Schedules seeded.")


# --- Main Execution Logic ---

async def main():
    """Main function to run the seeding process."""
    parser = argparse.ArgumentParser(description="Seed the database with initial data.")
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Wipe existing data from seeded tables before running the seeder."
    )
    parser.add_argument(
        "--create-sftp",
        action="store_true",
        help="Create SFTP users in SFTPGo for SFTP-enabled trading partners."
    )
    args = parser.parse_args()

    print("--- Starting Database Seeding ---")
    async with AsyncSessionLocal() as session:
        if args.clean:
            await clear_data(session)
        
        # Seed all components in order
        await seed_processing_schedules(session)
        

    if args.create_sftp:
        print("\n📡 SFTP Connection Details:")
        print("🌐 SFTPGo Web Admin: http://localhost:8080/web/admin/")
        print("🔑 Admin credentials: admin / admin123")
        print("📡 SFTP Connection: localhost:2022")
        print("💾 Storage Backend: MinIO S3")
        print("\n🔐 Trading Partner SFTP Credentials:")
        print("  - tenant-a_uhg-pro:uhg_secure_pass_123 (United Health Group)")
        print("  - tenant-a_chc:chc_secure_pass_456 (Change Healthcare)")
        print("  - tenant-b_medicaid:medicaid_pass_789 (State Medicaid)")

    print("--- Database Seeding Complete ---")

if __name__ == "__main__":
    asyncio.run(main())