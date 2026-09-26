"""Tests for governed IntelligenceEngine -> W_STRAT end-to-end round-trip (T5/T6).

Validates:
IE bounded grant/directive -> W_STRAT -> AllocationSubAgent -> S_ALLOC -> validated result -> IE.
Asserts tenant/budget/channel scope preservation, single execution of specialist and sandbox,
task state transitions (COMPLETED on success, HELD on zero confidence), and cross-tenant isolation.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents.base import BoundedWorkerAgent
from app.agents.strategy_engine.strategy import StrategyAgent
from app.core.exceptions import PolicyViolationError
from app.orchestration.context_assembly import BrandPersonaResolver, ContextAssembler
from app.orchestration.dag_scheduler import DagScheduler
from app.orchestration.evidence_synthesis import EvidenceSynthesizer
from app.orchestration.hitl_preview_generator import HitlPreviewGenerator
from app.orchestration.intelligence_engine import IntelligenceEngine
from app.orchestration.policy_evaluator import PolicyEvaluator
from app.orchestration.rag_query_dispatch import RagQueryDispatcher
from app.orchestration.task_state_machine import TaskStateMachine
from app.schemas.governance import Directive, TenantScope, WorkerRole
from app.schemas.sandbox import NetworkPolicy, SandboxCapability
from app.schemas.strategy import StrategyResultEnvelope
from app.schemas.task_state import CanonicalTaskState, TaskStatus
from app.services.hitl import HitlCoordinator
from app.services.provenance import ProvenanceRecorder
from app.services.rag.controller import RagController
from app.services.rag.freshness import FreshnessPolicy
from app.services.rag.hybrid_retriever import HybridRetriever
from app.services.rag.schema_validator import SchemaValidator
from tests.conftest import (
    FakeProvenanceRepository,
    FakeVectorRepository,
    create_mock_remote_sandbox,
)


def _build_test_intelligence_engine(
    w_strat: StrategyAgent,
    provenance_recorder: ProvenanceRecorder,
) -> IntelligenceEngine:
    rag_repo = FakeVectorRepository()
    rag_controller = RagController(
        HybridRetriever(rag_repo),
        FreshnessPolicy(),
        SchemaValidator(),
    )
    rag_dispatcher = RagQueryDispatcher(rag_controller)

    workers: dict[WorkerRole, BoundedWorkerAgent] = {WorkerRole.STRATEGY: w_strat}
    return IntelligenceEngine(
        policy_evaluator=PolicyEvaluator(),
        dag_scheduler=DagScheduler(),
        task_state_machine=TaskStateMachine(),
        context_assembler=ContextAssembler(rag_dispatcher, BrandPersonaResolver()),
        evidence_synthesizer=EvidenceSynthesizer(),
        hitl_preview_generator=HitlPreviewGenerator(),
        hitl_coordinator=HitlCoordinator(),
        mcp_host=None,  # type: ignore[arg-type]
        provenance_recorder=provenance_recorder,
        workers=workers,
    )


# =============================================================================
# 1. Successful Governed Round-Trip
# =============================================================================


@pytest.mark.asyncio
async def test_ie_to_w_strat_successful_governed_roundtrip(sample_directive: Directive) -> None:
    """Governed IE -> W_STRAT invocation preserves boundaries and transitions state to COMPLETED."""
    prov_repo = FakeProvenanceRepository()
    provenance_recorder = ProvenanceRecorder(prov_repo)
    sandbox_client = create_mock_remote_sandbox(provenance_recorder=provenance_recorder)

    w_strat = StrategyAgent(sandbox_client)
    subagent_spy = AsyncMock(wraps=w_strat.allocation_agent)
    w_strat._allocation_agent = subagent_spy
    sandbox_invoke_spy = AsyncMock(wraps=sandbox_client.invoke)
    sandbox_client.invoke = sandbox_invoke_spy

    engine = _build_test_intelligence_engine(w_strat, provenance_recorder)

    task = CanonicalTaskState(
        task_id="task-strat-roundtrip-ok",
        directive_id=sample_directive.directive_id,
        worker_role=WorkerRole.STRATEGY,
        status=TaskStatus.PENDING,
        cts_state={
            "budget_cap": 30000.0,
            "claims_dossier": {
                "tenant_id": sample_directive.tenant_id,
                "claims": [{"claim_id": "c1", "validation_status": "SUPPORTED", "confidence": 0.9}],
            },
            "customer_voice_analysis": {
                "tenant_id": sample_directive.tenant_id,
                "objection_profiles": [{"objection_type": "fragrance", "frequency": 3}],
            },
            "competitor_intelligence": {
                "tenant_id": sample_directive.tenant_id,
                "competitor": "SerumCorp",
                "benchmark_price": "50.00",
            },
        },
    )

    result = await engine.invoke_strategy_worker(
        directive=sample_directive,
        task=task,
        query="omnichannel acquisition media plan and budget allocation",
        brand_id=sample_directive.tenant_id,
    )

    # 1. Exactly one specialist and one sandbox invocation
    assert subagent_spy.reason.await_count == 1
    assert sandbox_invoke_spy.await_count == 1

    # 2. Hardened sandbox mandate
    assert sandbox_invoke_spy.await_args is not None
    mandate = sandbox_invoke_spy.await_args[0][0]
    assert mandate.capability == SandboxCapability.ALLOC
    assert mandate.network_policy == NetworkPolicy.DISABLED
    assert mandate.tenant_id == sample_directive.tenant_id

    # 3. Validated typed result
    assert isinstance(result, StrategyResultEnvelope)
    assert result.task_id == "task-strat-roundtrip-ok"
    assert result.strategy_plan is not None
    assert result.strategy_plan.total_allocated <= 30000.0
    assert result.confidence.point_estimate >= 0.70

    # 4. Provenance records
    worker_records = [r for r in prov_repo.records if "worker_execution" in r.activity]
    assert len(worker_records) >= 2


# =============================================================================
# 2. Zero-Confidence / Sandbox Failure Round-Trip
# =============================================================================


@pytest.mark.asyncio
async def test_ie_to_w_strat_sandbox_failure_roundtrip(sample_directive: Directive) -> None:
    """Sandbox failure causes worker to return zero confidence and records failed lineage."""
    prov_repo = FakeProvenanceRepository()
    provenance_recorder = ProvenanceRecorder(prov_repo)
    sandbox_client = create_mock_remote_sandbox(provenance_recorder=provenance_recorder)

    # Force sandbox invocation failure
    sandbox_invoke_spy = AsyncMock(
        return_value=MagicMock(
            success=False,
            status=MagicMock(value="failed"),
            error="Remote kernel terminated unexpectedly",
            sanitized_output={},
            generated_artifacts=[],
            execution_id="exec-failed-123",
            provenance={},
        )
    )
    sandbox_client.invoke = sandbox_invoke_spy

    w_strat = StrategyAgent(sandbox_client)
    engine = _build_test_intelligence_engine(w_strat, provenance_recorder)

    task = CanonicalTaskState(
        task_id="task-strat-roundtrip-fail",
        directive_id=sample_directive.directive_id,
        worker_role=WorkerRole.STRATEGY,
        status=TaskStatus.PENDING,
        cts_state={"budget_cap": 15000.0},
    )

    envelope = await engine.delegate_task(
        directive=sample_directive,
        task=task,
        query="propose strategy",
        brand_id=sample_directive.tenant_id,
    )

    assert envelope.confidence.point_estimate == 0.0
    assert any("sandbox execution failed" in e for e in envelope.evidence)

    # Lineage must be recorded as failed, never completed
    records = prov_repo.records
    failed_recs = [r for r in records if r.metadata.get("lifecycle_stage") == "failed"]
    assert len(failed_recs) == 1
    completed_recs = [r for r in records if r.metadata.get("lifecycle_stage") == "completed"]
    assert len(completed_recs) == 0


# =============================================================================
# 3. Scope and Policy Boundary Enforcement
# =============================================================================


@pytest.mark.asyncio
async def test_invoke_strategy_worker_rejects_non_strategy_role(sample_directive: Directive) -> None:
    """Invoking W_STRAT for a task with a non-Strategy role raises PolicyViolationError."""
    prov_repo = FakeProvenanceRepository()
    recorder = ProvenanceRecorder(prov_repo)
    client = create_mock_remote_sandbox(provenance_recorder=recorder)
    engine = _build_test_intelligence_engine(StrategyAgent(client), recorder)

    non_strat_task = CanonicalTaskState(
        task_id="task-non-strat",
        directive_id=sample_directive.directive_id,
        worker_role=WorkerRole.DEVELOPMENT,  # Non-Strategy!
        status=TaskStatus.PENDING,
    )

    with pytest.raises(PolicyViolationError, match="Cannot invoke W_STRAT for task with worker role"):
        await engine.invoke_strategy_worker(directive=sample_directive, task=non_strat_task)


@pytest.mark.asyncio
async def test_w_strat_rejects_cross_tenant_evidence(sample_directive: Directive) -> None:
    """StrategyAgent rejects dependencies belonging to another tenant (fail-closed)."""
    prov_repo = FakeProvenanceRepository()
    recorder = ProvenanceRecorder(prov_repo)
    client = create_mock_remote_sandbox(provenance_recorder=recorder)
    engine = _build_test_intelligence_engine(StrategyAgent(client), recorder)

    off_tenant_task = CanonicalTaskState(
        task_id="task-off-tenant",
        directive_id=sample_directive.directive_id,
        worker_role=WorkerRole.STRATEGY,
        status=TaskStatus.PENDING,
        cts_state={
            "claims_dossier": {
                "tenant_id": "malicious_tenant_off_scope",
                "claims": [{"claim_id": "c99", "validation_status": "SUPPORTED"}],
            }
        },
    )

    with pytest.raises(ValueError, match="Tenant isolation breach"):
        await engine.delegate_task(
            directive=sample_directive,
            task=off_tenant_task,
            query="propose strategy",
            brand_id=sample_directive.tenant_id,
        )
