"""Persists canonical task-state and dependency records."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.persistence.database import metadata
from app.persistence.repositories.base import BaseJsonRepository, standard_table
from app.schemas.task_state import CanonicalTaskState

_table = standard_table("task_states", metadata)


class TaskStateRepository(BaseJsonRepository[CanonicalTaskState]):
    """Persists the authoritative ``CanonicalTaskState`` for every task."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        super().__init__(
            session_factory,
            _table,
            serialize=lambda model: model.model_dump(mode="json"),
            deserialize=lambda doc: CanonicalTaskState.model_validate(doc),
        )

    async def save_state(self, tenant_id: str, state: CanonicalTaskState) -> None:
        await self.save(state.task_id, tenant_id, state)

    async def compare_and_swap_state(
        self, tenant_id: str, expected_version: int, state: CanonicalTaskState
    ) -> bool:
        """Atomically update state if current version matches expected_version."""
        payload = self._serialize(state)
        async with self._session_factory() as session:
            row = await session.execute(
                select(self._table.c.document).where(
                    self._table.c.id == state.task_id,
                    self._table.c.tenant_id == tenant_id,
                )
            )
            doc = row.scalar_one_or_none()
            if doc is not None:
                current = self._deserialize(doc)
                if current.version != expected_version:
                    return False
                await session.execute(
                    self._table.update()
                    .where(
                        self._table.c.id == state.task_id,
                        self._table.c.tenant_id == tenant_id,
                    )
                    .values(document=payload, updated_at=datetime.now(UTC))
                )
            else:
                if expected_version != 0:
                    return False
                await session.execute(
                    self._table.insert().values(
                        id=state.task_id,
                        tenant_id=tenant_id,
                        document=payload,
                        updated_at=datetime.now(UTC),
                    )
                )
            await session.commit()
            return True

    async def list_by_directive(self, directive_id: str) -> list[CanonicalTaskState]:
        """Return every task state associated with ``directive_id``."""

        async with self._session_factory() as session:
            rows = await session.execute(select(self._table.c.document))
            states = [CanonicalTaskState.model_validate(doc) for (doc,) in rows.all()]
        return [state for state in states if state.directive_id == directive_id]