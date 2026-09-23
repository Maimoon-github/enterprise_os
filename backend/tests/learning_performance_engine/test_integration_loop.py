"""Tests for LP-07: Integration & Learning Loop DAG, Barriers, and Governed Promotion."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
import pytest

from app.agents.learning_performance import LearningPerformanceAgent
from app.persistence.repositories.memory import MemoryRecord, MemoryRepository
from app.schemas.agent_contracts import TaskGrant
from app.schemas.governance import RiskLevel, TenantScope, WorkerRole
from app.schemas.learning_performance import QADecision, SpecialistStatus
from app.schemas.task_state import CanonicalTaskState, TaskStatus
from app.security.authorization_boundary import CallerIdentity
from app.services.attribution_coordinator import AttributionCoordinator
from app.services.memory_promotion import MemoryPromotionService
from tests.conftest import FakeProvenanceRepository, FakeSandboxClient
from app.services.provenance import ProvenanceRecorder


from app.schemas.telemetry import TelemetryEvent, TelemetryEventType


class _InMemoryTelemetryRepo:
    def __init__(self, events: list[TelemetryEvent]) -> None:
        self._events = events

    async def list_all(self, tenant_id: str) -> list[TelemetryEvent]:
        return [e for e in self._events if e.tenant_id == tenant_id]


class _InMemoryMemoryRepo(MemoryRepository):
    def __init__(self) -> None:
        self._store: dict[str, MemoryRecord] = {}

    async def promote(self, record: MemoryRecord, min_confidence: float = 0.6) -> None:
        self._store[record.memory_id] = record

    async def list_by_tenant(
        self,
        tenant_id: str,
        category: str | None = None,
        namespace: str | None = None,
    ) -> list[MemoryRecord]:
        return [
            r for r in self._store.values()
            if r.tenant_id == tenant_id
            and (not category or r.category == category)
            and (not namespace or r.namespace == namespace)
        ]

    def all(self) -> list[MemoryRecord]:
        return list(self._store.values())


def _make_t30_task(tenant_id: str = "tenant-gamma") -> CanonicalTaskState:
    t = CanonicalTaskState(
        task_id="task-t30",
        directive_id="dir-t30",
        worker_role=WorkerRole.LEARNING_PERFORMANCE,
        status=TaskStatus.COMPLETED,
    )
    t.governance_approved = True
    return t


def _make_sample_telemetry(tenant_id: str = "tenant-gamma") -> list[TelemetryEvent]:
    now = datetime.now(UTC)
    return [
        TelemetryEvent(
            event_id=f"ev-{i}",
            tenant_id=tenant_id,
            event_type=TelemetryEventType.CONVERSION,
            occurred_at=now - timedelta(minutes=i * 10),
            channel="meta",
            metrics={"revenue": 100.0, "spend": 25.0},
        )
        for i in range(1, 10)
    ]


# --- 1. Fixed DAG Execution Flow and Barrier Synchronization ---

@pytest.mark.asyncio
async def test_fixed_dag_execution_with_barriers() -> None:
    agent = LearningPerformanceAgent()
    grant = TaskGrant(
        task_id="task-t31-loop",
        worker_role=WorkerRole.LEARNING_PERFORMANCE,
        tenant_scope=TenantScope(tenant_id="tenant-gamma"),
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
    )
    events = [e.model_dump(mode="json") for e in _make_sample_telemetry("tenant-gamma")]

    qa_res, candidate, envelope = await agent.execute_learning_pipeline(grant, {"events": events})

    # Assert barrier completion
    assert qa_res.decision == QADecision.PASS
    assert len(qa_res.accepted_claim_ids) > 0
    assert candidate is not None
    # Candidate strictly bound to QA digest
    assert candidate.qa_digest == qa_res.evidence_bundle_digest
    assert set(candidate.accepted_claim_ids) == set(qa_res.accepted_claim_ids)
    assert candidate.status == "candidate"  # Model A authority: worker cannot self-promote


# --- 2. Unsafe Telemetry Blocks Fan-out (Failure Propagation) ---

@pytest.mark.asyncio
async def test_unsafe_telemetry_blocks_fanout() -> None:
    agent = LearningPerformanceAgent()
    grant = TaskGrant(
        task_id="task-t31-unsafe",
        worker_role=WorkerRole.LEARNING_PERFORMANCE,
        tenant_scope=TenantScope(tenant_id="tenant-gamma"),
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
    )

    # Empty events or malformed input blocks fan-out
    qa_res, candidate, envelope = await agent.execute_learning_pipeline(grant, {"events": []})

    assert qa_res.decision == QADecision.BLOCK
    assert "UNSAFE_TELEMETRY_BLOCKED_FANOUT" in qa_res.issue_codes
    assert candidate is None
    assert "Unsafe telemetry data stopped downstream measurement analysis." in envelope.unresolved_risks_or_assumptions


# --- 3. Coordinator Full Loop and CTS & Provenance Recording ---

@pytest.mark.asyncio
async def test_attribution_coordinator_full_loop() -> None:
    events = _make_sample_telemetry("tenant-gamma")
    telemetry_repo = _InMemoryTelemetryRepo(events)
    agent = LearningPerformanceAgent()
    prov_repo = FakeProvenanceRepository()
    prov_recorder = ProvenanceRecorder(prov_repo)

    coordinator = AttributionCoordinator(
        telemetry_repository=telemetry_repo,  # type: ignore[arg-type]
        agent=agent,
        provenance_recorder=prov_recorder,
    )

    t30_task = _make_t30_task("tenant-gamma")
    t31_task = CanonicalTaskState(
        task_id="task-t31",
        directive_id="dir-t31",
        worker_role=WorkerRole.LEARNING_PERFORMANCE,
        status=TaskStatus.PENDING,
    )
    task_states = {"task-t30": t30_task, "task-t31": t31_task}

    qa_res, candidate, envelope = await coordinator.execute_learning_loop(
        "tenant-gamma",
        task_states,
    )

    assert qa_res.decision == QADecision.PASS
    assert candidate is not None
    # Provenance recorded
    assert len(prov_repo.records) >= 1
    assert any(r.activity == "learning_loop_executed" for r in prov_repo.records)


# --- 4. Governed Promotion & Idempotent Replay ---

@pytest.mark.asyncio
async def test_governed_memory_promotion_idempotency() -> None:
    mem_repo = _InMemoryMemoryRepo()
    promotion_service = MemoryPromotionService(mem_repo, min_confidence=0.7)

    # Candidate statement
    statement = "Meta channel attribution weight 0.50 with verified decay half-life."
    tenant_id = "tenant-gamma"

    # First promotion succeeds
    rec1 = await promotion_service.promote(
        tenant_id=tenant_id,
        category="attribution",
        statement=statement,
        confidence=0.85,
        source_task_ids=["task-t31"],
    )
    assert rec1 is not None
    assert len(mem_repo.all()) == 1

    # Second promotion with lower confidence rejected
    rec_low = await promotion_service.promote(
        tenant_id=tenant_id,
        category="attribution",
        statement="Unreliable low confidence metric",
        confidence=0.50,
        source_task_ids=["task-t31"],
    )
    assert rec_low is None
    assert len(mem_repo.all()) == 1
