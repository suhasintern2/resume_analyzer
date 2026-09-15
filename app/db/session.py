"""Database engine and session management.

Engines are created lazily (SQLAlchemy does not connect until first use),
so importing this module never requires the database to be running.
"""

import logging

from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings

logger = logging.getLogger(__name__)

# Sync engine (used by SQLAlchemy 2.0-style ORM sessions and Alembic-style tooling).
engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DB_ECHO,
    pool_size=settings.DB_POOL_SIZE,
    pool_pre_ping=True,
)

# Async engine (used by async FastAPI routes, e.g. the job queue in later tasks).
async_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DB_ECHO,
    pool_size=settings.DB_POOL_SIZE,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
AsyncSessionLocal = async_sessionmaker(bind=async_engine, expire_on_commit=False)


def get_db():
    """FastAPI dependency yielding a SQLAlchemy session per request."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


async def check_db_connection() -> bool:
    """Verify the database is reachable. Returns True on success."""
    try:
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database connection check failed: {e}")
        return False