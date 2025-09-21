"""Database configuration helpers for the FastAPI backend."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .config import settings


class Base(DeclarativeBase):
    """Base class for ORM models."""


engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a scoped async database session."""

    async with AsyncSessionLocal() as session:
        yield session


async def dispose_engine() -> None:
    """Dispose the global database engine (useful for shutdown hooks)."""

    await engine.dispose()
