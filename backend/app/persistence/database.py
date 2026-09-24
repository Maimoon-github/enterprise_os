"""PostgreSQL/pgvector/TimescaleDB connection boundary.

The concrete driver/ORM was unspecified by the source architecture (see
``docs/ASSUMPTIONS.md``); this module standardizes on SQLAlchemy's async
engine with ``asyncpg`` so every repository shares one connection pool and
one schema-creation entrypoint instead of each opening its own connection.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.settings import DatabaseSettings

metadata = MetaData()


class Database:
    """Owns the async engine and session factory for the system of record."""

    def __init__(self, settings: DatabaseSettings) -> None:
        self._settings = settings
        self._engine: AsyncEngine = create_async_engine(
            settings.dsn,
            pool_size=settings.pool_max_size,
            pool_pre_ping=True,
            connect_args={"timeout": settings.statement_timeout_seconds},
        )
        self._session_factory = async_sessionmaker(
            bind=self._engine, expire_on_commit=False, autoflush=False
        )

    @property
    def engine(self) -> AsyncEngine:
        return self._engine

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        """Return the shared async session factory for repositories to bind to."""

        return self._session_factory

    async def create_all(self) -> None:
        """Create all registered tables. Safe to call repeatedly (idempotent)."""

        async with self._engine.begin() as conn:
            await conn.run_sync(metadata.create_all)

    async def dispose(self) -> None:
        """Release all pooled connections."""

        await self._engine.dispose()

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """Yield a transactional session, committing on success and rolling back on error."""

        async with self._session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise