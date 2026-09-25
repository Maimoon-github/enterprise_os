"""Unit tests for L4-06: Provenance, Transaction Integrity & Recovery Controls.

Verifies:
- Provenance append-only semantics and cryptographic hash-chain verification (tamper evidence).
- Atomic transaction boundaries: failure during provenance forces rollback of domain mutations.
- ART failure sequencing: payload preserved as orphan on metadata failure, zero reference published.
- Orphan payload detection and non-destructive reconciliation.
- CMS staged mutation intent and result provenance capture with provider version tracking.
- Storage health aggregation without credential or sensitive data leakage.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.integrations.artifact_store.client import ArtifactStoreClient
from app.integrations.cms.client import CmsClient
from app.mcp.data_gateway import DataGateway
from app.persistence.repositories.artifact import ArtifactReference
from app.persistence.repositories.memory import MemoryRecord
from app.persistence.repositories.provenance import ProvenanceRepository
from app.schemas.governance import RiskLevel, TenantScope
from app.schemas.provenance import ProvenanceRecord
from app.security.authorization_boundary import AuthorizationBoundary, CallerIdentity
from app.services.provenance import ProvenanceRecorder
from app.services.storage_health import StorageHealthAggregator


# --- Mock Persistence Helpers ---

class _InMemoryProvenanceRepo:
    """In-memory append-only provenance store with SHA-256 hash chaining."""

    def __init__(self) -> None:
        self.records: dict[str, list[ProvenanceRecord]] = {}

    async def append(
        self,
        *,
        tenant_id: str,
        entity_id: str,
        activity: str,
        agent: str,
        record_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        w3c_prov: dict[str, Any] | None = None,
        session: Any = None,
    ) -> ProvenanceRecord:
        chain = self.records.setdefault(tenant_id, [])
        prev_hash = chain[-1].record_hash if chain else None
        occurred_at = datetime.now(UTC)

        meta_payload = str(sorted((metadata or {}).items())) + str(sorted((w3c_prov or {}).items()))
        meta_hash = hashlib.sha256(meta_payload.encode()).hexdigest()
        raw = f"{prev_hash or ''}|{entity_id}|{activity}|{agent}|{occurred_at.isoformat()}|{meta_hash}"
        record_hash = hashlib.sha256(raw.encode()).hexdigest()

        rec = ProvenanceRecord(
            record_id=record_id or str(uuid.uuid4()),
            tenant_id=tenant_id,
            entity_id=entity_id,
            activity=activity,
            agent=agent,
            occurred_at=occurred_at,
            prev_record_hash=prev_hash,
            metadata_hash=meta_hash,
            record_hash=record_hash,
            metadata=metadata or {},
            w3c_prov=w3c_prov or {},
        )
        chain.append(rec)
        return rec

    async def chain(self, tenant_id: str) -> list[ProvenanceRecord]:
        return list(self.records.get(tenant_id, []))

    def verify(self, records: list[ProvenanceRecord]) -> bool:
        prev_hash: str | None = None
        for r in records:
            meta_payload = str(sorted((r.metadata or {}).items())) + str(sorted((r.w3c_prov or {}).items()))
            meta_hash = hashlib.sha256(meta_payload.encode()).hexdigest()
            raw = f"{prev_hash or ''}|{r.entity_id}|{r.activity}|{r.agent}|{r.occurred_at.isoformat()}|{meta_hash}"
            expected = hashlib.sha256(raw.encode()).hexdigest()
            if r.record_hash != expected or r.prev_record_hash != prev_hash:
                return False
            prev_hash = r.record_hash
        return True

    async def verify_chain(self, tenant_id: str) -> bool:
        return self.verify(await self.chain(tenant_id))


class _MockArtifactRepository:
    def __init__(self) -> None:
        self.registered: dict[str, ArtifactReference] = {}

    async def register(self, tenant_id: str, ref: ArtifactReference, session: Any = None) -> None:
        if getattr(session, "should_fail_artifact_repo", False) is True:
            raise RuntimeError("Database connection lost during artifact metadata insert")
        self.registered[ref.artifact_id] = ref

    async def resolve(self, artifact_id: str, tenant_id: str | None = None) -> ArtifactReference:
        if artifact_id not in self.registered:
            raise KeyError(f"Artifact {artifact_id} not found")
        return self.registered[artifact_id]

    async def resolve_by_hash(self, content_hash: str, tenant_id: str | None = None) -> ArtifactReference | None:
        for ref in self.registered.values():
            if ref.content_hash == content_hash:
                return ref
        return None


class _MockMemoryRepository:
    def __init__(self) -> None:
        self.records: list[MemoryRecord] = []

    async def promote(self, record: MemoryRecord, session: Any = None) -> None:
        if getattr(session, "should_fail_memory_repo", False) is True:
            raise RuntimeError("Database error during memory promote")
        self.records.append(record)


class _MockVectorRepository:
    def __init__(self) -> None:
        self.docs: list[dict[str, Any]] = []

    async def similarity_search(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        return []

    async def index_document(self, *args: Any, **kwargs: Any) -> None:
        pass


# --- Tests ---

@pytest.fixture
def auth_boundary() -> AuthorizationBoundary:
    return AuthorizationBoundary()


@pytest.fixture
def test_setup(auth_boundary: AuthorizationBoundary) -> dict[str, Any]:
    prov_repo = _InMemoryProvenanceRepo()
    prov_recorder = ProvenanceRecorder(repository=prov_repo)  # type: ignore[arg-type]
    art_store = ArtifactStoreClient()
    art_repo = _MockArtifactRepository()
    mem_repo = _MockMemoryRepository()
    cms_client = CmsClient()
    vector_repo = _MockVectorRepository()

    gateway = DataGateway(
        vector_repo,  # type: ignore[arg-type]
        authorization_boundary=auth_boundary,
        artifact_store=art_store,
        artifact_repository=art_repo,  # type: ignore[arg-type]
        memory_repository=mem_repo,  # type: ignore[arg-type]
        cms_client=cms_client,
        provenance_recorder=prov_recorder,
    )

    caller = CallerIdentity(
        subject="intelligence_engine",
        tenant_scope=TenantScope(tenant_id="tenant-l406"),
        risk_ceiling=RiskLevel.HIGH,
    )

    return {
        "gateway": gateway,
        "caller": caller,
        "prov_repo": prov_repo,
        "prov_recorder": prov_recorder,
        "art_store": art_store,
        "art_repo": art_repo,
        "mem_repo": mem_repo,
        "cms_client": cms_client,
    }


@pytest.mark.asyncio
async def test_provenance_append_only_and_chain_verification(test_setup: dict[str, Any]) -> None:
    """Verify append-only progression, unbroken hash chain, and tamper detection."""
    prov_repo: _InMemoryProvenanceRepo = test_setup["prov_repo"]
    recorder: ProvenanceRecorder = test_setup["prov_recorder"]
    tenant_id = "tenant-l406"

    # Append 3 records
    r1 = await recorder.record(tenant_id=tenant_id, entity_id="e1", activity="act1", agent="agent1")
    r2 = await recorder.record(tenant_id=tenant_id, entity_id="e2", activity="act2", agent="agent2")
    r3 = await recorder.record(tenant_id=tenant_id, entity_id="e3", activity="act3", agent="agent3")

    chain = await prov_repo.chain(tenant_id)
    assert len(chain) == 3
    assert r1.prev_record_hash is None
    assert r2.prev_record_hash == r1.record_hash
    assert r3.prev_record_hash == r2.record_hash

    # Verification passes on untampered chain
    assert await prov_repo.verify_chain(tenant_id) is True

    # Simulate retroactive tampering on record 2
    tampered_record = chain[1].model_copy(update={"entity_id": "malicious_tamper"})
    tampered_chain = [chain[0], tampered_record, chain[2]]
    assert prov_repo.verify(tampered_chain) is False

    # Check that ProvenanceRepository exposes append/read only (no update or delete)
    real_repo = ProvenanceRepository(session_factory=MagicMock())
    assert hasattr(real_repo, "append")
    assert hasattr(real_repo, "chain")
    assert hasattr(real_repo, "verify_chain")
    assert not hasattr(real_repo, "update")
    assert not hasattr(real_repo, "delete")
    assert not hasattr(real_repo, "remove")


@pytest.mark.asyncio
async def test_atomic_rollback_on_provenance_failure(test_setup: dict[str, Any]) -> None:
    """Verify that failure in provenance recording re-raises and aborts transaction."""
    gateway: DataGateway = test_setup["gateway"]
    caller: CallerIdentity = test_setup["caller"]
    mem_repo: _MockMemoryRepository = test_setup["mem_repo"]
    prov_recorder: ProvenanceRecorder = test_setup["prov_recorder"]
    tenant_id = "tenant-l406"

    # Mock provenance recorder to fail on append
    prov_recorder.record = AsyncMock(side_effect=RuntimeError("WAL disk full during audit append"))

    rec = MemoryRecord(
        memory_id="mem-tx-fail-1",
        tenant_id=tenant_id,
        category="strategy",
        statement="Important strategic learning",
        confidence=0.95,
    )

    # In a transaction session, provenance failure must bubble up to force caller rollback
    mock_session = MagicMock()
    with pytest.raises(RuntimeError, match="WAL disk full during audit append"):
        await gateway.promote_memory(caller, tenant_id=tenant_id, record=rec, session=mock_session)


@pytest.mark.asyncio
async def test_art_failure_sequencing_and_orphan_preservation(test_setup: dict[str, Any]) -> None:
    """Verify ART sequence: put payload succeeds, metadata fails -> no ref published, orphan preserved."""
    gateway: DataGateway = test_setup["gateway"]
    caller: CallerIdentity = test_setup["caller"]
    art_store: ArtifactStoreClient = test_setup["art_store"]
    art_repo: _MockArtifactRepository = test_setup["art_repo"]
    tenant_id = "tenant-l406"

    payload_data = b"CRITICAL_DELIVERABLE_PAYLOAD_V1"
    expected_hash = hashlib.sha256(payload_data).hexdigest()

    # Configure session to simulate database failure during metadata insert
    failing_session = MagicMock()
    failing_session.should_fail_artifact_repo = True

    # Attempt store_and_register_artifact
    with pytest.raises(RuntimeError, match="Database connection lost during artifact metadata insert"):
        await gateway.store_and_register_artifact(
            caller,
            tenant_id=tenant_id,
            content=payload_data,
            artifact_id="art-fail-1",
            session=failing_session,
        )

    # Invariants check:
    # 1. ArtifactReference was NOT registered in repository
    assert "art-fail-1" not in art_repo.registered

    # 2. Immutable object in store was PRESERVED (orphan, not deleted or overwritten)
    assert await art_store.head(expected_hash) is not None
    assert await art_store.get(expected_hash) == payload_data

    # 3. Orphan reconciliation detects the unreferenced object
    recon = await gateway.reconcile_orphan_artifacts(caller, tenant_id=tenant_id)
    assert recon["status"] == "reconciled"
    assert expected_hash in recon["orphan_hashes"]
    assert len(recon["referenced_hashes"]) == 0

    # 4. If payload is corrupted before verification, store_and_register_artifact fails immediately
    corrupt_client = ArtifactStoreClient()
    corrupt_client.put_if_absent = AsyncMock(return_value=(expected_hash, len(payload_data), f"art://{expected_hash}"))
    corrupt_client.verify_integrity = AsyncMock(return_value=False)
    corrupt_gateway = DataGateway(
        _MockVectorRepository(),  # type: ignore[arg-type]
        authorization_boundary=test_setup["gateway"]._authorization_boundary,
        artifact_store=corrupt_client,
        artifact_repository=art_repo,  # type: ignore[arg-type]
    )
    with pytest.raises(ValueError, match="Payload integrity check failed"):
        await corrupt_gateway.store_and_register_artifact(
            caller,
            tenant_id=tenant_id,
            content=payload_data,
        )


@pytest.mark.asyncio
async def test_cms_staged_mutation_intent_and_result_provenance(test_setup: dict[str, Any]) -> None:
    """Verify CMS staged mutation flow: record intent -> staged mutation -> provider version -> record result."""
    gateway: DataGateway = test_setup["gateway"]
    caller: CallerIdentity = test_setup["caller"]
    prov_repo: _InMemoryProvenanceRepo = test_setup["prov_repo"]
    tenant_id = "tenant-l406"

    # Stage CMS entry with idempotency key
    staged = await gateway.stage_cms_entry(
        caller,
        tenant_id=tenant_id,
        content_type="landing_page",
        entry_id="hero-banner",
        data={"headline": "Future of Autonomous Enterprise"},
        idempotency_key="idemp-cms-001",
    )
    assert staged is not None

    # Check provenance chain for both intent and result
    chain = await prov_repo.chain(tenant_id)
    intent_records = [r for r in chain if r.activity == "mcp_data_cms_stage_intent"]
    result_records = [r for r in chain if r.activity == "mcp_data_cms_stage"]

    assert len(intent_records) == 1
    assert intent_records[0].metadata.get("idempotency_key") == "idemp-cms-001"

    assert len(result_records) == 1
    assert result_records[0].metadata.get("idempotency_key") == "idemp-cms-001"
    assert "provider_version" in result_records[0].metadata or "staged" in str(result_records[0].metadata)


@pytest.mark.asyncio
async def test_storage_health_aggregation_and_sanitization(test_setup: dict[str, Any]) -> None:
    """Verify aggregated Layer-4 readiness check without sensitive credential/data exposure."""
    mock_db = MagicMock()
    mock_db.healthcheck = AsyncMock(return_value={
        "status": "healthy",
        "latency_ms": 1.25,
        "extensions": {"pgvector": "0.7.0", "timescaledb": "2.14.0"},
        "connection_secret": "SUPPRESSED_SECRET",  # should not be returned by health service
    })

    art_store = test_setup["art_store"]
    cms_client = test_setup["cms_client"]
    prov_recorder = test_setup["prov_recorder"]

    aggregator = StorageHealthAggregator(
        database=mock_db,
        artifact_store=art_store,
        cms_client=cms_client,
        provenance_recorder=prov_recorder,
    )

    report = await aggregator.check_health()
    assert report["status"] == "healthy"
    assert report["layer"] == "Layer-4"
    comps = report["components"]
    assert comps["database"]["status"] == "healthy"
    assert comps["artifact_store"]["status"] == "healthy"
    assert comps["cms"]["status"] == "healthy"
    assert comps["provenance"]["status"] == "healthy"

    # Verify no leaks of credentials or raw connection secrets
    report_str = str(report)
    assert "SUPPRESSED_SECRET" not in report_str
    assert "password" not in report_str.lower()
    assert "secret" not in report_str.lower()

    # Degraded state when database healthcheck raises
    mock_db.healthcheck = AsyncMock(side_effect=ConnectionRefusedError("Postgres unreachable"))
    degraded_report = await aggregator.check_health()
    assert degraded_report["status"] == "degraded"
    assert degraded_report["components"]["database"]["status"] == "unhealthy"
    assert degraded_report["components"]["database"]["error"] == "ConnectionRefusedError"


@pytest.mark.asyncio
async def test_l4_07_failure_and_tamper_fail_closed(test_setup: dict[str, Any]) -> None:
    """Verify that CMS outages and corrupted artifact payloads fail closed without leaking state."""
    gateway: DataGateway = test_setup["gateway"]
    caller: CallerIdentity = test_setup["caller"]
    art_store: ArtifactStoreClient = test_setup["art_store"]
    art_repo: _MockArtifactRepository = test_setup["art_repo"]
    cms_client: CmsClient = test_setup["cms_client"]
    tenant_id = "tenant-l406"

    # 1. Corrupted artifact payload retrieval fails closed
    content = b"ORIGINAL_VALID_DELIVERABLE_123"
    ref = await gateway.store_and_register_artifact(
        caller, tenant_id=tenant_id, content=content, artifact_id="art-valid-1"
    )
    assert ref.content_hash == hashlib.sha256(content).hexdigest()

    # Tamper with the raw payload in store to simulate bit rot / storage corruption
    art_store._store[ref.content_hash] = b"CORRUPTED_DELIVERABLE_BIT_ROT"
    with pytest.raises(ValueError, match="Integrity verification failed"):
        await gateway.get_artifact_payload(caller, tenant_id=tenant_id, artifact_id="art-valid-1")

    # 2. CMS outage / timeout fails closed
    cms_client.stage_entry = AsyncMock(side_effect=TimeoutError("Headless CMS connection timeout"))
    with pytest.raises(TimeoutError, match="Headless CMS connection timeout"):
        await gateway.stage_cms_entry(
            caller,
            tenant_id=tenant_id,
            content_type="blog",
            entry_id="b1",
            data={"title": "test"},
        )
