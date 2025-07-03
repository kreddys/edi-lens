from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from .config import settings

# Create the async engine
engine = create_async_engine(settings.DATABASE_URL, echo=True)

# Create a sessionmaker
AsyncSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Base class for SQLAlchemy models
Base = declarative_base()

async def get_db() -> AsyncSession:
    """Dependency to get a database session."""
    async with AsyncSessionLocal() as session:
        yield session

async def init_db():
    """Initializes the database by creating all tables."""
    async with engine.begin() as conn:
        # The following command creates all tables.
        # For production, you should use a migration tool like Alembic.
        # from src.models import trading_partner, rule # etc.
        await conn.run_sync(Base.metadata.create_all)