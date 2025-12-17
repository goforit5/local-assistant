"""Database session management for Local Assistant.

Provides async database session factory and dependency injection for FastAPI.
"""

import os
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.pool import NullPool

from memory.models import Base


# Get database URL from environment
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://assistant:assistant@localhost:5432/assistant"
)

# Convert postgresql:// to postgresql+asyncpg:// if needed
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)


# Create async engine
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    poolclass=NullPool,  # Use NullPool for better connection management
    pool_pre_ping=True,  # Verify connections before using
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency for database sessions.

    Yields an async database session and ensures cleanup on completion.

    Usage:
        @app.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(Item))
            return result.scalars().all()
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_session() -> AsyncSession:
    """Get a standalone database session.

    Returns a new async session. Caller is responsible for closing.

    Usage:
        async with get_session() as db:
            result = await db.execute(select(Item))
            items = result.scalars().all()
    """
    return AsyncSessionLocal()


async def init_db():
    """Initialize database tables.

    Creates all tables defined in Base metadata.
    Only use for development/testing - use Alembic for production.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_db():
    """Drop all database tables.

    WARNING: This will delete all data!
    Only use for development/testing.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def close_db():
    """Close database engine and cleanup connections."""
    await engine.dispose()
