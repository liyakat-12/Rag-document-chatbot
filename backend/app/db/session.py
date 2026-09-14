"""Database engine and session management."""

from collections.abc import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from backend.app.config import get_settings


class Base(DeclarativeBase):
    """Base class for ORM models."""


settings = get_settings()

_is_sqlite = settings.database_url.startswith("sqlite")

# NullPool for SQLite: avoids reused aiosqlite connections that raise
# "no active connection" under concurrent Streamlit/FastAPI traffic.
_engine_kwargs: dict = {
    "echo": settings.debug,
    "future": True,
}
if _is_sqlite:
    _engine_kwargs["poolclass"] = NullPool
    _engine_kwargs["connect_args"] = {"timeout": 30}

engine = create_async_engine(settings.database_url, **_engine_kwargs)


if _is_sqlite:

    @event.listens_for(engine.sync_engine, "connect")
    def _sqlite_on_connect(dbapi_connection, _connection_record) -> None:  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()


AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async DB session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Create all tables."""
    # Import models so metadata is populated
    from backend.app.db import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
