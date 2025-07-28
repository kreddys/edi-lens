# FILE: backend/tests/conftest.py
import pytest
import pytest_asyncio
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
import logging
import json
import sys
from pathlib import Path
import os

from src.main import app
from src.core.database import get_db, Base
from src.core.config import settings
from src.edi_schemas.edi_guide import ImplementationGuideSchema

# ==============================================================================
# PYTEST HOOKS & SESSION-WIDE FIXTURES
# ==============================================================================

@pytest.fixture(scope="session", autouse=True)
def setup_test_environment(pytestconfig):
    """
    An autouse session-scoped fixture to configure the test environment
    before any tests are run. This is the definitive place for setup.
    """
    # 1. Configure Logging
    # Use pytest's own --log-cli-level option, defaulting to INFO if not provided.
    log_level = pytestconfig.getoption("log_cli_level") or "INFO"
    logging.basicConfig(
        level=log_level.upper(),
        format="[%(asctime)s] [%(levelname)s] [%(name)s:%(lineno)d] - %(message)s",
        stream=sys.stdout,
        force=True  # This is crucial to override any other logging configs.
    )
    # Reduce noise from verbose libraries unless we are in DEBUG mode.
    if log_level.upper() != "DEBUG":
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    
    logging.info(f"Test logging configured with level: {log_level.upper()}")

    # 2. Set environment variable to signal we are in a test run
    os.environ["IS_PYTEST"] = "true"
    
    # Let the test session run
    yield
    
    # Teardown: unset the environment variable
    del os.environ["IS_PYTEST"]

# ==============================================================================
# INTEGRATION TEST FIXTURES (Depend on Docker services)
# ==============================================================================

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
    """Provides a clean database session for each integration test function."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with TestAsyncSessionLocal() as session:
        yield session
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()

@pytest_asyncio.fixture(scope="function")
async def async_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Provides an httpx client for making API calls to the app in integration tests."""
    async def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    # The lifespan context ensures the app's startup/shutdown events run
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client
            
    app.dependency_overrides.clear()

# ==============================================================================
# UNIT TEST FIXTURES (Completely isolated, no Docker needed)
# ==============================================================================

@pytest.fixture(scope="session")
def standalone_schema() -> ImplementationGuideSchema:
    """
    A session-scoped fixture specifically for UNIT TESTS.
    It loads the 837p schema directly from its runtime file path,
    bypassing the app's SchemaManager and any database/client fixtures.
    This ensures true isolation for parser tests.
    """
    try:
        project_root = Path(__file__).parent.parent
        schema_path = project_root / "data/edi_schemas/837.5010.X222.A1.json"
        
        if not schema_path.exists():
            pytest.fail(f"Unit test schema file not found at calculated path: {schema_path}")
        
        with open(schema_path, 'r') as f:
            schema_data = json.load(f)
            return ImplementationGuideSchema.model_validate(schema_data)
    except Exception as e:
        pytest.fail(f"Failed to load or parse the schema for unit tests: {e}")

@pytest.fixture(scope="session")
def valid_837p_edi_string() -> str:
    """Provides a shared, compliant 837P EDI string for parser unit tests."""
    return """
ISA*00*          *00*          *ZZ*SENDERID       *ZZ*RECEIVERID     *240715*1200*^*00501*000000001*0*P*>~
GS*HC*SENDER*RECEIVER*20240715*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
BHT*0019*00*1234*20240715*1200*CH~
NM1*41*2*PREMIER BILLING*****46*SUBMITTER1~
PER*IC*JOHN DOE*TE*8005551212~
NM1*40*2*PAYER A*****46*RECEIVER1~
HL*1**20*1~
NM1*85*2*BILLING PROVIDER*****XX*1234567890~
N3*123 MAIN ST~
N4*ANYTOWN*CA*90210~
REF*EI*123456789~
HL*2*1*22*0~
SBR*P*18*GRP123******CI~
NM1*IL*1*DOE*JOHN****MI*SUBID123~
NM1*PR*2*PAYER A*****PI*PAYERID123~
CLM*PATCTRL123*500***11>B>1*Y*A*Y*Y~
DTP*431*D8*20240715~
PWK*OZ*BM***AC*CONTROL123~
HI*BK>87340~
LX*1~
SV1*HC>99213*125*UN*1***1**Y~
SE*24*0001~
GE*1*1~
IEA*1*000000001~
""".strip()