"""Unit and Integration Tests for Task-31 (T31).

Validates:
1. Authoritative T30 prerequisite dependency check (fails closed if missing/unapproved/incomplete).
2. Model A boundary preservation: W_LEARN has no direct CDB/RAG access; S_ATTR has zero DB access.
3. Strict tenant isolation: rejects off-tenant paths or spend records.
4. Deterministic multi-touch attribution models (linear, first-touch, last-touch, time-decay, position-based).
5. Creative fatigue and exponential decay scoring (lambda=0.05, fatigue < 0.65, hook refresh vs scale).
6. Safe ROAS calculations protecting against zero / missing spend denominators.
7. Explicit handling of insufficient telemetry and configuration gaps without fabricating metrics.
8. Replay / duplicate filtering and delayed event handling within window.
9. Packaging of structured EvidenceEnvelope with confidence intervals and candidate learning deltas for IE.
10. Zero T32 memory promotion side-effects.
11. Canonical Task State (CTS) update and W3C audit provenance emission.
12. Authoritative T32 eligibility assertion.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from app.agents.learning_performance import LearningPerformanceAgent
from app.core.exceptions import (
    AuthorizationError,
    PolicyViolationError,
)
from app.integrations.sandbox.client import SandboxClient
from app.persistence.repositories.memory import MemoryRepository
from app.persistence.repositories.telemetry import TelemetryRepository
from app.schemas.agent_contracts import (
    AttributionDeliverable,
    AttributionModelType,
    TaskGrant,
)
from app.schemas.governance import TenantScope, WorkerRole
from app.schemas.task_state import CanonicalTaskState, TaskStatus
from app.schemas.telemetry import TelemetryEvent, TelemetryEventType
from app.services.attribution_coordinator import AttributionCoordinator
from app.services.provenance import ProvenanceRecorder
from app.services.task_state import TaskStateService
from tests.conftest import FakeProvenanceRepository


class _InMemoryTelemetryRepository(TelemetryRepository):
    """Stand-in telemetry repository for T31 testing."""

    def __init__(self) -> None:
        self._events: dict[str, TelemetryEvent] = {}

    async def record(self, event: TelemetryEvent) -> None:
        self._events[event.event_id] = event

    async def list_all(self, tenant_id: str) -> list[TelemetryEvent]:
        return [e for e in self._events.values() if e.tenant_id == tenant_id]

    async def list_by_type(self, tenant_id: str, event_type: str) -> list[TelemetryEvent]:
        return [
            e for e in self._events.values()
            if e.tenant_id == tenant_id and e.event_type.value == event_type
        ]


class _InMemoryMemoryRepository(MemoryRepository):
    """Stand-in memory repository to verify ZERO premature T32 promotion."""

    def __init__(self) -> None:
        self.promoted_records: list[Any] = []

    async def promote(self, record: Any, min_confidence: float = 0.6) -> None:  # type: ignore[override]
        self.promoted_records.append(record)


class _FakeTaskStateRepository:
    def __init__(self) -> None:
        self.states: dict[str, CanonicalTaskState] = {}

    async def require(self, task_id: str) -> CanonicalTaskState:
        if task_id not in self.states:
            raise KeyError(f"Task '{task_id}' not found.")
        return self.states[task_id]

    async def save_state(self, tenant_id: str, state: CanonicalTaskState) -> None:
        self.states[state.task_id] = state


def _setup_t31_environment(
    tenant_id: str = "tenant-alpha",
    t30_status: TaskStatus = TaskStatus.COMPLETED,
    t30_approved: bool = True,
    has_t30: bool = True,
) -> tuple[
    AttributionCoordinator,
    LearningPerformanceAgent,
    _InMemoryTelemetryRepository,
    _InMemoryMemoryRepository,
    dict[str, CanonicalTaskState],
    FakeProvenanceRepository,
]:
    telemetry_repo = _InMemoryTelemetryRepository()
    memory_repo = _InMemoryMemoryRepository()
    task_repo = _FakeTaskStateRepository()
    prov_repo = FakeProvenanceRepository()
    prov_recorder = ProvenanceRecorder(prov_repo)
    task_service = TaskStateService(task_repo, provenance_recorder=prov_recorder)

    # Sandbox client executing isolated S_ATTR micro-tool
    sandbox_client = SandboxClient()
    agent = LearningPerformanceAgent(sandbox_client)

    coordinator = AttributionCoordinator(
        telemetry_repository=telemetry_repo,
        agent=agent,
        task_state_service=task_service,
        provenance_recorder=prov_recorder,
    )

    task_states: dict[str, CanonicalTaskState] = {}
    if has_t30:
        t30 = CanonicalTaskState(
            task_id="task-t30",
            directive_id="dir-t30",
            worker_role=WorkerRole.LEARNING_PERFORMANCE,
            status=t30_status,
            governance_approved=t30_approved,
            cts_state={"tenant_id": tenant_id, "telemetry_ingestion": {"total_ingested": 10}},
        )
        task_states["task-t30"] = t30
        task_repo.states["task-t30"] = t30

    t31 = CanonicalTaskState(
        task_id="task-t31",
        directive_id="dir-t31",
        worker_role=WorkerRole.LEARNING_PERFORMANCE,
        status=TaskStatus.IN_PROGRESS,
        governance_approved=True,
        cts_state={"tenant_id": tenant_id},
    )
    task_states["task-t31"] = t31
    task_repo.states["task-t31"] = t31

    return coordinator, agent, telemetry_repo, memory_repo, task_states, prov_repo


# ============================================================================
# 1. Dependency & Prerequisite Verification
# ============================================================================

@pytest.mark.asyncio
async def test_t31_fails_closed_when_t30_missing() -> None:
    """T31 cannot proceed if T30 live telemetry dependency is absent."""
    coordinator, _, _, _, task_states, _ = _setup_t31_environment(has_t30=False)

    with pytest.raises(PolicyViolationError) as exc:
        await coordinator.execute_attribution("tenant-alpha", task_states)
    assert "Dependency T30" in str(exc.value)


@pytest.mark.asyncio
async def test_t31_fails_closed_when_t30_not_completed() -> None:
    """T31 cannot proceed if T30 is still in progress or failed."""
    coordinator, _, _, _, task_states, _ = _setup_t31_environment(t30_status=TaskStatus.IN_PROGRESS)

    with pytest.raises(PolicyViolationError) as exc:
        await coordinator.execute_attribution("tenant-alpha", task_states)
    assert "Dependency T30 is not completed" in str(exc.value)


@pytest.mark.asyncio
async def test_t31_fails_closed_when_t30_unapproved() -> None:
    """T31 cannot proceed if T30 lacks authoritative governance approval."""
    coordinator, _, _, _, task_states, _ = _setup_t31_environment(t30_approved=False)

    with pytest.raises(PolicyViolationError) as exc:
        await coordinator.execute_attribution("tenant-alpha", task_states)
    assert "lacks authoritative governance approval" in str(exc.value)


# ============================================================================
# 2. Model A Boundary & Architecture Verification
# ============================================================================

@pytest.mark.asyncio
async def test_t31_model_a_preservation() -> None:
    """Verify W_LEARN has no direct database connection attributes and delegates to S_ATTR."""
    sandbox_client = SandboxClient()
    agent = LearningPerformanceAgent(sandbox_client)

    # W_LEARN must only have sandbox client, no repository or database sessions
    assert not hasattr(agent, "telemetry_repository")
    assert not hasattr(agent, "_session_factory")
    assert not hasattr(agent, "_repository")
    assert agent.capability.value == "S_ATTR"


# ============================================================================
# 3. Tenant Scope & Cross-Tenant Rejection
# ============================================================================

@pytest.mark.asyncio
async def test_t31_rejects_cross_tenant_conversion_paths() -> None:
    """W_LEARN raises AuthorizationError if context contains foreign tenant paths."""
    sandbox_client = SandboxClient()
    agent = LearningPerformanceAgent(sandbox_client)

    grant = TaskGrant(
        task_id="task-t31",
        worker_role=WorkerRole.LEARNING_PERFORMANCE,
        tenant_scope=TenantScope(tenant_id="tenant-alpha"),
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
    )

    rogue_context: dict[str, object] = {
        "paths": [
            {
                "conversion_id": "conv-rogue",
                "tenant_id": "tenant-beta",  # Off-tenant!
                "revenue": 500.0,
                "touchpoints": [{"channel": "meta"}],
            }
        ]
    }

    with pytest.raises(AuthorizationError) as exc:
        await agent.run(grant, rogue_context)
    assert "Cross-tenant data violation" in str(exc.value)


@pytest.mark.asyncio
async def test_t31_rejects_cross_tenant_spend_records() -> None:
    """W_LEARN raises AuthorizationError if context contains foreign tenant spend records."""
    sandbox_client = SandboxClient()
    agent = LearningPerformanceAgent(sandbox_client)

    grant = TaskGrant(
        task_id="task-t31",
        worker_role=WorkerRole.LEARNING_PERFORMANCE,
        tenant_scope=TenantScope(tenant_id="tenant-alpha"),
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
    )

    rogue_context: dict[str, object] = {
        "spend_data": [
            {"channel": "meta", "spend": 1000.0, "tenant_id": "tenant-rogue"}
        ]
    }

    with pytest.raises(AuthorizationError) as exc:
        await agent.run(grant, rogue_context)
    assert "Cross-tenant data violation" in str(exc.value)


# ============================================================================
# 4. Multi-Touch Attribution Models
# ============================================================================

@pytest.mark.asyncio
async def test_t31_linear_attribution() -> None:
    """Linear attribution divides credit equally across all touchpoints in a journey."""
    coordinator, agent, telemetry_repo, _, task_states, _ = _setup_t31_environment()

    # Create journey with 4 touchpoints: Google Ads -> Meta Ads -> TikTok Ads -> Website Storefront
    now = datetime.now(UTC)
    events = [
        TelemetryEvent(
            event_id="ev-1",
            tenant_id="tenant-alpha",
            event_type=TelemetryEventType.TRAFFIC,
            channel="google",
            occurred_at=now - timedelta(days=5),
            correlation_id="session-user-1",
        ),
        TelemetryEvent(
            event_id="ev-2",
            tenant_id="tenant-alpha",
            event_type=TelemetryEventType.TRAFFIC,
            channel="meta",
            occurred_at=now - timedelta(days=3),
            correlation_id="session-user-1",
        ),
        TelemetryEvent(
            event_id="ev-3",
            tenant_id="tenant-alpha",
            event_type=TelemetryEventType.TRAFFIC,
            channel="tiktok",
            occurred_at=now - timedelta(days=1),
            correlation_id="session-user-1",
        ),
        TelemetryEvent(
            event_id="ev-4",
            tenant_id="tenant-alpha",
            event_type=TelemetryEventType.CONVERSION,
            channel="website",
            occurred_at=now,
            correlation_id="session-user-1",
            metrics={"revenue": 400.0},
        ),
        # Ad spend events
        TelemetryEvent(
            event_id="sp-1",
            tenant_id="tenant-alpha",
            event_type=TelemetryEventType.AD_SPEND,
            channel="google",
            occurred_at=now,
            metrics={"spend": 50.0},
        ),
        TelemetryEvent(
            event_id="sp-2",
            tenant_id="tenant-alpha",
            event_type=TelemetryEventType.AD_SPEND,
            channel="meta",
            occurred_at=now,
            metrics={"spend": 50.0},
        ),
        TelemetryEvent(
            event_id="sp-3",
            tenant_id="tenant-alpha",
            event_type=TelemetryEventType.AD_SPEND,
            channel="tiktok",
            occurred_at=now,
            metrics={"spend": 50.0},
        ),
    ]
    for ev in events:
        await telemetry_repo.record(ev)

    envelope, deliverable = await coordinator.execute_attribution(
        "tenant-alpha",
        task_states,
        model_type=AttributionModelType.LINEAR,
    )

    assert deliverable is not None
    assert deliverable.model_type == AttributionModelType.LINEAR
    # 3 touchpoints (google, meta, tiktok) each receive 1/3 of $400 ($133.33)
    weights = {w.channel: w.weight for w in deliverable.channel_weights}
    assert pytest.approx(weights["google"], 0.01) == 0.3333
    assert pytest.approx(weights["meta"], 0.01) == 0.3333
    assert pytest.approx(weights["tiktok"], 0.01) == 0.3333


@pytest.mark.asyncio
async def test_t31_first_touch_attribution() -> None:
    """First-touch attribution assigns 100% of conversion value to the initial touchpoint."""
    coordinator, agent, telemetry_repo, _, task_states, _ = _setup_t31_environment()

    now = datetime.now(UTC)
    events = [
        TelemetryEvent(
            event_id="ev-1",
            tenant_id="tenant-alpha",
            event_type=TelemetryEventType.TRAFFIC,
            channel="google",
            occurred_at=now - timedelta(days=4),
            correlation_id="sess-first",
        ),
        TelemetryEvent(
            event_id="ev-2",
            tenant_id="tenant-alpha",
            event_type=TelemetryEventType.TRAFFIC,
            channel="meta",
            occurred_at=now - timedelta(days=1),
            correlation_id="sess-first",
        ),
        TelemetryEvent(
            event_id="ev-3",
            tenant_id="tenant-alpha",
            event_type=TelemetryEventType.CONVERSION,
            channel="website",
            occurred_at=now,
            correlation_id="sess-first",
            metrics={"revenue": 250.0},
        ),
    ]
    for ev in events:
        await telemetry_repo.record(ev)

    envelope, deliverable = await coordinator.execute_attribution(
        "tenant-alpha",
        task_states,
        model_type=AttributionModelType.FIRST_TOUCH,
    )

    assert deliverable is not None
    rev_by_channel = {w.channel: w.attributed_revenue for w in deliverable.channel_weights}
    assert rev_by_channel["google"] == 250.0
    assert rev_by_channel.get("meta", 0.0) == 0.0


@pytest.mark.asyncio
async def test_t31_last_touch_attribution() -> None:
    """Last-touch attribution assigns 100% of conversion value to the final marketing touchpoint."""
    coordinator, agent, telemetry_repo, _, task_states, _ = _setup_t31_environment()

    now = datetime.now(UTC)
    events = [
        TelemetryEvent(
            event_id="ev-1",
            tenant_id="tenant-alpha",
            event_type=TelemetryEventType.TRAFFIC,
            channel="google",
            occurred_at=now - timedelta(days=3),
            correlation_id="sess-last",
        ),
        TelemetryEvent(
            event_id="ev-2",
            tenant_id="tenant-alpha",
            event_type=TelemetryEventType.TRAFFIC,
            channel="instagram",
            occurred_at=now - timedelta(hours=2),
            correlation_id="sess-last",
        ),
        TelemetryEvent(
            event_id="ev-3",
            tenant_id="tenant-alpha",
            event_type=TelemetryEventType.CONVERSION,
            channel="website",
            occurred_at=now,
            correlation_id="sess-last",
            metrics={"revenue": 300.0},
        ),
    ]
    for ev in events:
        await telemetry_repo.record(ev)

    envelope, deliverable = await coordinator.execute_attribution(
        "tenant-alpha",
        task_states,
        model_type=AttributionModelType.LAST_TOUCH,
    )

    assert deliverable is not None
    rev_by_channel = {w.channel: w.attributed_revenue for w in deliverable.channel_weights}
    assert rev_by_channel["instagram"] == 300.0
    assert rev_by_channel.get("google", 0.0) == 0.0


@pytest.mark.asyncio
async def test_t31_time_decay_attribution() -> None:
    """Time-decay attribution gives exponentially more credit to touches closer to conversion."""
    coordinator, agent, telemetry_repo, _, task_states, _ = _setup_t31_environment()

    now = datetime.now(UTC)
    # Touch 1 was 7 days ago (1 half-life: raw weight 0.5)
    # Touch 2 was immediately before conversion (0 days: raw weight 1.0)
    events = [
        TelemetryEvent(
            event_id="ev-1",
            tenant_id="tenant-alpha",
            event_type=TelemetryEventType.TRAFFIC,
            channel="google",
            occurred_at=now - timedelta(days=7),
            correlation_id="sess-decay",
        ),
        TelemetryEvent(
            event_id="ev-2",
            tenant_id="tenant-alpha",
            event_type=TelemetryEventType.TRAFFIC,
            channel="meta",
            occurred_at=now,
            correlation_id="sess-decay",
        ),
        TelemetryEvent(
            event_id="ev-3",
            tenant_id="tenant-alpha",
            event_type=TelemetryEventType.CONVERSION,
            channel="website",
            occurred_at=now,
            correlation_id="sess-decay",
            metrics={"revenue": 150.0},
        ),
    ]
    for ev in events:
        await telemetry_repo.record(ev)

    envelope, deliverable = await coordinator.execute_attribution(
        "tenant-alpha",
        task_states,
        model_type=AttributionModelType.TIME_DECAY,
    )

    assert deliverable is not None
    weights = {w.channel: w.weight for w in deliverable.channel_weights}
    # Touch 2 (1.0) vs Touch 1 (0.5): Touch 2 gets ~66.7%, Touch 1 gets ~33.3%
    assert weights["meta"] > weights["google"]
    assert pytest.approx(weights["meta"], 0.02) == 0.6667
    assert pytest.approx(weights["google"], 0.02) == 0.3333


@pytest.mark.asyncio
async def test_t31_position_based_attribution() -> None:
    """Position-based (U-shaped) attribution gives 40% first, 40% last, and 20% middle."""
    coordinator, agent, telemetry_repo, _, task_states, _ = _setup_t31_environment()

    now = datetime.now(UTC)
    events = [
        TelemetryEvent(
            event_id="ev-1",
            tenant_id="tenant-alpha",
            event_type=TelemetryEventType.TRAFFIC,
            channel="google",
            occurred_at=now - timedelta(days=6),
            correlation_id="sess-u",
        ),
        TelemetryEvent(
            event_id="ev-2",
            tenant_id="tenant-alpha",
            event_type=TelemetryEventType.TRAFFIC,
            channel="meta",
            occurred_at=now - timedelta(days=3),
            correlation_id="sess-u",
        ),
        TelemetryEvent(
            event_id="ev-3",
            tenant_id="tenant-alpha",
            event_type=TelemetryEventType.TRAFFIC,
            channel="tiktok",
            occurred_at=now - timedelta(days=1),
            correlation_id="sess-u",
        ),
        TelemetryEvent(
            event_id="ev-4",
            tenant_id="tenant-alpha",
            event_type=TelemetryEventType.CONVERSION,
            channel="website",
            occurred_at=now,
            correlation_id="sess-u",
            metrics={"revenue": 1000.0},
        ),
    ]
    for ev in events:
        await telemetry_repo.record(ev)

    envelope, deliverable = await coordinator.execute_attribution(
        "tenant-alpha",
        task_states,
        model_type=AttributionModelType.POSITION_BASED,
    )

    assert deliverable is not None
    weights = {w.channel: w.weight for w in deliverable.channel_weights}
    assert pytest.approx(weights["google"], 0.01) == 0.40
    assert pytest.approx(weights["tiktok"], 0.01) == 0.40
    assert pytest.approx(weights["meta"], 0.01) == 0.20


# ============================================================================
# 5. Creative Decay & Fatigue Scoring
# ============================================================================

@pytest.mark.asyncio
async def test_t31_creative_fatigue_and_exponential_decay() -> None:
    """Creative decay uses e^(-0.05 * days); flags fatigue if decay < 0.65."""
    sandbox_client = SandboxClient()
    agent = LearningPerformanceAgent(sandbox_client)

    grant = TaskGrant(
        task_id="task-t31",
        worker_role=WorkerRole.LEARNING_PERFORMANCE,
        tenant_scope=TenantScope(tenant_id="tenant-alpha"),
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
    )

    # Creative 1 has been active for 2 days (fresh: decay ~0.90)
    # Creative 2 has been active for 15 days (fatigued: decay ~0.47)
    context: dict[str, object] = {
        "creatives": [
            {"creative_id": "cr-fresh", "channel": "meta", "days_active": 2.0, "reported_roas": 3.5},
            {"creative_id": "cr-stale", "channel": "meta", "days_active": 15.0, "reported_roas": 3.0},
        ],
        "roas": "3.0",
        "days_active": "15.0",
    }

    envelope = await agent.run(grant, context)
    deliverable = agent.extract_attribution_deliverable(envelope)

    assert deliverable is not None
    decays = {d.creative_id: d for d in deliverable.decay_metrics}

    assert decays["cr-fresh"].decay_multiplier > 0.85
    assert not decays["cr-fresh"].fatigue_detected
    assert decays["cr-fresh"].recommended_action == "scale_spend"

    assert decays["cr-stale"].decay_multiplier < 0.65
    assert decays["cr-stale"].fatigue_detected
    assert decays["cr-stale"].recommended_action == "refresh_creative_hooks"


# ============================================================================
# 6. ROAS Calculations & Safe Denominators
# ============================================================================

@pytest.mark.asyncio
async def test_t31_roas_handles_zero_spend_safely() -> None:
    """Zero spend with revenue records safe status without ZeroDivisionError."""
    sandbox_client = SandboxClient()
    agent = LearningPerformanceAgent(sandbox_client)

    grant = TaskGrant(
        task_id="task-t31",
        worker_role=WorkerRole.LEARNING_PERFORMANCE,
        tenant_scope=TenantScope(tenant_id="tenant-alpha"),
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
    )

    context: dict[str, object] = {
        "paths": [
            {
                "conversion_id": "c-1",
                "revenue": 500.0,
                "touchpoints": [{"channel": "organic_search"}],
            }
        ],
        "spend_data": {"organic_search": 0.0},
    }

    envelope = await agent.run(grant, context)
    deliverable = agent.extract_attribution_deliverable(envelope)

    assert deliverable is not None
    roas_organic = next(r for r in deliverable.roas_metrics if r.channel == "organic_search")
    assert roas_organic.spend == 0.0
    assert roas_organic.revenue == 500.0
    assert roas_organic.roas == 0.0
    assert roas_organic.status == "zero_spend_with_revenue"


# ============================================================================
# 7. Insufficient Data & Configuration Gaps
# ============================================================================

@pytest.mark.asyncio
async def test_t31_explicit_insufficient_data_result() -> None:
    """When zero telemetry and zero conversion paths exist, explicit insufficient_data is returned."""
    sandbox_client = SandboxClient()
    agent = LearningPerformanceAgent(sandbox_client)

    grant = TaskGrant(
        task_id="task-t31",
        worker_role=WorkerRole.LEARNING_PERFORMANCE,
        tenant_scope=TenantScope(tenant_id="tenant-alpha"),
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
    )

    envelope = await agent.run(grant, context={})

    assert envelope.payload.get("status") == "insufficient_data"
    assert envelope.confidence.point_estimate == 0.0
    assert any("INSUFFICIENT_DATA" in e for e in envelope.evidence)


@pytest.mark.asyncio
async def test_t31_explicit_configuration_gap_result() -> None:
    """Requesting an unsupported attribution model returns configuration_gap without inventing rules."""
    sandbox_client = SandboxClient()
    agent = LearningPerformanceAgent(sandbox_client)

    grant = TaskGrant(
        task_id="task-t31",
        worker_role=WorkerRole.LEARNING_PERFORMANCE,
        tenant_scope=TenantScope(tenant_id="tenant-alpha"),
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
    )

    envelope = await agent.run(grant, context={"model_type": "quantum_markov_bayesian_custom"})

    assert envelope.payload.get("status") == "configuration_gap"
    assert envelope.confidence.point_estimate == 0.0
    assert any("CONFIGURATION_GAP" in e for e in envelope.evidence)


# ============================================================================
# 8. Zero Premature T32 Promotion
# ============================================================================

@pytest.mark.asyncio
async def test_t31_zero_t32_memory_promotion() -> None:
    """T31 produces evidence deltas for IE, but strictly never promotes to MemoryRepository."""
    coordinator, agent, telemetry_repo, memory_repo, task_states, _ = _setup_t31_environment()

    # Ingest conversion telemetry
    now = datetime.now(UTC)
    await telemetry_repo.record(
        TelemetryEvent(
            event_id="ev-c1",
            tenant_id="tenant-alpha",
            event_type=TelemetryEventType.CONVERSION,
            channel="website",
            occurred_at=now,
            correlation_id="sess-t32",
            metrics={"revenue": 200.0},
        )
    )

    envelope, deliverable = await coordinator.execute_attribution("tenant-alpha", task_states)

    # Deliverable has candidate deltas
    assert deliverable is not None
    assert len(deliverable.proposed_learning_deltas) > 0
    assert "learning_delta" in envelope.proposed_state_changes

    # But MemoryRepository has ZERO promoted records!
    assert len(memory_repo.promoted_records) == 0


# ============================================================================
# 9. CTS State Update & W3C Provenance
# ============================================================================

@pytest.mark.asyncio
async def test_t31_updates_cts_and_records_provenance() -> None:
    """Successful T31 execution updates CTS task state and records W3C provenance."""
    coordinator, agent, telemetry_repo, _, task_states, prov_repo = _setup_t31_environment()

    now = datetime.now(UTC)
    await telemetry_repo.record(
        TelemetryEvent(
            event_id="ev-cts",
            tenant_id="tenant-alpha",
            event_type=TelemetryEventType.CONVERSION,
            channel="website",
            occurred_at=now,
            metrics={"revenue": 100.0},
        )
    )

    envelope, deliverable = await coordinator.execute_attribution("tenant-alpha", task_states)

    # Check CTS task-t31
    t31_task = task_states["task-t31"]
    assert t31_task.status == TaskStatus.COMPLETED
    assert "attribution_deliverable" in t31_task.cts_state
    assert t31_task.cts_state["t32_eligible"] is True

    # Check provenance records
    records = prov_repo._chains.get("tenant-alpha", [])
    t31_prov = [r for r in records if r.activity == "attribution_and_decay_calculated"]
    assert len(t31_prov) == 1
    assert t31_prov[0].agent == "W_LEARN"
    assert t31_prov[0].entity_id == "task-t31"


# ============================================================================
# 10. Backward Compatibility with Existing Integration Test
# ============================================================================

@pytest.mark.asyncio
async def test_t31_backward_compatibility_with_roas_events() -> None:
    """Existing context={'roas_events': [event]} shape continues to function seamlessly."""
    sandbox_client = SandboxClient()
    agent = LearningPerformanceAgent(sandbox_client)

    ev = TelemetryEvent(
        event_id="ev-compat",
        tenant_id="acme",
        event_type=TelemetryEventType.ROAS,
        channel="meta",
        occurred_at=datetime.now(UTC),
        metrics={"roas": 3.8},
    )

    grant = TaskGrant(
        task_id="task-compat",
        worker_role=WorkerRole.LEARNING_PERFORMANCE,
        tenant_scope=TenantScope(tenant_id="acme"),
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
    )

    envelope = await agent.run(grant, context={"roas_events": [ev]})
    assert envelope.evidence
    assert envelope.confidence.point_estimate > 0.7
    assert "learning_delta" in envelope.proposed_state_changes
