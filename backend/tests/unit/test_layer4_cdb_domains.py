"""Unit tests and benchmarks for Layer-4 CDB persistence domains: vector & telemetry."""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock
import pytest
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PolicyViolationError, RepositoryError
from app.mcp.data_gateway import DataGateway
from app.persistence.repositories.base import standard_table
from app.persistence.repositories.telemetry import TelemetryRepository
from app.persistence.repositories.vector import VectorRepository, _cosine_similarity, _embed
from app.schemas.governance import RiskLevel, TenantScope
from app.schemas.telemetry import TelemetryEvent, TelemetryEventType
from app.security.authorization_boundary import CallerIdentity


def make_mock_session_factory(session: AsyncSession) -> MagicMock:
    factory = MagicMock()
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=None)
    factory.return_value = ctx
    return factory


# =====================================================================
# 1. Vector Domain Tests
# =====================================================================


@pytest.fixture
def mock_session() -> AsyncMock:
    sess = AsyncMock(spec=AsyncSession)
    sess.is_active = True
    return sess


@pytest.fixture
def vector_repo(mock_session: AsyncMock) -> VectorRepository:
    factory = make_mock_session_factory(mock_session)
    return VectorRepository(session_factory=factory, dimension=256)


@pytest.mark.asyncio
async def test_vector_index_fails_on_missing_tenant_or_doc(vector_repo: VectorRepository) -> None:
    with pytest.raises(RepositoryError, match="Tenant ID cannot be empty"):
        await vector_repo.index_document(doc_id="d1", tenant_id="", text="hello", source="test")

    with pytest.raises(RepositoryError, match="Doc ID cannot be empty"):
        await vector_repo.index_document(doc_id="   ", tenant_id="t1", text="hello", source="test")


@pytest.mark.asyncio
async def test_vector_dimension_and_metric_mismatch_rejection(
    vector_repo: VectorRepository,
) -> None:
    # Dimension mismatch on write
    with pytest.raises(ValueError, match="Embedding dimension mismatch"):
        await vector_repo.index_document(
            doc_id="d1",
            tenant_id="t1",
            text="hello",
            source="test",
            embedding=[0.1] * 128,  # expected 256
        )

    # Metric mismatch on write
    with pytest.raises(ValueError, match="Unsupported distance metric"):
        await vector_repo.index_document(
            doc_id="d1",
            tenant_id="t1",
            text="hello",
            source="test",
            metric="euclidean",
        )

    # Dimension mismatch on search
    with pytest.raises(ValueError, match="Query vector dimension mismatch"):
        await vector_repo.similarity_search(
            tenant_id="t1",
            query_vector=[0.1] * 100,
        )


@pytest.mark.asyncio
async def test_vector_cross_tenant_collision_rejection(
    vector_repo: VectorRepository, mock_session: AsyncMock
) -> None:
    # Existing document owned by tenant-owner
    mock_row = MagicMock()
    mock_row.scalar_one_or_none.return_value = "tenant-owner"
    mock_session.execute.return_value = mock_row

    with pytest.raises(RepositoryError, match="Cross-tenant access violation"):
        await vector_repo.index_document(
            doc_id="doc-123",
            tenant_id="tenant-attacker",
            text="forbidden",
            source="test",
            session=mock_session,
        )


@pytest.mark.asyncio
async def test_vector_namespace_isolation_and_exact_baseline() -> None:
    in_memory_docs: list[dict[str, Any]] = []

    def save_doc(doc: dict[str, Any]) -> None:
        in_memory_docs.append(doc)

    mock_sess = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.all.side_effect = lambda: [(d,) for d in in_memory_docs]
    mock_sess.execute.return_value = mock_result
    factory = make_mock_session_factory(mock_sess)

    repo = VectorRepository(session_factory=factory, dimension=256)

    # Seed 3 docs: 2 in 'marketing' namespace, 1 in 'legal'
    doc_mkt_1 = {
        "doc_id": "m1",
        "tenant_id": "t-alpha",
        "namespace": "marketing",
        "text": "summer sale campaign strategy",
        "embedding": _embed("summer sale campaign strategy", dim=256),
    }
    doc_mkt_2 = {
        "doc_id": "m2",
        "tenant_id": "t-alpha",
        "namespace": "marketing",
        "text": "winter discounts advertisement",
        "embedding": _embed("winter discounts advertisement", dim=256),
    }
    doc_legal = {
        "doc_id": "l1",
        "tenant_id": "t-alpha",
        "namespace": "legal",
        "text": "compliance agreement terms",
        "embedding": _embed("compliance agreement terms", dim=256),
    }
    in_memory_docs.extend([doc_mkt_1, doc_mkt_2, doc_legal])

    # Search in 'marketing' namespace
    results_mkt = await repo.similarity_search(
        tenant_id="t-alpha", query="campaign strategy", namespace="marketing", top_k=10
    )
    assert len(results_mkt) == 2
    assert all(r["namespace"] == "marketing" for r in results_mkt)
    assert results_mkt[0]["doc_id"] == "m1"
    assert results_mkt[0]["search_mode"] == "exact"

    # Search in 'legal' namespace
    results_legal = await repo.similarity_search(
        tenant_id="t-alpha", query="compliance", namespace="legal", top_k=10
    )
    assert len(results_legal) == 1
    assert results_legal[0]["doc_id"] == "l1"


