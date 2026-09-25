from __future__ import annotations

import re
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.exceptions import RepositoryError
from app.persistence.database import metadata
from app.persistence.repositories.base import BaseJsonRepository, standard_table
from app.schemas.artifact import ArtifactReference

_table = standard_table("artifacts", metadata)
_SHA256_HEX_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")


class ArtifactRepository(BaseJsonRepository[ArtifactReference]):
    """Persists and resolves immutable ``ArtifactReference`` records."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        super().__init__(
            session_factory,
            _table,
            serialize=lambda model: model.model_dump(mode="json"),
            deserialize=lambda doc: ArtifactReference.model_validate(doc),
        )

    async def register(
        self,
        tenant_id: str,
        artifact: ArtifactReference,
        *,
        session: AsyncSession | None = None,
    ) -> None:
        """Register an immutable deliverable reference under ``tenant_id``."""
        if not tenant_id or not isinstance(tenant_id, str) or not tenant_id.strip():
            raise RepositoryError("Tenant ID cannot be empty.")
        if not artifact.artifact_id or not isinstance(artifact.artifact_id, str) or not artifact.artifact_id.strip():
            raise RepositoryError("Artifact ID cannot be empty.")
        if not artifact.content_hash or not _SHA256_HEX_PATTERN.match(artifact.content_hash):
            raise RepositoryError(
                f"Invalid artifact content_hash '{artifact.content_hash}'; must be 64-char SHA-256 hex digest."
            )

        # Idempotent write-once check
        existing = await self.get(artifact.artifact_id, tenant_id=tenant_id, session=session)
        if existing is not None:
            if existing.content_hash == artifact.content_hash:
                return  # Idempotent registration of identical artifact
            raise RepositoryError(
                f"Artifact '{artifact.artifact_id}' already exists and is immutable. Overwrite forbidden."
            )

        # Ensure tenant_id in artifact matches
        if artifact.tenant_id is None:
            artifact.tenant_id = tenant_id
        elif artifact.tenant_id != tenant_id:
            raise RepositoryError(
                f"Artifact tenant mismatch: '{artifact.tenant_id}' != '{tenant_id}'."
            )

        await self.save(artifact.artifact_id, tenant_id, artifact, session=session)

    async def resolve(
        self,
        artifact_id: str,
        *,
        tenant_id: str | None = None,
        session: AsyncSession | None = None,
    ) -> ArtifactReference:
        """Return the artifact for ``artifact_id``, raising if it does not exist."""
        return await self.require(artifact_id, tenant_id=tenant_id, session=session)

    async def resolve_by_hash(
        self,
        content_hash: str,
        tenant_id: str | None = None,
        *,
        session: AsyncSession | None = None,
    ) -> ArtifactReference | None:
        """Find an artifact matching a SHA-256 cryptographic hash within tenant scope.

        Never treats content_hash alone as cross-tenant authorization.
        """
        if not content_hash or not isinstance(content_hash, str) or not content_hash.strip():
            return None

        stmt = select(self._table.c.document)
        if tenant_id is not None:
            stmt = stmt.where(self._table.c.tenant_id == tenant_id)

        if session is not None:
            rows = await session.execute(stmt)
            raw_docs = [doc for (doc,) in rows.all()]
        else:
            if self._session_factory is None:
                return None
            async with self._session_factory() as local_session:
                rows = await local_session.execute(stmt)
                raw_docs = [doc for (doc,) in rows.all()]

        for doc in raw_docs:
            if isinstance(doc, dict):
                art = ArtifactReference.model_validate(doc)
                if art.content_hash == content_hash:
                    # Enforce tenant isolation defense-in-depth
                    if tenant_id is not None and art.tenant_id != tenant_id:
                        continue
                    return art
        return None

    async def list_by_tenant(
        self,
        tenant_id: str,
        deliverable_type: str | None = None,
        *,
        session: AsyncSession | None = None,
    ) -> list[ArtifactReference]:
        """Return all artifacts for ``tenant_id``, optionally filtered by ``deliverable_type``."""
        artifacts = await super().list_by_tenant(tenant_id, session=session)
        if deliverable_type is not None:
            artifacts = [a for a in artifacts if a.deliverable_type == deliverable_type]
        return artifacts