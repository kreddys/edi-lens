import pytest
import pytest_asyncio
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
import logging 
import sys 

from src.main import app
from src.core.database import get_db, Base
from src.core.config import settings

# --- THIS IS THE NEW SECTION FOR LOGGING ---
@pytest.fixture(scope="session", autouse=True)
def setup_test_logging():
    """Set up logging to output to console for all tests."""
    # This configures the root logger.
    # All loggers created with logging.getLogger(__name__) will inherit this.
    logging.basicConfig(
        level=logging.DEBUG, # Set the level to DEBUG
        format="[%(asctime)s] [%(levelname)s] [%(name)s] - %(message)s",
        stream=sys.stdout, # Direct output to stdout
        force=True # Override any existing configurations
    )
# --- END OF NEW SECTION ---


# Use a separate test database URL
TEST_DATABASE_URL = settings.DATABASE_URL.replace(
    settings.POSTGRES_DB, settings.POSTGRES_DB + "_test"
)

# Create a test engine and sessionmaker
test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestAsyncSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Fixture that provides a database session for a test, and handles
    schema creation and teardown. This fixture is used by integration tests.
    """
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestAsyncSessionLocal() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await test_engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def async_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    Provide a clean test client for each test function, with DB dependency 
    overridden and lifespan events managed.
    """
    
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    # --- THIS IS THE FIX ---
    # Manually manage the application's lifespan events.
    # This ensures that startup events (like loading schemas) are run before tests,
    # and shutdown events are run after.
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client

    app.dependency_overrides.clear()