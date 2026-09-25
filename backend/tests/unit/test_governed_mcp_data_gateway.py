"""Unit tests for the Governed MCP Data Gateway (Layer 3 - MCP_DATA)."""

from __future__ import annotations

import pytest

from app.core.exceptions import AuthorizationError, PolicyViolationError
from app.mcp.data_gateway import DataGateway
from app.persistence.repositories.artifact import ArtifactReference
from app.persistence.repositories.memory import MemoryRecord
from app.schemas.governance import Directive, RiskLevel, TenantScope
from app.schemas.telemetry import TelemetryEvent, TelemetryEventType
from app.security.authorization_boundary import AuthorizationBoundary, CallerIdentity
from tests.conftest import FakeVectorRepository


class _FakeMemoryRepository:
    def __init__(self) -> None:
        self._records: dict[str, list[MemoryRecord]] = {}

    async def promote(self, record: MemoryRecord, min_confidence: float = 0.6) -> None:
        if record.confidence < min_confidence:
            raise ValueError("Below confidence threshold")
        self._records.setdefault(record.tenant_id, []).append(record)

    async def list_by_tenant(
        self,
        tenant_id: str,
        category: str | None = None,
        namespace: str | None = None,
    ) -> list[MemoryRecord]:
        recs = self._records.get(tenant_id, [])
        if category:
            recs = [r for r in recs if r.category == category]
        if namespace:
            recs = [r for r in recs if r.namespace == namespace]
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

    async def resolve_by_hash(self, content_hash: str, tenant_id: str | None = None) -> ArtifactReference | None:
        for art in self._artifacts.values():
            if art.content_hash == content_hash:
                return art
        return None


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


@pytest.mark.asyncio
async def test_data_gateway_cms_and_artifact_hash_and_memory_namespaces() -> None:
    from app.integrations.cms.client import CmsClient
    from app.schemas.artifact import ArtifactReference

    scope = TenantScope(tenant_id="tenant-alpha")
    caller = CallerIdentity(subject="ie", tenant_scope=scope, risk_ceiling=RiskLevel.HIGH)

    memory_repo = _FakeMemoryRepository()
    artifact_repo = _FakeArtifactRepository()
    cms_client = CmsClient()  # uses in-memory fallback

    gateway = DataGateway(
        vector_repository=FakeVectorRepository(),
        authorization_boundary=AuthorizationBoundary(),
        memory_repository=memory_repo,  # type: ignore[arg-type]
        artifact_repository=artifact_repo,  # type: ignore[arg-type]
        cms_client=cms_client,
    )

    # 1. CMS Staging through DataGateway
    await gateway.stage_cms_entry(
        caller,
        tenant_id="tenant-alpha",
        content_type="pages",
        entry_id="landing-hero",
        data={"title": "Enterprise OS", "status": "draft"},
    )
    staged_pages = await gateway.read_cms_staged(caller, tenant_id="tenant-alpha", content_type="pages")
    assert len(staged_pages) == 1
    assert staged_pages[0]["title"] == "Enterprise OS"

    # 2. Artifact Hash Resolution and Integrity Check
    test_content = b"artifact cryptographic payload"
    computed_hash = ArtifactReference.compute_hash(test_content)
    art = ArtifactReference(
        artifact_id="art-hash-1",
        content_hash=computed_hash,
        uri="enterprise://artifacts/art-hash-1",
        media_type="application/octet-stream",
        deliverable_type="evidence_dossier",
    )
    assert art.verify_integrity(test_content) is True
    assert art.verify_integrity(b"tampered payload") is False

    await gateway.register_artifact(caller, tenant_id="tenant-alpha", artifact=art)
    by_hash = await gateway.resolve_artifact_by_hash(caller, tenant_id="tenant-alpha", content_hash=computed_hash)
    assert by_hash is not None
    assert by_hash.artifact_id == "art-hash-1"

    # 3. Institutional Memory Namespace Filtering
    rule_mem = MemoryRecord(
        memory_id="mem-rule-1",
        tenant_id="tenant-alpha",
        category="brand_rules",
        namespace="brand_rules",
        statement="Always use active voice",
        confidence=0.95,
    )
    heuristic_mem = MemoryRecord(
        memory_id="mem-heur-1",
        tenant_id="tenant-alpha",
        category="heuristics",
        namespace="attribution_heuristics",
        statement="Weight first-touch 40%",
        confidence=0.85,
    )
    await gateway.promote_memory(caller, tenant_id="tenant-alpha", record=rule_mem)
    await gateway.promote_memory(caller, tenant_id="tenant-alpha", record=heuristic_mem)

    brand_rules = await gateway.query_memory(caller, tenant_id="tenant-alpha", namespace="brand_rules")
    assert len(brand_rules) == 1
    assert brand_rules[0].memory_id == "mem-rule-1"

    heuristics = await gateway.query_memory(caller, tenant_id="tenant-alpha", namespace="attribution_heuristics")
    assert len(heuristics) == 1
    assert heuristics[0].memory_id == "mem-heur-1"


