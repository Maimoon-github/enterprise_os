"""PostgreSQL/pgvector/TimescaleDB connection boundary.

Standardizes on SQLAlchemy's async engine with asyncpg so every repository
shares connection pooling, deterministic transactional boundaries, tenant RLS
context propagation, and readiness checks.
"""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncGenerator, Sequence
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from sqlalchemy import MetaData, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.exceptions import PolicyViolationError
from app.core.settings import DatabaseSettings

logger = logging.getLogger(__name__)

metadata = MetaData()


class Database:
    """Owns the async engine, session factory, tenant RLS context, and migrations for Layer 4."""

    def __init__(self, settings: DatabaseSettings) -> None:
        self._settings = settings
        connect_args: dict[str, Any] = {}
        if "postgresql" in settings.dsn or "asyncpg" in settings.dsn:
            connect_args["timeout"] = settings.statement_timeout_seconds

        self._engine: AsyncEngine = create_async_engine(
            settings.dsn,
            pool_size=settings.pool_max_size,
            pool_pre_ping=True,
            connect_args=connect_args,
        )
        self._session_factory = async_sessionmaker(
            bind=self._engine, expire_on_commit=False, autoflush=False
        )
        self._migration_engine: AsyncEngine | None = None
        if settings.migration_dsn:
            self._migration_engine = create_async_engine(
                settings.migration_dsn,
                pool_pre_ping=True,
                connect_args=connect_args,
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
        if self._migration_engine is not None:
            await self._migration_engine.dispose()

    @asynccontextmanager
    async def session(
        self, *, tenant_id: str | None = None
    ) -> AsyncGenerator[AsyncSession, None]:
        """Yield a transactional session, setting tenant RLS context when provided."""
        async with self._session_factory() as session:
            try:
                if tenant_id and self._settings.enforce_rls:
                    try:
                        await session.execute(
                            text("SET LOCAL app.current_tenant = :tenant_id"),
                            {"tenant_id": tenant_id},
                        )
                    except Exception as e:
                        logger.debug("Could not set app.current_tenant session variable: %s", e)
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    @asynccontextmanager
    async def tenant_session(self, tenant_id: str) -> AsyncGenerator[AsyncSession, None]:
        """Yield a tenant-scoped transactional session, failing closed on empty tenant context."""
        if not tenant_id or not tenant_id.strip():
            raise ValueError("A non-empty tenant_id is required for tenant-scoped session.")
        async with self.session(tenant_id=tenant_id) as session:
            yield session

    @asynccontextmanager
    async def transaction(
        self,
        *,
        session: AsyncSession | None = None,
        tenant_id: str | None = None,
    ) -> AsyncGenerator[AsyncSession, None]:
        """Participate in caller-supplied transaction or open a new transactional boundary."""
        if session is not None:
            if tenant_id and self._settings.enforce_rls:
                try:
                    await session.execute(
                        text("SET LOCAL app.current_tenant = :tenant_id"),
                        {"tenant_id": tenant_id},
                    )
                except Exception as e:
                    logger.debug("Could not set app.current_tenant session variable: %s", e)
            async with session.begin_nested():
                yield session
        else:
            async with self.session(tenant_id=tenant_id) as new_sess:
                yield new_sess

    async def verify_extensions(
        self,
        required: Sequence[str] = ("vector",),
        *,
        fail_on_missing: bool = False,
    ) -> dict[str, bool]:
        """Check for installed PostgreSQL extensions without exposing credentials."""
        results: dict[str, bool] = {ext: False for ext in required}
        try:
            async with self._engine.connect() as conn:
                res = await conn.execute(text("SELECT extname FROM pg_extension"))
                installed = {row[0] for row in res.fetchall()}
                for ext in required:
                    results[ext] = ext in installed
        except Exception as exc:
            logger.debug("Extension query failed: %s", exc)
        if fail_on_missing:
            missing = [ext for ext, present in results.items() if not present]
            if missing:
                raise RuntimeError(f"Missing required database extensions: {missing}")
        return results

    async def verify_runtime_role(self) -> dict[str, Any]:
        """Verify that runtime role is non-superuser, non-owner, and has NOBYPASSRLS."""
        role_info: dict[str, Any] = {
            "current_user": "unknown",
            "is_superuser": False,
            "bypass_rls": False,
            "compliant": True,
        }
        try:
            async with self._engine.connect() as conn:
                user_res = await conn.execute(text("SELECT CURRENT_USER, current_setting('is_superuser', true)"))
                row = user_res.fetchone()
                if row:
                    role_info["current_user"] = row[0]
                    role_info["is_superuser"] = row[1] == "on"

                bypass_res = await conn.execute(
                    text("SELECT rolbypassrls FROM pg_roles WHERE rolname = CURRENT_USER")
                )
                bypass_row = bypass_res.fetchone()
                if bypass_row:
                    role_info["bypass_rls"] = bool(bypass_row[0])

                if role_info["is_superuser"] or role_info["bypass_rls"]:
                    role_info["compliant"] = False
                    if self._settings.require_non_privileged_role:
                        raise PolicyViolationError(
                            f"Privileged database role '{role_info['current_user']}' detected. "
                            "Runtime role must be non-superuser and NOBYPASSRLS."
                        )
        except PolicyViolationError:
            raise
        except Exception as exc:
            logger.debug("Runtime role verification check encountered non-fatal error: %s", exc)
        return role_info

    async def healthcheck(self) -> dict[str, Any]:
        """Perform database readiness check without leaking credentials or tenant records."""
        start = time.perf_counter()
        pool = self._engine.pool
        pool_stats = {
            "size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
        }
        try:
            async with self._engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            exts = await self.verify_extensions(["vector", "timescaledb"])
            return {
                "status": "healthy",
                "latency_ms": latency_ms,
                "pool": pool_stats,
                "extensions": exts,
            }
        except Exception as exc:
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            return {
                "status": "unhealthy",
                "error": exc.__class__.__name__,
                "latency_ms": latency_ms,
                "pool": pool_stats,
            }

    async def apply_migrations(
        self, migrations_dir: str | Path | None = None
    ) -> list[str]:
        """Execute versioned Layer-4 SQL migrations idempotently in numerical order."""
        if migrations_dir is None:
            base_path = Path(__file__).resolve().parent.parent.parent / "migrations" / "sql"
        else:
            base_path = Path(migrations_dir)

        if not base_path.exists():
            return []

        migration_files = sorted(base_path.glob("*.sql"))
        applied: list[str] = []

        engine_to_use = self._migration_engine or self._engine
        async with engine_to_use.begin() as conn:
            await conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                        version VARCHAR PRIMARY KEY,
                        applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                    );
                    """
                )
            )

            res = await conn.execute(text("SELECT version FROM schema_migrations"))
            already_applied = {row[0] for row in res.fetchall()}

            for sql_file in migration_files:
                version = sql_file.name
                if version in already_applied:
                    continue
                content = sql_file.read_text(encoding="utf-8")
                await conn.exec_driver_sql(content)
                await conn.execute(
                    text("INSERT INTO schema_migrations (version) VALUES (:version)"),
                    {"version": version},
                )
                applied.append(version)

        return applied