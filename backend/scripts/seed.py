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

# --- THIS IS THE FIX ---
# Path now correctly points to the top-level 'seed_data' directory
# __file__ is /.../backend/scripts/seed.py
# .parent is /.../backend/scripts/
# .parent is /.../backend/
SEED_DATA_DIR = Path(__file__).parent.parent / "seed_data"

# --- Database Setup ---
engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# --- Seeder Functions ---

async def clear_data(session: AsyncSession):
    """Wipes data from relevant tables before seeding."""
    print("🧹 Clearing existing trading partner data...")
    # We delete from trading_partners and rely on `cascade="all, delete-orphan"`
    # to handle the deletion of profiles and criteria.
    await session.execute(text("DELETE FROM trading_partners"))
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
        
        # This is where we can add more seeder functions in the future
        await seed_trading_partners(session)
        # await seed_rules(session) # Example for the future

    print("--- Database Seeding Complete ---")

if __name__ == "__main__":
    asyncio.run(main())