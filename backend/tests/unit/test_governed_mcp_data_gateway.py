"""Unit tests for the Governed MCP Data Gateway (Layer 3 - MCP_DATA)."""

from __future__ import annotations

import pytest

from app.core.exceptions import AuthorizationError
from app.mcp.data_gateway import DataGateway
from app.persistence.repositories.artifact import ArtifactReference
from app.persistence.repositories.memory import MemoryRecord
from app.schemas.governance import Directive, RiskLevel, TenantScope
from app.security.authorization_boundary import AuthorizationBoundary, CallerIdentity
from tests.conftest import FakeVectorRepository


class _FakeMemoryRepository:
    def __init__(self) -> None:
        self._records: dict[str, list[MemoryRecord]] = {}

    async def promote(self, record: MemoryRecord) -> None:
        self._records.setdefault(record.tenant_id, []).append(record)

    async def list_by_tenant(self, tenant_id: str, category: str | None = None) -> list[MemoryRecord]:
        recs = self._records.get(tenant_id, [])
        if category:
            return [r for r in recs if r.category == category]
        return recs


class _FakeArtifactRepository:
    def __init__(self) -> None:
        self._artifacts: dict[str, ArtifactReference] = {}

    async def register(self, tenant_id: str, artifact: ArtifactReference) -> None:
        self._artifacts[artifact.artifact_id] = artifact

    async def resolve(self, artifact_id: str) -> ArtifactReference:
        if artifact_id not in self._artifacts:
            raise KeyError(f"Artifact {artifact_id} not found")
        return self._artifacts[artifact_id]


@pytest.mark.asyncio
async def test_data_gateway_allows_tenant_scoped_operations() -> None:
    scope = TenantScope(tenant_id="tenant-alpha", brand_ids=["alpha-brand"])
    caller = CallerIdentity(subject="ie", tenant_scope=scope, risk_ceiling=RiskLevel.HIGH)

    vector_repo = FakeVectorRepository()
    memory_repo = _FakeMemoryRepository()
    artifact_repo = _FakeArtifactRepository()

    gateway = DataGateway(
        vector_repository=vector_repo,
        authorization_boundary=AuthorizationBoundary(),
        memory_repository=memory_repo,  # type: ignore[arg-type]
        artifact_repository=artifact_repo,  # type: ignore[arg-type]
    )

    # 1. Vector ingest and query
    await gateway.ingest(caller, tenant_id="tenant-alpha", doc_id="doc-1", text="brand guidelines", source="seed")
    results = await gateway.query(caller, tenant_id="tenant-alpha", query="brand", top_k=5)
    assert len(results) == 1
    assert results[0]["text"] == "brand guidelines"

    # 2. Institutional Memory promotion and query
    mem_record = MemoryRecord(
        memory_id="mem-1",
        tenant_id="tenant-alpha",
        category="brand_voice",
        statement="Punchy and direct",
        confidence=0.9,
    )
    await gateway.promote_memory(caller, tenant_id="tenant-alpha", record=mem_record)
    recs = await gateway.query_memory(caller, tenant_id="tenant-alpha", category="brand_voice")
    assert len(recs) == 1
    assert recs[0].statement == "Punchy and direct"

    # 3. Artifact Registry registration and resolution
    art_ref = ArtifactReference(
        artifact_id="art-1",
        content_hash="abc123hash",
        uri="enterprise://artifacts/art-1",
        media_type="application/json",
        deliverable_type="copy_pack",
    )
    await gateway.register_artifact(caller, tenant_id="tenant-alpha", artifact=art_ref)
    resolved = await gateway.resolve_artifact(caller, tenant_id="tenant-alpha", artifact_id="art-1")
    assert resolved is not None
    assert resolved.deliverable_type == "copy_pack"


@pytest.mark.asyncio
async def test_data_gateway_rejects_cross_tenant_access() -> None:
    scope = TenantScope(tenant_id="tenant-alpha")
    caller = CallerIdentity(subject="ie", tenant_scope=scope, risk_ceiling=RiskLevel.HIGH)

    gateway = DataGateway(
        vector_repository=FakeVectorRepository(),
        authorization_boundary=AuthorizationBoundary(),
    )

    with pytest.raises(AuthorizationError):
        await gateway.query(caller, tenant_id="tenant-bravo", query="secret data")

    with pytest.raises(AuthorizationError):
        await gateway.ingest(
            caller, tenant_id="tenant-bravo", doc_id="doc-x", text="injected", source="hack"
        )
