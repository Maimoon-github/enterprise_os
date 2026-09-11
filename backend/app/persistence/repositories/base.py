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

    async def save(self, record_id: str, tenant_id: str, model: ModelT) -> None:
        """Upsert ``model`` under ``record_id``, scoped to ``tenant_id``."""

        payload = self._serialize(model)
        async with self._session_factory() as session:
            existing = await session.scalar(
                select(self._table.c.id).where(self._table.c.id == record_id)
            )
            if existing is None:
                await session.execute(
                    self._table.insert().values(
                        id=record_id,
                        tenant_id=tenant_id,
                        document=payload,
                        updated_at=datetime.now(UTC),
                    )
                )
            else:
                await session.execute(
                    self._table.update()
                    .where(self._table.c.id == record_id)
                    .values(document=payload, updated_at=datetime.now(UTC))
                )
            await session.commit()

    async def get(self, record_id: str) -> ModelT | None:
        """Return the model stored under ``record_id``, or None if absent."""

        async with self._session_factory() as session:
            row = await session.execute(
                select(self._table.c.document).where(self._table.c.id == record_id)
            )
            document = row.scalar_one_or_none()
            return self._deserialize(document) if document is not None else None

    async def list_by_tenant(self, tenant_id: str) -> list[ModelT]:
        """Return all models stored for ``tenant_id``."""

        async with self._session_factory() as session:
            rows = await session.execute(
                select(self._table.c.document).where(self._table.c.tenant_id == tenant_id)
            )
            return [self._deserialize(doc) for (doc,) in rows.all()]

    async def require(self, record_id: str) -> ModelT:
        """Return the model stored under ``record_id``, raising if absent."""

        model = await self.get(record_id)
        if model is None:
            raise RepositoryError(f"No record found with id '{record_id}'.")
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
