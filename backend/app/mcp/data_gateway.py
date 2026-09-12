"""Governed CRUD facade between Agentic RAG and systems of record.

The data gateway is the governed path (MCP_DATA) by which the Agentic RAG
service, Intelligence Engine, and orchestration layers read from or write to
the systems of record:
- Central Enterprise Database (CDB: relational/operational & vector)
- Headless CMS & Content Store (CMS: content models & staging)
- Institutional Memory Store (MEM: brand books & learned heuristics)
- Artifact & Evidence Registry (ART: content-addressable deliverables)

Enforces tenant authorization on every call before delegating to a repository.
"""

from __future__ import annotations

from typing import Any

from app.integrations.cms.client import CmsClient
from app.persistence.repositories.artifact import ArtifactReference, ArtifactRepository
from app.persistence.repositories.memory import MemoryRecord, MemoryRepository
from app.persistence.repositories.operational import OperationalRepository
from app.persistence.repositories.vector import VectorRepository
from app.schemas.governance import Directive, RiskLevel, TenantScope
from app.security.authorization_boundary import AuthorizationBoundary, CallerIdentity


class DataGateway:
    """Authorizes and executes reads/writes against CDB, CMS, MEM, and ART systems of record."""

    def __init__(
        self,
        vector_repository: VectorRepository,
        authorization_boundary: AuthorizationBoundary | None = None,
        *,
        operational_repository: OperationalRepository | None = None,
        memory_repository: MemoryRepository | None = None,
        artifact_repository: ArtifactRepository | None = None,
        cms_client: CmsClient | None = None,
    ) -> None:
        self._vector_repository = vector_repository
        self._authorization_boundary = authorization_boundary or AuthorizationBoundary()
        self._operational_repository = operational_repository
        self._memory_repository = memory_repository
        self._artifact_repository = artifact_repository
        self._cms_client = cms_client

    def _authorize_tenant(
        self, caller: CallerIdentity, tenant_id: str, risk: RiskLevel = RiskLevel.LOW
    ) -> None:
        self._authorization_boundary.authorize(
            caller,
            requested_scope=TenantScope(tenant_id=tenant_id),
            requested_risk=risk,
        )

    # -- Vector / Knowledge Retrieval & Ingestion --
    async def query(
        self, caller: CallerIdentity, *, tenant_id: str, query: str, top_k: int = 10
    ) -> list[dict[str, Any]]:
        """Authorize and execute a similarity-search read."""
        self._authorize_tenant(caller, tenant_id)
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
        self._authorize_tenant(caller, tenant_id)
        await self._vector_repository.index_document(
            doc_id=doc_id, tenant_id=tenant_id, text=text, source=source
        )

    # -- Institutional Memory Store (MEM) --
    async def query_memory(
        self, caller: CallerIdentity, *, tenant_id: str, category: str | None = None
    ) -> list[MemoryRecord]:
        """Authorize and query institutional memory records."""
        self._authorize_tenant(caller, tenant_id)
        if self._memory_repository is None:
            return []
        if hasattr(self._memory_repository, "list_by_tenant"):
            return await self._memory_repository.list_by_tenant(tenant_id, category=category)
        return []

    async def promote_memory(
        self, caller: CallerIdentity, *, tenant_id: str, record: MemoryRecord
    ) -> None:
        """Authorize and promote a validated learning delta into institutional memory."""
        self._authorize_tenant(caller, tenant_id, risk=RiskLevel.MEDIUM)
        if self._memory_repository is not None:
            await self._memory_repository.promote(record)

    # -- Artifact & Evidence Registry (ART) --
    async def resolve_artifact(
        self, caller: CallerIdentity, *, tenant_id: str, artifact_id: str
    ) -> ArtifactReference | None:
        """Authorize and resolve a deliverable/evidence artifact by UUID/hash."""
        self._authorize_tenant(caller, tenant_id)
        if self._artifact_repository is None:
            return None
        return await self._artifact_repository.resolve(artifact_id)

    async def register_artifact(
        self, caller: CallerIdentity, *, tenant_id: str, artifact: ArtifactReference
    ) -> None:
        """Authorize and register an immutable deliverable in the artifact registry."""
        self._authorize_tenant(caller, tenant_id)
        if self._artifact_repository is not None:
            await self._artifact_repository.register(tenant_id, artifact)

    # -- Headless CMS Staging (CMS) --
    async def read_cms_staged(
        self, caller: CallerIdentity, *, tenant_id: str, content_type: str
    ) -> list[dict[str, str]]:
        """Authorize and read staged CMS models."""
        self._authorize_tenant(caller, tenant_id)
        if self._cms_client is None:
            return []
        return await self._cms_client.read_staged(content_type)

    async def apply_cms_changes(
        self,
        caller: CallerIdentity,
        *,
        tenant_id: str,
        content_type: str,
        entry_id: str,
        diff: dict[str, str],
    ) -> dict[str, str]:
        """Authorize and apply schema/content diffs to staged CMS entries."""
        self._authorize_tenant(caller, tenant_id, risk=RiskLevel.MEDIUM)
        if self._cms_client is None:
            return {"status": "cms_unconfigured"}
        return await self._cms_client.apply_changes(content_type, entry_id, diff)

    # -- Central Operational DB (CDB) --
    async def save_directive(
        self, caller: CallerIdentity, *, tenant_id: str, directive: Directive
    ) -> None:
        """Authorize and persist an operational directive."""
        self._authorize_tenant(caller, tenant_id)
        if self._operational_repository is not None:
            await self._operational_repository.save_directive(directive)

    async def get_directive(
        self, caller: CallerIdentity, *, tenant_id: str, directive_id: str
    ) -> Directive | None:
        """Authorize and load an operational directive."""
        self._authorize_tenant(caller, tenant_id)
        if self._operational_repository is not None:
            return await self._operational_repository.require(directive_id)
        return None