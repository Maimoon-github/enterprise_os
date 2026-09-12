"""Resolves immutable deliverables by UUID/hash."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from sqlalchemy import select

from app.persistence.database import metadata
from app.persistence.repositories.base import BaseJsonRepository, standard_table
from app.schemas.artifact import ArtifactReference

_table = standard_table("artifacts", metadata)


class ArtifactRepository(BaseJsonRepository[ArtifactReference]):
    """Persists and resolves ``ArtifactReference`` records."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        super().__init__(
            session_factory,
            _table,
            serialize=lambda model: model.model_dump(mode="json"),
            deserialize=lambda doc: ArtifactReference.model_validate(doc),
        )

    async def register(self, tenant_id: str, artifact: ArtifactReference) -> None:
        """Register an immutable deliverable reference under ``tenant_id``."""
        await self.save(artifact.artifact_id, tenant_id, artifact)

    async def resolve(self, artifact_id: str) -> ArtifactReference:
        """Return the artifact for ``artifact_id``, raising if it does not exist."""
        return await self.require(artifact_id)

    async def resolve_by_hash(
        self, content_hash: str, tenant_id: str | None = None
    ) -> ArtifactReference | None:
        """Find an artifact matching a SHA-256 cryptographic hash."""
        if self._session_factory is None:
            return None
        async with self._session_factory() as session:
            stmt = select(self._table.c.document)
            if tenant_id is not None:
                stmt = stmt.where(self._table.c.tenant_id == tenant_id)
            rows = await session.execute(stmt)
            for (doc,) in rows.all():
                art = ArtifactReference.model_validate(doc)
                if art.content_hash == content_hash:
                    return art
        return None

    async def list_by_tenant(
        self, tenant_id: str, deliverable_type: str | None = None
    ) -> list[ArtifactReference]:
        """Return all artifacts for ``tenant_id``, optionally filtered by ``deliverable_type``."""
        if self._session_factory is None:
            return []
        async with self._session_factory() as session:
            rows = await session.execute(
                select(self._table.c.document).where(self._table.c.tenant_id == tenant_id)
            )
            artifacts = [ArtifactReference.model_validate(doc) for (doc,) in rows.all()]
        if deliverable_type is not None:
            artifacts = [a for a in artifacts if a.deliverable_type == deliverable_type]
        return artifacts