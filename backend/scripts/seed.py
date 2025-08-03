import asyncio
import argparse
import yaml
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

from src.core.config import settings
from src.repositories.trading_partner import TradingPartnerRepository
from src.api.schemas import TradingPartnerCreate
from src.models.processing_schedule import ProcessingSchedule
from src.models.sftp_configuration import SftpConfiguration

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
    await session.execute(text("DELETE FROM partner_profiles"))  # Clear profiles second
    await session.execute(text("DELETE FROM trading_partners"))  # Clear partners last
    await session.execute(text("DELETE FROM processing_schedules"))
    await session.commit()
    print("✅ Data cleared.")

async def seed_trading_partners(session: AsyncSession):
    """Seeds trading partners from the YAML file."""
    print("🌱 Seeding Trading Partners...")
    repo = TradingPartnerRepository(session)
    seed_file = SEED_DATA_DIR / "trading_partners.yml"

    if not seed_file.exists():
        print(f"⚠️  Warning: Seed file not found at {seed_file}. Skipping.")
        return

    with open(seed_file, 'r') as f:
        partners_data = yaml.safe_load(f)

    if not partners_data:
        print("   - No trading partners found in seed file. Skipping.")
        return

    for partner_data in partners_data:
        tenant_id = partner_data["tenant_id"]
        partner_name = partner_data["name"]

        # Idempotency Check
        existing = await repo.get_by_name(name=partner_name, tenant_id=tenant_id)
        if existing:
            print(f"   - Skipping '{partner_name}' for tenant '{tenant_id}' (already exists).")
            continue

        print(f"   - Creating '{partner_name}' for tenant '{tenant_id}'...")
        # Use Pydantic schemas for validation and structure
        partner_in = TradingPartnerCreate.model_validate(partner_data)
        await repo.create_with_profiles(partner_in=partner_in, tenant_id=tenant_id)

    await session.commit()
    print("✅ Trading Partners seeded.")

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

async def seed_sftp_configurations(session: AsyncSession):
    """Seeds SFTP configurations for existing trading partners."""
    print("🌱 Seeding SFTP Configurations...")
    
    # Get processing schedules
    schedules_result = await session.execute(text("SELECT id, name FROM processing_schedules"))
    schedules = {row.name: row.id for row in schedules_result.fetchall()}
    
    # Get trading partners
    partners_result = await session.execute(text("SELECT id, name, tenant_id FROM trading_partners"))
    partners = {(row.tenant_id, row.name): row.id for row in partners_result.fetchall()}
    
    sftp_configs = [
        {
            "tenant_id": "tenant-a",
            "partner_name": "United Health Group (Professional)",
            "sftp_username": "tenant-a_uhg-pro",
            "password_hash": "uhg_secure_pass_123",  # In production, this should be properly hashed
            "poll_schedule": "Every 15 minutes",
            "file_patterns": '["*.edi", "*.x12", "*_837_*.txt"]'
        },
        {
            "tenant_id": "tenant-a", 
            "partner_name": "Change Healthcare (Clearinghouse)",
            "sftp_username": "tenant-a_chc",
            "password_hash": "chc_secure_pass_456",
            "poll_schedule": "Every 5 minutes",
            "file_patterns": '["*.835", "*.277", "*_remit_*.edi"]'
        },
        {
            "tenant_id": "tenant-b",
            "partner_name": "State Medicaid", 
            "sftp_username": "tenant-b_medicaid",
            "password_hash": "medicaid_pass_789",
            "poll_schedule": "Hourly",
            "file_patterns": '["*_medicaid_*.edi", "*.x12"]'
        }
    ]
    
    for config_data in sftp_configs:
        partner_key = (config_data["tenant_id"], config_data["partner_name"])
        if partner_key not in partners:
            print(f"   - Skipping SFTP config for '{config_data['partner_name']}' (partner not found).")
            continue
            
        partner_id = partners[partner_key]
        schedule_id = schedules.get(config_data["poll_schedule"])
        
        # Check if SFTP config already exists
        existing = await session.execute(
            text("SELECT id FROM sftp_configurations WHERE partner_id = :partner_id"),
            {"partner_id": partner_id}
        )
        if existing.fetchone():
            print(f"   - Skipping SFTP config for '{config_data['partner_name']}' (already exists).")
            continue
        
        print(f"   - Creating SFTP config for '{config_data['partner_name']}'...")
        sftp_config = SftpConfiguration(
            tenant_id=config_data["tenant_id"],
            partner_id=partner_id,
            sftp_enabled=True,
            sftp_username=config_data["sftp_username"],
            authentication_type="PASSWORD",
            password_hash=config_data["password_hash"],
            inbound_directory="/sftp/tenants/{tenant_id}/{username}/in",
            outbound_directory="/sftp/tenants/{tenant_id}/{username}/out",
            file_name_patterns=config_data["file_patterns"],
            poll_schedule_id=schedule_id,
            poll_enabled=True,
            response_timeout_minutes=30,
            max_file_size_bytes=52428800  # 50MB
        )
        session.add(sftp_config)
    
    await session.commit()
    print("✅ SFTP Configurations seeded.")

# --- Main Execution Logic ---

async def main():
    """Main function to run the seeding process."""
    parser = argparse.ArgumentParser(description="Seed the database with initial data.")
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Wipe existing data from seeded tables before running the seeder."
    )
    args = parser.parse_args()

    print("--- Starting Database Seeding ---")
    async with AsyncSessionLocal() as session:
        if args.clean:
            await clear_data(session)
        
        # Seed all components in order
        await seed_processing_schedules(session)
        await seed_trading_partners(session)
        await seed_sftp_configurations(session)

    print("--- Database Seeding Complete ---")

if __name__ == "__main__":
    asyncio.run(main())