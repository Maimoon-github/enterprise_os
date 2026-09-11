"""Resolves immutable deliverables by UUID/hash."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.persistence.database import metadata
from app.persistence.repositories.base import BaseJsonRepository, standard_table
from app.schemas.artifact import ArtifactReference

_table = standard_table("artifacts", metadata)


class ArtifactRepository(BaseJsonRepository[ArtifactReference]):
    """Persists and resolves ``ArtifactReference`` records."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        super().__init__(
            session_factory,
            _table,
            serialize=lambda model: model.model_dump(mode="json"),
            deserialize=lambda doc: ArtifactReference.model_validate(doc),
        )

    async def register(self, tenant_id: str, artifact: ArtifactReference) -> None:
        await self.save(artifact.artifact_id, tenant_id, artifact)

    async def resolve(self, artifact_id: str) -> ArtifactReference:
        """Return the artifact for ``artifact_id``, raising if it does not exist."""

        return await self.require(artifact_id)