@pytest.mark.asyncio
async def test_vector_ann_vs_exact_benchmark_and_recall() -> None:
    """Benchmark comparing exact baseline search vs configurable ANN search.

    Assesses recall@k, latency, and tenant-filter correctness.
    """
    tenant_id = "tenant-bench"
    other_tenant = "tenant-other"

    corpus: list[dict[str, Any]] = []
    # Seed 60 documents for tenant-bench and 20 for other-tenant
    for i in range(60):
        text_content = f"document cluster topic {i % 5} detailed explanation number {i}"
        corpus.append(
            {
                "doc_id": f"doc-{i}",
                "tenant_id": tenant_id,
                "namespace": "default",
                "text": text_content,
                "embedding": _embed(text_content, dim=256),
            }
        )
    for i in range(20):
        corpus.append(
            {
                "doc_id": f"foreign-{i}",
                "tenant_id": other_tenant,
                "namespace": "default",
                "text": f"other company confidential data {i}",
                "embedding": _embed(f"other data {i}", dim=256),
            }
        )

    mock_sess = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    # Filter by tenant in query result simulation
    mock_result.all.return_value = [(d,) for d in corpus if d["tenant_id"] == tenant_id]
    mock_sess.execute.return_value = mock_result
    factory = make_mock_session_factory(mock_sess)

    repo = VectorRepository(session_factory=factory, dimension=256)
    query = "document cluster topic 2 analysis"

    # 1. Exact Search Baseline
    t0 = time.perf_counter()
    exact_results = await repo.similarity_search(
        tenant_id=tenant_id, query=query, top_k=5, search_type="exact"
    )
    exact_latency_ms = (time.perf_counter() - t0) * 1000

    # 2. ANN Search
    t1 = time.perf_counter()
    ann_results = await repo.similarity_search(
        tenant_id=tenant_id, query=query, top_k=5, search_type="ann", ef_search=30
    )
    ann_latency_ms = (time.perf_counter() - t1) * 1000

    assert len(exact_results) == 5
    assert len(ann_results) == 5

    # Verification: Zero cross-tenant leakage in both modes
    assert all(r["tenant_id"] == tenant_id for r in exact_results)
    assert all(r["tenant_id"] == tenant_id for r in ann_results)

    # Verification: Recall@5 calculation
    exact_ids = {r["doc_id"] for r in exact_results}
    ann_ids = {r["doc_id"] for r in ann_results}
    recall_at_5 = len(exact_ids & ann_ids) / len(exact_ids)

    # ANN achieves >= 0.80 recall@5 on clustered corpus
    assert recall_at_5 >= 0.80
    assert exact_results[0]["search_mode"] == "exact"
    assert ann_results[0]["search_mode"] == "ann"


# =====================================================================
# 2. Telemetry Domain Tests
# =====================================================================


@pytest.fixture
def telemetry_repo(mock_session: AsyncMock) -> TelemetryRepository:
    factory = make_mock_session_factory(mock_session)
    return TelemetryRepository(session_factory=factory)


