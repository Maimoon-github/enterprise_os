"""Persists enterprise directives and generated operational records."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.exceptions import PolicyViolationError
from app.persistence.database import metadata
from app.persistence.repositories.base import BaseJsonRepository, standard_table
from app.schemas.governance import Directive

_table = standard_table("operational_directives", metadata)


class OperationalRepository(BaseJsonRepository[Directive]):
    """Persists ``Directive`` records issued by tenant owners."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        super().__init__(
            session_factory,
            _table,
            serialize=lambda model: model.model_dump(mode="json"),
            deserialize=lambda doc: Directive.model_validate(doc),
        )

    async def save_directive(self, directive: Directive, session: AsyncSession | None = None) -> None:
        """Persist a directive, enforcing that existing directive revisions cannot be modified."""
        existing = await self.get(directive.directive_id, session=session)
        if existing is not None:
            if existing.model_dump(mode="json") != directive.model_dump(mode="json"):
                raise PolicyViolationError(
                    f"Directive '{directive.directive_id}' already exists and is immutable."
                )
            return
        await self.save(directive.directive_id, directive.tenant_id, directive, session=session)