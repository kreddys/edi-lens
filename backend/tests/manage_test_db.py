import asyncio
import sys
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from src.core.config import settings
from src.core.database import Base

async def create_test_db():
    """Creates the test database."""
    print("--- Creating Test Database ---")
    db_name = f"{settings.POSTGRES_DB}_test"
    # Connect to the default 'postgres' database to be able to create a new one
    default_db_url = settings.DATABASE_URL.rsplit('/', 1)[0] + '/postgres'
    engine = create_async_engine(default_db_url, isolation_level="AUTOCOMMIT")

    async with engine.connect() as conn:
        # Check if DB exists before trying to drop it
        res = await conn.execute(text(f"SELECT 1 FROM pg_database WHERE datname='{db_name}'"))
        if res.scalar() == 1:
            print(f"Test database '{db_name}' already exists. Dropping it first.")
            await conn.execute(text(f"DROP DATABASE {db_name} WITH (FORCE)"))
        
        print(f"Creating new test database: '{db_name}'")
        await conn.execute(text(f"CREATE DATABASE {db_name}"))

    await engine.dispose()

    print("--- Test Database Created Successfully ---")


async def drop_test_db():
    """Drops the test database."""
    print("--- Dropping Test Database ---")
    db_name = f"{settings.POSTGRES_DB}_test"
    default_db_url = settings.DATABASE_URL.rsplit('/', 1)[0] + '/postgres'
    engine = create_async_engine(default_db_url, isolation_level="AUTOCOMMIT")

    async with engine.connect() as conn:
        await conn.execute(text(f"DROP DATABASE IF EXISTS {db_name} WITH (FORCE)"))

    await engine.dispose()
    print("--- Test Database Dropped Successfully ---")

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ["create", "drop"]:
        print("Usage: python -m tests.manage_test_db [create|drop]")
        sys.exit(1)

    command = sys.argv[1]
    if command == "create":
        asyncio.run(create_test_db())
    elif command == "drop":
        asyncio.run(drop_test_db())