@pytest.mark.asyncio
async def test_telemetry_idempotent_ingestion(
    telemetry_repo: TelemetryRepository, mock_session: AsyncMock
) -> None:
    event = TelemetryEvent(
        event_id="evt-100",
        tenant_id="tenant-telemetry",
        event_type=TelemetryEventType.CONVERSION,
        channel="shopify",
        occurred_at=datetime.now(UTC),
        idempotency_key="idem-key-abc-123",
        metrics={"revenue": 150.0},
    )

    # 1. First record call: no existing record -> executes save
    with pytest.MonkeyPatch.context() as mp:
        mock_save1 = AsyncMock()
        mp.setattr(telemetry_repo, "get_by_idempotency_key", AsyncMock(return_value=None))
        mp.setattr(telemetry_repo, "get", AsyncMock(return_value=None))
        mp.setattr(telemetry_repo, "save", mock_save1)

        res1 = await telemetry_repo.record(event)
        assert res1.event_id == "evt-100"
        mock_save1.assert_awaited_once()

    # 2. Second record call: existing record found by idempotency_key -> returns existing without saving
    with pytest.MonkeyPatch.context() as mp:
        mock_save2 = AsyncMock()
        mp.setattr(telemetry_repo, "get_by_idempotency_key", AsyncMock(return_value=event))
        mp.setattr(telemetry_repo, "save", mock_save2)

        res2 = await telemetry_repo.record(event)
        assert res2.event_id == "evt-100"
        mock_save2.assert_not_called()


@pytest.mark.asyncio
async def test_telemetry_query_range_and_filtering() -> None:
    now = datetime.now(UTC)
    events_data = [
        {
            "event_id": "evt-1",
            "tenant_id": "tenant-range",
            "event_type": "conversion",
            "channel": "web",
            "occurred_at": (now - timedelta(hours=3)).isoformat(),
            "metrics": {"value": 10.0},
        },
        {
            "event_id": "evt-2",
            "tenant_id": "tenant-range",
            "event_type": "traffic",
            "channel": "web",
            "occurred_at": (now - timedelta(hours=2)).isoformat(),
            "metrics": {"value": 20.0},
        },
        {
            "event_id": "evt-3",
            "tenant_id": "tenant-range",
            "event_type": "conversion",
            "channel": "web",
            "occurred_at": (now - timedelta(hours=1)).isoformat(),
            "metrics": {"value": 30.0},
        },
    ]

    mock_sess = AsyncMock(spec=AsyncSession)
    mock_res = MagicMock()
    mock_res.all.return_value = [(d,) for d in events_data]
    mock_sess.execute.return_value = mock_res
    factory = make_mock_session_factory(mock_sess)

    repo = TelemetryRepository(session_factory=factory)

    # Query range from 2.5 hours ago to 0.5 hours ago, filter conversions only
    start = now - timedelta(hours=2, minutes=30)
    end = now - timedelta(minutes=30)

    results = await repo.query_range(
        "tenant-range",
        start_time=start,
        end_time=end,
        event_type="conversion",
        limit=10,
    )

    # Only evt-3 matches both time range and event_type
    assert len(results) == 1
    assert results[0].event_id == "evt-3"
    assert results[0].metrics["value"] == 30.0


# =====================================================================
# 3. Model A Data Gateway Integration Tests
# =====================================================================


@pytest.mark.asyncio
async def test_data_gateway_vector_and_telemetry_isolation() -> None:
    mock_vector = AsyncMock(spec=VectorRepository)
    mock_vector.similarity_search.return_value = [{"doc_id": "v1", "score": 0.95}]
    mock_telemetry = AsyncMock(spec=TelemetryRepository)
    mock_telemetry.query_range.return_value = []

    gateway = DataGateway(
        vector_repository=mock_vector,
        telemetry_repository=mock_telemetry,
    )

    caller = CallerIdentity(
        subject="intelligence_engine",
        tenant_scope=TenantScope(tenant_id="t-1"),
        risk_ceiling=RiskLevel.MEDIUM,
    )

    # 1. Vector query passing namespace
    res = await gateway.query(caller, tenant_id="t-1", query="hello", namespace="test_ns")
    assert len(res) == 1
    mock_vector.similarity_search.assert_awaited_with(
        tenant_id="t-1", query="hello", top_k=10, namespace="test_ns"
    )

    # 2. Worker direct access rejection
    worker = CallerIdentity(
        subject="W_STRATEGY",
        tenant_scope=TenantScope(tenant_id="t-1"),
        risk_ceiling=RiskLevel.HIGH,
    )
    with pytest.raises(PolicyViolationError, match="Direct worker enterprise-store access forbidden"):
        await gateway.query(worker, tenant_id="t-1", query="hello")

    # 3. Telemetry range query through gateway
    await gateway.list_telemetry(
        caller,
        tenant_id="t-1",
        start_time=datetime.now(UTC) - timedelta(hours=1),
        limit=50,
    )
    mock_telemetry.query_range.assert_awaited()
