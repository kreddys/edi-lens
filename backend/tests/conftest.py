# FILE: backend/tests/conftest.py
import pytest
import pytest_asyncio
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
import logging 
import sys 
import os
import openlit
from pathlib import Path

from src.main import app
from src.core.database import get_db, Base
from src.core.config import settings

def pytest_addoption(parser):
    # ... (this is unchanged)
    parser.addoption(
        "--log-level-app", 
        action="store", 
        default="INFO",
        help="Set the log level for the application during tests (e.g., DEBUG, INFO, WARNING)"
    )

@pytest.fixture(scope="session", autouse=True)
def setup_test_suite(pytestconfig):
    log_level = pytestconfig.getoption("log_level_app").upper()
    logging.basicConfig(
        level=log_level,
        format="[%(asctime)s] [%(levelname)s] [%(name)s] - %(message)s",
        stream=sys.stdout,
        force=True
    )
    logging.info(f"Test logging configured with level: {log_level}")

    # --- THIS IS THE FIX ---
    # Set the log level for noisy libraries to WARNING to reduce clutter.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("litellm").setLevel(logging.WARNING)
    logging.getLogger("LiteLLM").setLevel(logging.WARNING)
    # --- END OF FIX ---

    os.environ["IS_PYTEST"] = "true"

    if os.getenv("ENABLE_OBSERVABILITY", "false").lower() == "true":
        print("\n[TEST SESSION START] Observability is enabled. Initializing OpenLIT...")
        
        # Disable all instrumentors by default for tests to avoid noise,
        # we can enable specific ones if we ever test instrumentation itself.
        openlit.init(
            application_name="edi-lens-test-suite",
            disabled_instrumentors=["*"]
        )
    else:
        print("\n[TEST SESSION START] Observability is disabled.")
    
    yield
    
    del os.environ["IS_PYTEST"]

# ... (rest of the file is unchanged) ...
test_engine = create_async_engine(settings.DATABASE_URL, echo=False)

TestAsyncSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with TestAsyncSessionLocal() as session:
        yield session
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()

@pytest_asyncio.fixture(scope="function")
async def async_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    # --- THIS IS THE FIX: The monkeypatch is no longer needed. ---
    # The EDI_SCHEMA_DIRECTORY from .env.test is sufficient.
    async def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client
            
    app.dependency_overrides.clear()