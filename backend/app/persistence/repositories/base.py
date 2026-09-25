"""Shared JSON-document repository behavior.

Every system-of-record repository in this package persists a Pydantic
model as a JSONB document keyed by id and tenant, with an append-only audit
column where relevant. Centralizing the read/write mechanics here avoids
each of the seven repositories re-implementing the same session and
serialization boilerplate.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Generic, TypeVar

from sqlalchemy import Column, DateTime, MetaData, String, Table, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.exceptions import RepositoryError

ModelT = TypeVar("ModelT")


class BaseJsonRepository(Generic[ModelT]):
    """Generic async CRUD over a single JSONB-backed table."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        table: Table,
        *,
        serialize: Callable[[ModelT], dict],
        deserialize: Callable[[dict], ModelT],
    ) -> None:
        self._session_factory = session_factory
        self._table = table
        self._serialize = serialize
        self._deserialize = deserialize

    async def _apply_tenant_context(self, session: AsyncSession, tenant_id: str) -> None:
        """Best-effort local tenant variable setup for PostgreSQL RLS."""
        if not tenant_id or not isinstance(tenant_id, str) or not tenant_id.strip():
            raise RepositoryError("Tenant ID cannot be empty.")
        try:
            from sqlalchemy import text

            await session.execute(
                text("SET LOCAL app.current_tenant = :tenant_id"),
                {"tenant_id": tenant_id},
            )
        except Exception:
            # Fall back safely on non-PostgreSQL dialects or unit-test mocks
            pass

    async def save(
        self,
        record_id: str,
        tenant_id: str,
        model: ModelT,
        *,
        session: AsyncSession | None = None,
    ) -> None:
        """Upsert ``model`` under ``record_id``, scoped to ``tenant_id``.

        If ``session`` is provided, participates in the caller's transaction without
        committing. Fails closed on cross-tenant writes or empty tenant_id.
        """
        if not record_id or not isinstance(record_id, str) or not record_id.strip():
            raise RepositoryError("Record ID cannot be empty.")
        if not tenant_id or not isinstance(tenant_id, str) or not tenant_id.strip():
            raise RepositoryError("Tenant ID cannot be empty.")

        payload = self._serialize(model)

        async def _execute_save(sess: AsyncSession) -> None:
            await self._apply_tenant_context(sess, tenant_id)
            existing_row = await sess.execute(
                select(self._table.c.tenant_id).where(self._table.c.id == record_id)
            )
            existing_tenant = existing_row.scalar_one_or_none()

            if existing_tenant is not None and existing_tenant != tenant_id:
                raise RepositoryError(
                    f"Cross-tenant access violation: record '{record_id}' does not belong to tenant '{tenant_id}'."
                )

            if existing_tenant is None:
                await sess.execute(
                    self._table.insert().values(
                        id=record_id,
                        tenant_id=tenant_id,
                        document=payload,
                        updated_at=datetime.now(UTC),
                    )
                )
            else:
                await sess.execute(
                    self._table.update()
                    .where((self._table.c.id == record_id) & (self._table.c.tenant_id == tenant_id))
                    .values(document=payload, updated_at=datetime.now(UTC))
                )

        if session is not None:
            await _execute_save(session)
        else:
            async with self._session_factory() as local_session:
                await _execute_save(local_session)
                await local_session.commit()

    async def get(
        self,
        record_id: str,
        *,
        tenant_id: str | None = None,
        session: AsyncSession | None = None,
    ) -> ModelT | None:
        """Return the model stored under ``record_id``, or None if absent.

        If ``tenant_id`` is supplied, bounds the read strictly to that tenant.
        If ``session`` is supplied, executes within the caller's transaction.
        """
        if not record_id or not isinstance(record_id, str) or not record_id.strip():
            raise RepositoryError("Record ID cannot be empty.")
        if tenant_id is not None and (not isinstance(tenant_id, str) or not tenant_id.strip()):
            raise RepositoryError("Tenant ID cannot be empty.")

        stmt = select(self._table.c.document).where(self._table.c.id == record_id)
        if tenant_id is not None:
            stmt = stmt.where(self._table.c.tenant_id == tenant_id)

        if session is not None:
            row = await session.execute(stmt)
            document = row.scalar_one_or_none()
            return self._deserialize(document) if document is not None else None

        async with self._session_factory() as local_session:
            row = await local_session.execute(stmt)
            document = row.scalar_one_or_none()
            return self._deserialize(document) if document is not None else None

    async def list_by_tenant(
        self,
        tenant_id: str,
        *,
        session: AsyncSession | None = None,
    ) -> list[ModelT]:
        """Return all models stored for ``tenant_id``.

        Fails closed if ``tenant_id`` is missing or empty.
        If ``session`` is supplied, participates in caller's transaction.
        """
        if not tenant_id or not isinstance(tenant_id, str) or not tenant_id.strip():
            raise RepositoryError("Tenant ID cannot be empty.")

        stmt = select(self._table.c.document).where(self._table.c.tenant_id == tenant_id)
        if session is not None:
            rows = await session.execute(stmt)
            return [self._deserialize(doc) for (doc,) in rows.all()]

        async with self._session_factory() as local_session:
            rows = await local_session.execute(stmt)
            return [self._deserialize(doc) for (doc,) in rows.all()]

    async def require(
        self,
        record_id: str,
        *,
        tenant_id: str | None = None,
        session: AsyncSession | None = None,
    ) -> ModelT:
        """Return the model stored under ``record_id``, raising if absent."""
        model = await self.get(record_id, tenant_id=tenant_id, session=session)
        if model is None:
            msg = f"No record found with id '{record_id}'"
            if tenant_id:
                msg += f" for tenant '{tenant_id}'"
            raise RepositoryError(f"{msg}.")
        return model


def standard_table(name: str, metadata: MetaData) -> Table:
    """Return a ``Table`` with the standard id/tenant_id/document/updated_at shape."""

    return Table(
        name,
        metadata,
        Column("id", String, primary_key=True),
        Column("tenant_id", String, nullable=False, index=True),
        Column("document", JSONB, nullable=False),
        Column("updated_at", DateTime(timezone=True), nullable=False),
    )
