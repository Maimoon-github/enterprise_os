"""Unit tests for L4-05: CMS & MCP-Governed Multi-Store Access.

Verifies:
- DataGateway as single facade across CDB, CMS, MEM, ART.
- Strict rejection of Worker, Specialist, Sub-Agent, and Sandbox callers.
- Cross-tenant denial and tenant bounding across all stores.
- Capability gating and delegation enforcement.
- CMS idempotency and version references.
- Agentic RAG exclusive routing through DataGateway (zero direct repo dependency).
- Transaction session propagation and provenance audit recording.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import AuthorizationError, PolicyViolationError
from app.integrations.artifact_store.client import ArtifactStoreClient
from app.integrations.cms.client import CmsClient
from app.mcp.data_gateway import DataGateway
from app.persistence.repositories.artifact import ArtifactReference
from app.persistence.repositories.memory import MemoryRecord
from app.schemas.governance import Directive, RiskLevel, TenantScope
from app.schemas.telemetry import TelemetryEvent, TelemetryEventType
from app.security.authorization_boundary import AuthorizationBoundary, CallerIdentity
from app.services.rag.controller import RagController
from app.services.rag.freshness import FreshnessPolicy
from app.services.rag.hybrid_retriever import HybridRetriever
from app.services.rag.schema_validator import SchemaValidator


class _MockVectorRepo:
    def __init__(self) -> None:
        self.indexed: list[dict[str, Any]] = []

    async def similarity_search(self, *, tenant_id: str, query: str, top_k: int = 10, **kwargs: Any) -> list[dict[str, Any]]:
        return [{
            "doc_id": "d1",
            "tenant_id": tenant_id,
            "text": f"match for {query}",
            "source": "seed",
            "retrieved_at": datetime.now(UTC).isoformat(),
            "score": 0.95,
        }]

    async def index_document(self, *, doc_id: str, tenant_id: str, text: str, source: str, **kwargs: Any) -> None:
        self.indexed.append({"doc_id": doc_id, "tenant_id": tenant_id, "text": text, "source": source})


class _MockMemoryRepo:
    def __init__(self) -> None:
        self.records: dict[str, list[MemoryRecord]] = {}

    async def promote(self, record: MemoryRecord, session: Any = None) -> None:
        self.records.setdefault(record.tenant_id, []).append(record)

    async def list_by_tenant(self, tenant_id: str, category: str | None = None, namespace: str | None = None) -> list[MemoryRecord]:
        recs = self.records.get(tenant_id, [])
        if category:
            recs = [r for r in recs if r.category == category]
        return recs


class _MockArtifactRepo:
    def __init__(self) -> None:
        self.registry: dict[str, ArtifactReference] = {}

    async def register(self, tenant_id: str, artifact: ArtifactReference, session: Any = None) -> None:
        self.registry[artifact.artifact_id] = artifact

    async def resolve(self, artifact_id: str, tenant_id: str | None = None) -> ArtifactReference:
        if artifact_id not in self.registry:
            raise KeyError(f"Artifact {artifact_id} not found")
        art = self.registry[artifact_id]
        if tenant_id and art.tenant_id != tenant_id:
            raise KeyError(f"Artifact {artifact_id} not accessible for tenant {tenant_id}")
        return art

    async def resolve_by_hash(self, content_hash: str, tenant_id: str | None = None) -> ArtifactReference | None:
        for art in self.registry.values():
            if art.content_hash == content_hash and (tenant_id is None or art.tenant_id == tenant_id):
                return art
        return None


class _MockOperationalRepo:
    def __init__(self) -> None:
        self.directives: dict[str, Directive] = {}

    async def save_directive(self, directive: Directive, session: Any = None) -> None:
        self.directives[directive.directive_id] = directive

    async def require(self, directive_id: str, session: Any = None) -> Directive:
        if directive_id not in self.directives:
            raise KeyError(f"Directive {directive_id} not found")
        return self.directives[directive_id]


class _MockTelemetryRepo:
    def __init__(self) -> None:
        self.events: list[TelemetryEvent] = []

    async def record(self, event: TelemetryEvent, session: Any = None) -> None:
        self.events.append(event)

    async def list_all(self, tenant_id: str, session: Any = None) -> list[TelemetryEvent]:
        return [e for e in self.events if e.tenant_id == tenant_id]


@pytest.fixture
def test_setup(tmp_path):
    scope = TenantScope(tenant_id="tenant-alpha")
    authorized_caller = CallerIdentity(subject="intelligence_engine", tenant_scope=scope, risk_ceiling=RiskLevel.HIGH)

    vector_repo = _MockVectorRepo()
    memory_repo = _MockMemoryRepo()
    artifact_repo = _MockArtifactRepo()
    operational_repo = _MockOperationalRepo()
    telemetry_repo = _MockTelemetryRepo()
    cms_client = CmsClient()
    artifact_store = ArtifactStoreClient(root_prefix=str(tmp_path / "artifacts"))
    mock_prov = AsyncMock()

    gateway = DataGateway(
        vector_repo,  # type: ignore[arg-type]
        AuthorizationBoundary(),
        operational_repository=operational_repo,  # type: ignore[arg-type]
        memory_repository=memory_repo,  # type: ignore[arg-type]
        artifact_repository=artifact_repo,  # type: ignore[arg-type]
        artifact_store=artifact_store,
        cms_client=cms_client,
        telemetry_repository=telemetry_repo,  # type: ignore[arg-type]
        provenance_recorder=mock_prov,
    )

    return {
        "caller": authorized_caller,
        "gateway": gateway,
        "cms": cms_client,
        "artifact_store": artifact_store,
        "mock_prov": mock_prov,
        "vector_repo": vector_repo,
        "memory_repo": memory_repo,
        "artifact_repo": artifact_repo,
        "operational_repo": operational_repo,
        "telemetry_repo": telemetry_repo,
    }


@pytest.mark.asyncio
async def test_data_gateway_mediates_all_four_stores_cdb_cms_mem_art(test_setup) -> None:
    gateway: DataGateway = test_setup["gateway"]
    caller: CallerIdentity = test_setup["caller"]
    tenant_id = "tenant-alpha"

    # 1. CDB: Vector query and ingest
    await gateway.ingest(caller, tenant_id=tenant_id, doc_id="doc-1", text="brand tone guidelines", source="seed")
    vec_results = await gateway.query(caller, tenant_id=tenant_id, query="brand tone")
    assert len(vec_results) == 1
    assert "brand tone" in vec_results[0]["text"]

    # 2. CDB: Operational Directive
    directive = Directive(
        directive_id="dir-101",
        tenant_id=tenant_id,
        objective="Maximize ROAS",
        budget_cap=50000.0,
        scope=caller.tenant_scope,
    )
    await gateway.save_directive(caller, tenant_id=tenant_id, directive=directive)
    loaded_dir = await gateway.get_directive(caller, tenant_id=tenant_id, directive_id="dir-101")
    assert loaded_dir is not None
    assert loaded_dir.objective == "Maximize ROAS"

    # 3. CDB: Telemetry
    telem = TelemetryEvent(
        event_id="tel-1",
        tenant_id=tenant_id,
        event_type=TelemetryEventType.ROAS,
        channel="meta",
        occurred_at=datetime.now(UTC),
        metrics={"roas": 3.8},
    )
    await gateway.record_telemetry(caller, tenant_id=tenant_id, event=telem)
    events = await gateway.list_telemetry(caller, tenant_id=tenant_id)
    assert len(events) == 1
    assert events[0].metrics["roas"] == 3.8

    # 4. MEM: Promotion and Query
    mem = MemoryRecord(
        memory_id="mem-101",
        tenant_id=tenant_id,
        category="rules",
        statement="Use high-contrast CTAs",
        confidence=0.92,
        logical_id="cta-rule",
        version=1,
    )
    await gateway.promote_memory(caller, tenant_id=tenant_id, record=mem)
    mems = await gateway.query_memory(caller, tenant_id=tenant_id, category="rules")
    assert len(mems) == 1
    assert mems[0].statement == "Use high-contrast CTAs"

    # 5. ART: Content addressed storage and retrieval
    art_content = b"PDF artifact payload content"
    art_ref = await gateway.store_and_register_artifact(
        caller, tenant_id=tenant_id, content=art_content, deliverable_type="evidence_dossier", media_type="application/pdf"
    )
    assert art_ref.tenant_id == tenant_id
    payload = await gateway.get_artifact_payload(caller, tenant_id=tenant_id, artifact_id=art_ref.artifact_id)
    assert payload == art_content

    # 6. CMS: Stage, Publish, Read Published, Rollback
    await gateway.stage_cms_entry(
        caller, tenant_id=tenant_id, content_type="pages", entry_id="home-page", data={"headline": "Welcome v1"}
    )
    pub_res = await gateway.publish_cms_entry(
        caller, tenant_id=tenant_id, content_type="pages", entry_id="home-page", version="v1.0"
    )
    assert pub_res["status"] == "published"
    assert "version_reference" in pub_res

    published_items = await gateway.read_cms_published(caller, tenant_id=tenant_id, content_type="pages", entry_id="home-page")
    assert len(published_items) == 1
    assert published_items[0]["headline"] == "Welcome v1"


@pytest.mark.asyncio
async def test_data_gateway_rejects_worker_subagent_and_sandbox_identities(test_setup) -> None:
    gateway: DataGateway = test_setup["gateway"]
    scope = TenantScope(tenant_id="tenant-alpha")

    forbidden_subjects = [
        "W_DEV",
        "W_CREAT",
        "S_ALLOC",
        "worker_content",
        "specialist_quality",
        "subagent_research",
        "sub_agent_copy",
        "sandbox_runner",
    ]

    for subj in forbidden_subjects:
        bad_caller = CallerIdentity(subject=subj, tenant_scope=scope, risk_ceiling=RiskLevel.HIGH)

        with pytest.raises((PolicyViolationError, AuthorizationError)):
            await gateway.query(bad_caller, tenant_id="tenant-alpha", query="test")

        with pytest.raises((PolicyViolationError, AuthorizationError)):
            await gateway.stage_cms_entry(bad_caller, tenant_id="tenant-alpha", content_type="pages", entry_id="p1", data={})

        with pytest.raises((PolicyViolationError, AuthorizationError)):
            await gateway.get_directive(bad_caller, tenant_id="tenant-alpha", directive_id="dir-1")

        with pytest.raises((PolicyViolationError, AuthorizationError)):
            await gateway.query_memory(bad_caller, tenant_id="tenant-alpha")


@pytest.mark.asyncio
async def test_data_gateway_rejects_cross_tenant_access_across_all_facades(test_setup) -> None:
    gateway: DataGateway = test_setup["gateway"]
    alpha_caller: CallerIdentity = test_setup["caller"]  # scoped to tenant-alpha
    beta_tenant = "tenant-beta"

    with pytest.raises(AuthorizationError):
        await gateway.query(alpha_caller, tenant_id=beta_tenant, query="test")

    with pytest.raises(AuthorizationError):
        await gateway.ingest(alpha_caller, tenant_id=beta_tenant, doc_id="d2", text="test", source="s")

    with pytest.raises(AuthorizationError):
        await gateway.query_memory(alpha_caller, tenant_id=beta_tenant)

    with pytest.raises(AuthorizationError):
        await gateway.read_cms_staged(alpha_caller, tenant_id=beta_tenant, content_type="pages")

    with pytest.raises(AuthorizationError):
        await gateway.stage_cms_entry(alpha_caller, tenant_id=beta_tenant, content_type="pages", entry_id="e1", data={})

    with pytest.raises(AuthorizationError):
        await gateway.publish_cms_entry(alpha_caller, tenant_id=beta_tenant, content_type="pages", entry_id="e1")

    with pytest.raises(AuthorizationError):
        await gateway.list_telemetry(alpha_caller, tenant_id=beta_tenant)


@pytest.mark.asyncio
async def test_data_gateway_enforces_capability_attenuation_and_empty_tenant(test_setup) -> None:
    gateway: DataGateway = test_setup["gateway"]
    scope = TenantScope(tenant_id="tenant-alpha")

    # Read-only caller attempting write operations
    read_only_caller = CallerIdentity(
        subject="intelligence_engine",
        tenant_scope=scope,
        risk_ceiling=RiskLevel.HIGH,
        allowed_capabilities=frozenset({"mcp_data_read"}),
    )

    with pytest.raises(AuthorizationError, match="lacks capability"):
        await gateway.ingest(read_only_caller, tenant_id="tenant-alpha", doc_id="d1", text="t", source="s")

    with pytest.raises(AuthorizationError, match="lacks capability"):
        await gateway.stage_cms_entry(read_only_caller, tenant_id="tenant-alpha", content_type="pages", entry_id="p1", data={})

    # Empty tenant fails closed
    with pytest.raises(AuthorizationError, match="Tenant ID is required"):
        await gateway.query(read_only_caller, tenant_id="", query="test")


@pytest.mark.asyncio
async def test_cms_client_idempotency_and_version_reference(test_setup) -> None:
    cms: CmsClient = test_setup["cms"]
    tenant_id = "tenant-alpha"
    idem_key = "deploy-request-999"

    # Stage with idempotency key
    stg1 = await cms.stage_entry("pages", "p-99", {"title": "Original"}, tenant_id=tenant_id, idempotency_key=idem_key)
    assert stg1["version_reference"] == "pages:p-99:staged"

    # Replaying with same key returns cached result
    stg2 = await cms.stage_entry("pages", "p-99", {"title": "Altered"}, tenant_id=tenant_id, idempotency_key=idem_key)
    assert stg2 == stg1

    # Publish with version reference
    pub1 = await cms.publish_entry("pages", "p-99", tenant_id=tenant_id, version="v1.2", idempotency_key="pub-99")
    assert pub1["version_reference"] == "pages:p-99:v1.2"
    assert pub1["version"] == "v1.2"

    # Replaying publish returns identical result
    pub2 = await cms.publish_entry("pages", "p-99", tenant_id=tenant_id, version="v1.2", idempotency_key="pub-99")
    assert pub2 == pub1


@pytest.mark.asyncio
async def test_rag_routes_strictly_through_data_gateway_never_direct_repo(test_setup) -> None:
    gateway: DataGateway = test_setup["gateway"]
    tenant_id = "tenant-alpha"

    # Instantiate HybridRetriever with data_gateway only (vector_repository is None)
    retriever = HybridRetriever(data_gateway=gateway)
    assert retriever._vector_repository is None

    rag_controller = RagController(retriever, FreshnessPolicy(), SchemaValidator(), data_gateway=gateway)

    # Retrieval works completely through DataGateway
    results = await rag_controller.retrieve(tenant_id=tenant_id, query="brand rules", top_k=3)
    assert len(results) == 1
    assert "match for brand rules" in results[0]["text"]
    assert results[0]["provenance_tracked"] is True

    # Ingestion works completely through DataGateway
    await rag_controller.ingest(tenant_id=tenant_id, doc_id="rag-doc-1", text="new policy", source="rag_feed")
    assert any(d["doc_id"] == "rag-doc-1" for d in test_setup["vector_repo"].indexed)


@pytest.mark.asyncio
async def test_provenance_and_transaction_session_propagation(test_setup) -> None:
    gateway: DataGateway = test_setup["gateway"]
    caller: CallerIdentity = test_setup["caller"]
    mock_prov: AsyncMock = test_setup["mock_prov"]
    tenant_id = "tenant-alpha"
    dummy_session = object()

    # Telemetry recording with session and audit
    telem = TelemetryEvent(
        event_id="tel-tx-1",
        tenant_id=tenant_id,
        event_type=TelemetryEventType.ROAS,
        channel="meta",
        occurred_at=datetime.now(UTC),
        metrics={"roas": 2.1},
    )
    await gateway.record_telemetry(caller, tenant_id=tenant_id, event=telem, session=dummy_session)
    mock_prov.record.assert_awaited()
    # Check that session was passed to provenance recorder
    assert mock_prov.record.call_args.kwargs.get("session") is dummy_session
