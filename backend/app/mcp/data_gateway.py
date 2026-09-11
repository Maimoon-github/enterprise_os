"""Governed CRUD facade between Agentic RAG and systems of record.

The data gateway is the only path by which the Agentic RAG service reads
from or writes to persistence; it enforces tenant authorization on every
call before delegating to a repository.
"""

from __future__ import annotations

from typing import Any

from app.persistence.repositories.vector import VectorRepository
from app.schemas.governance import RiskLevel, TenantScope
from app.security.authorization_boundary import AuthorizationBoundary, CallerIdentity


class DataGateway:
    """Authorizes and executes reads/writes against the vector system of record."""

    def __init__(
        self,
        vector_repository: VectorRepository,
        authorization_boundary: AuthorizationBoundary | None = None,
    ) -> None:
        self._vector_repository = vector_repository
        self._authorization_boundary = authorization_boundary or AuthorizationBoundary()

    async def query(
        self, caller: CallerIdentity, *, tenant_id: str, query: str, top_k: int = 10
    ) -> list[dict[str, Any]]:
        """Authorize and execute a similarity-search read."""

        self._authorization_boundary.authorize(
            caller,
            requested_scope=TenantScope(tenant_id=tenant_id),
            requested_risk=RiskLevel.LOW,
        )
        return await self._vector_repository.similarity_search(
            tenant_id=tenant_id, query=query, top_k=top_k
        )

    async def ingest(
        self,
        caller: CallerIdentity,
        *,
        tenant_id: str,
        doc_id: str,
        text: str,
        source: str,
    ) -> None:
        """Authorize and execute a document ingestion write."""

        self._authorization_boundary.authorize(
            caller,
            requested_scope=TenantScope(tenant_id=tenant_id),
            requested_risk=RiskLevel.LOW,
        )
        await self._vector_repository.index_document(
            doc_id=doc_id, tenant_id=tenant_id, text=text, source=source
        )