from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base, configure_mappers
from typing import AsyncGenerator
import logging
from .config import settings

logger = logging.getLogger(__name__)

engine = create_async_engine(settings.DATABASE_URL, echo=False)

AsyncSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

Base = declarative_base()

def configure_database_relationships():
    """Configure SQLAlchemy relationships after all models are imported.
    
    This function should be called after all models are imported to ensure
    that foreign key relationships can be properly resolved.
    """
    try:
        configure_mappers()
        logger.debug("Database relationships configured successfully")
    except Exception as e:
        logger.warning(f"Failed to configure database relationships: {e}")
        # This is non-fatal - relationships will be configured on first use

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get a database session."""
    logger.debug("Creating new database session.")
    async with AsyncSessionLocal() as session:
        logger.debug(f"[APP-SIDE] get_db dependency: yielding session with id: {id(session)}")
        try:
            yield session
        finally:
            logger.debug("Closing database session.")