class _FakeOperationalRepository:
    def __init__(self) -> None:
        self._directives: dict[str, Directive] = {}

    async def save_directive(self, directive: Directive) -> None:
        self._directives[directive.directive_id] = directive

    async def require(self, directive_id: str) -> Directive:
        if directive_id not in self._directives:
            raise KeyError(directive_id)
        return self._directives[directive_id]


class _FakeTelemetryRepository:
    def __init__(self) -> None:
        self._events: list[TelemetryEvent] = []

    async def record(self, event: TelemetryEvent) -> None:
        self._events.append(event)

    async def list_by_type(self, tenant_id: str, event_type: str) -> list[TelemetryEvent]:
        return [e for e in self._events if e.tenant_id == tenant_id and e.event_type.value == event_type]

    async def list_all(self, tenant_id: str) -> list[TelemetryEvent]:
        return [e for e in self._events if e.tenant_id == tenant_id]


@pytest.mark.asyncio
async def test_data_gateway_rejects_direct_worker_access_across_all_endpoints() -> None:
    from app.integrations.cms.client import CmsClient
    from datetime import UTC, datetime

    scope = TenantScope(tenant_id="tenant-alpha")
    worker_caller = CallerIdentity(subject="W_DEV", tenant_scope=scope, risk_ceiling=RiskLevel.MEDIUM)
    specialist_caller = CallerIdentity(subject="S_ATTR", tenant_scope=scope, risk_ceiling=RiskLevel.MEDIUM)

    gateway = DataGateway(
        vector_repository=FakeVectorRepository(),
        authorization_boundary=AuthorizationBoundary(),
        memory_repository=_FakeMemoryRepository(),  # type: ignore[arg-type]
        artifact_repository=_FakeArtifactRepository(),  # type: ignore[arg-type]
        cms_client=CmsClient(),
        operational_repository=_FakeOperationalRepository(),  # type: ignore[arg-type]
        telemetry_repository=_FakeTelemetryRepository(),  # type: ignore[arg-type]
    )

    for caller in (worker_caller, specialist_caller):
        # 1. query / ingest
        with pytest.raises(PolicyViolationError, match="Direct worker enterprise-store access forbidden"):
            await gateway.query(caller, tenant_id="tenant-alpha", query="test")
        with pytest.raises(PolicyViolationError, match="Direct worker enterprise-store access forbidden"):
            await gateway.ingest(caller, tenant_id="tenant-alpha", doc_id="d1", text="t", source="s")

        # 2. memory query
        with pytest.raises(PolicyViolationError, match="Direct worker enterprise-store access forbidden"):
            await gateway.query_memory(caller, tenant_id="tenant-alpha")

        # 3. artifact read / write
        with pytest.raises(PolicyViolationError, match="Direct worker enterprise-store access forbidden"):
            await gateway.resolve_artifact(caller, tenant_id="tenant-alpha", artifact_id="art-1")
        with pytest.raises(PolicyViolationError, match="Direct worker enterprise-store access forbidden"):
            await gateway.resolve_artifact_by_hash(caller, tenant_id="tenant-alpha", content_hash="hash1")
        art = ArtifactReference(
            artifact_id="art-2",
            content_hash="hash2",
            uri="enterprise://artifacts/art-2",
            media_type="application/json",
            deliverable_type="evidence_dossier",
        )
        with pytest.raises(PolicyViolationError, match="Direct worker enterprise-store access forbidden"):
            await gateway.register_artifact(caller, tenant_id="tenant-alpha", artifact=art)

        # 4. CMS read / stage / apply
        with pytest.raises(PolicyViolationError, match="Direct worker enterprise-store access forbidden"):
            await gateway.read_cms_staged(caller, tenant_id="tenant-alpha", content_type="pages")
        with pytest.raises(PolicyViolationError, match="Direct worker enterprise-store access forbidden"):
            await gateway.stage_cms_entry(caller, tenant_id="tenant-alpha", content_type="pages", entry_id="e1", data={})
        with pytest.raises(PolicyViolationError, match="Direct worker enterprise-store access forbidden"):
            await gateway.apply_cms_changes(caller, tenant_id="tenant-alpha", content_type="pages", entry_id="e1", diff={})

        # 5. Directives save / get
        dir_obj = Directive(
            directive_id="dir-1",
            tenant_id="tenant-alpha",
            title="test",
            objective="test",
            budget_cap=100.0,
            scope=scope,
        )
        with pytest.raises(PolicyViolationError, match="Direct worker enterprise-store access forbidden"):
            await gateway.save_directive(caller, tenant_id="tenant-alpha", directive=dir_obj)
        with pytest.raises(PolicyViolationError, match="Direct worker enterprise-store access forbidden"):
            await gateway.get_directive(caller, tenant_id="tenant-alpha", directive_id="dir-1")

        # 6. Telemetry write / read
        tel_ev = TelemetryEvent(
            event_id="evt-1",
            tenant_id="tenant-alpha",
            event_type=TelemetryEventType.ROAS,
            channel="meta",
            occurred_at=datetime.now(UTC),
            metrics={"roas": 2.5},
        )
        with pytest.raises(PolicyViolationError, match="Direct worker enterprise-store access forbidden"):
            await gateway.record_telemetry(caller, tenant_id="tenant-alpha", event=tel_ev)
        with pytest.raises(PolicyViolationError, match="Direct worker enterprise-store access forbidden"):
            await gateway.list_telemetry(caller, tenant_id="tenant-alpha")


@pytest.mark.asyncio
async def test_data_gateway_list_telemetry_governed_read() -> None:
    from datetime import UTC, datetime

    scope = TenantScope(tenant_id="tenant-alpha")
    caller = CallerIdentity(subject="intelligence_engine", tenant_scope=scope, risk_ceiling=RiskLevel.LOW)

    tel_repo = _FakeTelemetryRepository()
    gateway = DataGateway(
        vector_repository=FakeVectorRepository(),
        authorization_boundary=AuthorizationBoundary(),
        telemetry_repository=tel_repo,  # type: ignore[arg-type]
    )

    ev = TelemetryEvent(
        event_id="evt-100",
        tenant_id="tenant-alpha",
        event_type=TelemetryEventType.ROAS,
        channel="meta",
        occurred_at=datetime.now(UTC),
        metrics={"roas": 4.1},
    )
    await gateway.record_telemetry(caller, tenant_id="tenant-alpha", event=ev)

    results = await gateway.list_telemetry(caller, tenant_id="tenant-alpha", event_type=TelemetryEventType.ROAS.value)
    assert len(results) == 1
    assert results[0].metrics["roas"] == 4.1

