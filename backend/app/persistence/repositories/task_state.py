"""Persists canonical task-state and dependency records."""

from __future__ import annotations

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

    async def list_by_directive(self, directive_id: str) -> list[CanonicalTaskState]:
        """Return every task state associated with ``directive_id``."""

        async with self._session_factory() as session:
            rows = await session.execute(select(self._table.c.document))
            states = [CanonicalTaskState.model_validate(doc) for (doc,) in rows.all()]
        return [state for state in states if state.directive_id == directive_id]