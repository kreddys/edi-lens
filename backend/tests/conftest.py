import pytest
from typing import AsyncGenerator

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

from src.main import app
from src.core.database import Base, get_db
from src.core.config import settings

# --- Test Database Setup ---
# Use a separate database for testing
TEST_DATABASE_URL = f"{settings.DATABASE_URL}_test"
DEFAULT_DATABASE_URL = settings.DATABASE_URL.rsplit('/', 1)[0] + '/postgres'

# Create engines
engine = create_async_engine(TEST_DATABASE_URL)
default_engine = create_async_engine(DEFAULT_DATABASE_URL, isolation_level="AUTOCOMMIT")

TestingSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=engine, class_=AsyncSession
)

# --- Pytest Fixtures ---
@pytest.fixture(scope="session", autouse=True)
async def setup_test_database():
    """
    Fixture to create and tear down the test database for the entire test session.
    """
    db_name = TEST_DATABASE_URL.split('/')[-1]
    
    async with default_engine.connect() as conn:
        await conn.execute(text(f"DROP DATABASE IF EXISTS {db_name}"))
        await conn.execute(text(f"CREATE DATABASE {db_name}"))

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Provides a clean database session for each test function.
    """
    async with TestingSessionLocal() as session:
        yield session

@pytest.fixture
async def async_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    Provides an async test client for making API requests.
    This client uses the test database.
    """
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

    # Clean up the override after the test
    del app.dependency_overrides[get_db]