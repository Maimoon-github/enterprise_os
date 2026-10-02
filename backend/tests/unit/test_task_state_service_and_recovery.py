"""Unit tests for TaskStateService, checkpoints, holds, retries, and recovery."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
import pytest

from app.core.exceptions import InvalidTransitionError
from app.orchestration.task_state_machine import TaskStateMachine
from app.persistence.repositories.task_state import TaskStateRepository
from app.schemas.governance import WorkerRole
from app.schemas.task_state import CanonicalTaskState, TaskStatus
from app.services.provenance import ProvenanceRecorder
from app.services.task_state import TaskStateService
from tests.conftest import FakeProvenanceRepository


class _FakeTaskStateRepository:
    def __init__(self) -> None:
        self.states: dict[str, CanonicalTaskState] = {}

    async def save_state(self, tenant_id: str, state: CanonicalTaskState) -> None:
        self.states[state.task_id] = state

    async def require(self, task_id: str) -> CanonicalTaskState:
        if task_id not in self.states:
            raise KeyError(f"Task {task_id} not found")
        return self.states[task_id]


@pytest.fixture
def fake_cts_service() -> TaskStateService:
    repo = _FakeTaskStateRepository()
    provenance = ProvenanceRecorder(FakeProvenanceRepository())
    return TaskStateService(
        repository=repo,
        state_machine=TaskStateMachine(),
        provenance_recorder=provenance,
        max_retries=2,
    )


@pytest.mark.asyncio
async def test_task_state_service_transitions_and_checkpoints(fake_cts_service: TaskStateService) -> None:
    initial = CanonicalTaskState(
        task_id="task-cts-1",
        directive_id="dir-1",
        worker_role=WorkerRole.STRATEGY,
        status=TaskStatus.PENDING,
    )
    await fake_cts_service.save_state("tenant-1", initial)

    # Transition PENDING -> GRANTED
    granted = await fake_cts_service.transition("tenant-1", initial, TaskStatus.GRANTED, note="Grant issued")
    assert granted.status == TaskStatus.GRANTED
    assert len(granted.checkpoints) == 1
    assert granted.checkpoints[0].note == "Grant issued"

    # Fetch from repository
    loaded = await fake_cts_service.get_state("task-cts-1")
    assert loaded.status == TaskStatus.GRANTED


@pytest.mark.asyncio
async def test_task_hold_and_resume_flow(fake_cts_service: TaskStateService) -> None:
    task = CanonicalTaskState(
        task_id="task-hold-1",
        directive_id="dir-1",
        worker_role=WorkerRole.CREATIVE_CONTENT,
        status=TaskStatus.IN_PROGRESS,
    )
    await fake_cts_service.save_state("tenant-1", task)

    # Place on hold
    held = await fake_cts_service.hold_task("tenant-1", "task-hold-1", reason="Waiting for brand asset")
    assert held.status == TaskStatus.HELD
    assert held.hold_reason == "Waiting for brand asset"

    # Resume
    resumed = await fake_cts_service.resume_task("tenant-1", "task-hold-1", target_status=TaskStatus.IN_PROGRESS)
    assert resumed.status == TaskStatus.IN_PROGRESS
    assert resumed.hold_reason is None


@pytest.mark.asyncio
async def test_failure_handling_and_retry_exhaustion(fake_cts_service: TaskStateService) -> None:
    task = CanonicalTaskState(
        task_id="task-retry-1",
        directive_id="dir-1",
        worker_role=WorkerRole.DEVELOPMENT,
        status=TaskStatus.IN_PROGRESS,
    )
    await fake_cts_service.save_state("tenant-1", task)

    # Attempt 1 fails -> Held
    held_1 = await fake_cts_service.handle_task_failure("tenant-1", "task-retry-1", "Timeout in sandbox")
    assert held_1.status == TaskStatus.HELD

    # Resume and Attempt 2 fails -> Held
    resumed = await fake_cts_service.resume_task("tenant-1", "task-retry-1", target_status=TaskStatus.IN_PROGRESS)
    held_2 = await fake_cts_service.handle_task_failure("tenant-1", "task-retry-1", "Timeout again")
    assert held_2.status == TaskStatus.HELD

    # Resume and Attempt 3 fails -> Max retries (2) exhausted -> FAILED
    resumed = await fake_cts_service.resume_task("tenant-1", "task-retry-1", target_status=TaskStatus.IN_PROGRESS)
    failed = await fake_cts_service.handle_task_failure("tenant-1", "task-retry-1", "Fatal memory error")
    assert failed.status == TaskStatus.FAILED


@pytest.mark.asyncio
async def test_task_state_service_concurrency_conflict_rejected() -> None:
    class _CasTaskRepo:
        def __init__(self) -> None:
            self.states: dict[str, CanonicalTaskState] = {}

        async def compare_and_swap_state(
            self, tenant_id: str, expected_version: int, state: CanonicalTaskState
        ) -> bool:
            current = self.states.get(state.task_id)
            if current is not None and current.version != expected_version:
                return False
            self.states[state.task_id] = state
            return True

        async def require(self, task_id: str) -> CanonicalTaskState:
            return self.states[task_id]

    repo = _CasTaskRepo()
    service = TaskStateService(repository=repo, state_machine=TaskStateMachine())

    initial = CanonicalTaskState(
        task_id="task-cas-1",
        directive_id="dir-1",
        worker_role=WorkerRole.STRATEGY,
        status=TaskStatus.PENDING,
        version=0,
    )
    repo.states[initial.task_id] = initial

    # First transition advances version to 1
    t1 = await service.transition("tenant-1", initial, TaskStatus.GRANTED)
    assert t1.status == TaskStatus.GRANTED
    assert t1.version == 1

    # Stale transition using initial (version 0) fails closed with InvalidTransitionError
    with pytest.raises(InvalidTransitionError, match="Concurrency conflict"):
        await service.transition("tenant-1", initial, TaskStatus.HELD)


@pytest.mark.asyncio
async def test_task_state_service_recover_task_checkpoint() -> None:
    from tests.conftest import FakeProvenanceRepository

    class _CasTaskRepo:
        def __init__(self) -> None:
            self.states: dict[str, CanonicalTaskState] = {}

        async def compare_and_swap_state(
            self, tenant_id: str, expected_version: int, state: CanonicalTaskState
        ) -> bool:
            current = self.states.get(state.task_id)
            if current is not None and current.version != expected_version:
                return False
            self.states[state.task_id] = state
            return True

        async def require(self, task_id: str) -> CanonicalTaskState:
            return self.states[task_id]

        async def save_state(self, tenant_id: str, state: CanonicalTaskState) -> None:
            self.states[state.task_id] = state

    prov_repo = FakeProvenanceRepository()
    recorder = ProvenanceRecorder(prov_repo)
    repo = _CasTaskRepo()
    service = TaskStateService(repository=repo, state_machine=TaskStateMachine(), provenance_recorder=recorder)

    initial = CanonicalTaskState(
        task_id="task-rec-1",
        directive_id="dir-1",
        worker_role=WorkerRole.CREATIVE_CONTENT,
        status=TaskStatus.PENDING,
        version=0,
    )
    repo.states[initial.task_id] = initial

    granted = await service.transition("tenant-1", initial, TaskStatus.GRANTED, note="cp-1")
    in_prog = await service.transition("tenant-1", granted, TaskStatus.IN_PROGRESS, note="cp-2")
    held = await service.transition("tenant-1", in_prog, TaskStatus.HELD, note="cp-3")
    assert held.status == TaskStatus.HELD
    assert held.version == 3

    # Recover to cp-2 (IN_PROGRESS)
    target_cp_id = in_prog.checkpoints[-1].checkpoint_id
    restored = await service.recover_task_checkpoint("tenant-1", "task-rec-1", target_cp_id)
    assert restored.status == TaskStatus.IN_PROGRESS
    assert restored.version == 4

    # Verify provenance recorded
    chain = await recorder.audit_chain("tenant-1")
    assert any(r.activity == "task_checkpoint_recovery" for r in chain)


@pytest.mark.asyncio
async def test_task_state_service_audit_write_failure_blocks_transition() -> None:
    class _FailingProvenanceRecorder:
        async def record(self, *args, **kwargs) -> None:
            raise RuntimeError("Audit ledger unavailable; storage disconnected")

    class _SimpleRepo:
        def __init__(self) -> None:
            self.states: dict[str, CanonicalTaskState] = {}

        async def save_state(self, tenant_id: str, state: CanonicalTaskState) -> None:
            self.states[state.task_id] = state

        async def require(self, task_id: str) -> CanonicalTaskState:
            return self.states[task_id]

    service = TaskStateService(
        repository=_SimpleRepo(),
        state_machine=TaskStateMachine(),
        provenance_recorder=_FailingProvenanceRecorder(),  # type: ignore[arg-type]
    )

    initial = CanonicalTaskState(
        task_id="task-audit-fail",
        directive_id="dir-1",
        worker_role=WorkerRole.DEVELOPMENT,
        status=TaskStatus.PENDING,
    )

    # Transition fails closed when audit writing fails
    with pytest.raises(RuntimeError, match="Audit ledger unavailable"):
        await service.transition("tenant-1", initial, TaskStatus.GRANTED)


@pytest.mark.asyncio
async def test_task_state_repository_cas_success_and_conflict() -> None:
    session = AsyncMock()
    session_factory = MagicMock(return_value=session)
    session.__aenter__.return_value = session

    repo = TaskStateRepository(session_factory=session_factory)

    state = CanonicalTaskState(
        task_id="task-db-cas-1",
        directive_id="dir-1",
        worker_role=WorkerRole.STRATEGY,
        status=TaskStatus.GRANTED,
        version=1,
    )

    # 1. Matching version (0 in DB, expected 0) -> True and commit
    current_doc = CanonicalTaskState(
        task_id="task-db-cas-1",
        directive_id="dir-1",
        worker_role=WorkerRole.STRATEGY,
        status=TaskStatus.PENDING,
        version=0,
    ).model_dump(mode="json")

    mock_row = MagicMock()
    mock_row.scalar_one_or_none.return_value = current_doc
    session.execute.return_value = mock_row

    result = await repo.compare_and_swap_state("tenant-1", expected_version=0, state=state)
    assert result is True
    session.commit.assert_awaited()

    # 2. Conflicting version (current is 2, expected 0) -> False and NO commit
    current_doc["version"] = 2
    mock_row.scalar_one_or_none.return_value = current_doc
    session.commit.reset_mock()

    result_conflict = await repo.compare_and_swap_state("tenant-1", expected_version=0, state=state)
    assert result_conflict is False
    session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_task_state_repository_cas_deadlock_retry() -> None:
    session1 = AsyncMock()
    session1.__aenter__.return_value = session1
    session1.execute.side_effect = Exception("deadlock detected while locking key")

    session2 = AsyncMock()
    session2.__aenter__.return_value = session2
    current_doc = CanonicalTaskState(
        task_id="task-db-cas-2",
        directive_id="dir-1",
        worker_role=WorkerRole.STRATEGY,
        status=TaskStatus.PENDING,
        version=0,
    ).model_dump(mode="json")
    mock_row = MagicMock()
    mock_row.scalar_one_or_none.return_value = current_doc
    session2.execute.return_value = mock_row

    session_factory = MagicMock(side_effect=[session1, session2])
    repo = TaskStateRepository(session_factory=session_factory)

    state = CanonicalTaskState(
        task_id="task-db-cas-2",
        directive_id="dir-1",
        worker_role=WorkerRole.STRATEGY,
        status=TaskStatus.GRANTED,
        version=1,
    )

    success = await repo.compare_and_swap_state("tenant-1", expected_version=0, state=state, max_attempts=2)
    assert success is True
    session1.rollback.assert_awaited()
    session2.commit.assert_awaited()


@pytest.mark.asyncio
async def test_task_state_repository_cas_fatal_rollback() -> None:
    session = AsyncMock()
    session.__aenter__.return_value = session
    session.execute.side_effect = RuntimeError("Fatal connection aborted")

    session_factory = MagicMock(return_value=session)
    repo = TaskStateRepository(session_factory=session_factory)

    state = CanonicalTaskState(
        task_id="task-db-cas-3",
        directive_id="dir-1",
        worker_role=WorkerRole.STRATEGY,
        status=TaskStatus.GRANTED,
        version=1,
    )

    with pytest.raises(RuntimeError, match="Fatal connection aborted"):
        await repo.compare_and_swap_state("tenant-1", expected_version=0, state=state)

    session.rollback.assert_awaited()


class _MockWorkerAgent:
    capability = None
    allowed_tools: list[str] = []

    def __init__(self, succeeds: bool = True, raises: bool = False) -> None:
        self.succeeds = succeeds
        self.raises = raises

    async def run(self, grant: Any, context: Any) -> Any:
        if self.raises:
            raise RuntimeError("Simulated worker execution crash")
        from app.schemas.agent_contracts import ConfidenceInterval, EvidenceEnvelope

        confidence = ConfidenceInterval(
            point_estimate=0.95 if self.succeeds else 0.0,
            lower_bound=0.8,
            upper_bound=1.0,
        )
        return EvidenceEnvelope(
            task_id=grant.task_id,
            worker_role=grant.worker_role,
            confidence=confidence,
            payload={"domain_status": "success" if self.succeeds else "failed"},
        )


def _build_test_engine(workers: dict[WorkerRole, Any], provenance: ProvenanceRecorder | None = None) -> Any:
    if provenance is None:
        provenance = ProvenanceRecorder(FakeProvenanceRepository())
    from app.mcp.host import McpHost
    from app.orchestration.brand_persona import BrandPersonaResolver
    from app.orchestration.context_assembly import ContextAssembler
    from app.orchestration.dag_scheduler import DagScheduler
    from app.orchestration.evidence_synthesis import EvidenceSynthesizer
    from app.orchestration.hitl_preview_generator import HitlPreviewGenerator
    from app.orchestration.intelligence_engine import IntelligenceEngine
    from app.orchestration.policy_evaluator import PolicyEvaluator
    from app.orchestration.rag_query_dispatch import RagQueryDispatcher
    from app.services.hitl import HitlCoordinator
    from app.services.rag.controller import RagController
    from app.services.rag.freshness import FreshnessPolicy
    from app.services.rag.hybrid_retriever import HybridRetriever
    from app.services.rag.schema_validator import SchemaValidator
    from tests.conftest import FakeVectorRepository

    v_repo = FakeVectorRepository()
    rag_ctrl = RagController(HybridRetriever(v_repo), FreshnessPolicy(), SchemaValidator())
    return IntelligenceEngine(
        policy_evaluator=PolicyEvaluator(),
        dag_scheduler=DagScheduler(),
        task_state_machine=TaskStateMachine(),
        context_assembler=ContextAssembler(RagQueryDispatcher(rag_ctrl), BrandPersonaResolver()),
        evidence_synthesizer=EvidenceSynthesizer(),
        hitl_preview_generator=HitlPreviewGenerator(),
        hitl_coordinator=HitlCoordinator(),
        mcp_host=McpHost(AsyncMock(), AsyncMock()),
        provenance_recorder=provenance,
        workers=workers,
    )


@pytest.mark.asyncio
async def test_background_persistence_and_observable_terminal_state(fake_cts_service: TaskStateService) -> None:
    """Verifies that DAG background execution persists checkpoints and observable terminal status."""
    from app.schemas.governance import Directive, TenantScope, RiskLevel
    directive = Directive(
        directive_id="dir-test-pers",
        tenant_id="tenant-pers",
        scope=TenantScope(tenant_id="tenant-pers"),
        risk_ceiling=RiskLevel.LOW,
        budget_cap=5000.0,
        objective="Verify background persistence",
    )

    task = CanonicalTaskState(
        task_id="task-pers-1",
        directive_id=directive.directive_id,
        tenant_id=directive.tenant_id,
        worker_role=WorkerRole.DEVELOPMENT,
        status=TaskStatus.PENDING,
    )
    await fake_cts_service.save_state(directive.tenant_id, task)

    engine = _build_test_engine(
        workers={WorkerRole.DEVELOPMENT: _MockWorkerAgent(succeeds=True)},
        provenance=fake_cts_service._provenance_recorder,
    )

    result = await engine.execute_dag(
        directive,
        [task],
        task_state_service=fake_cts_service,
    )

    # 1. Returned DagExecutionResult has both envelopes and authoritative task states
    assert "task-pers-1" in result
    assert result.task_states["task-pers-1"].status == TaskStatus.COMPLETED
    assert len(result.task_states["task-pers-1"].checkpoints) == 3

    # 2. Persisted state in repository progressed beyond PENDING to COMPLETED
    persisted = await fake_cts_service.get_state("task-pers-1")
    assert persisted.status == TaskStatus.COMPLETED
    assert [cp.status for cp in persisted.checkpoints] == [
        TaskStatus.GRANTED,
        TaskStatus.IN_PROGRESS,
        TaskStatus.COMPLETED,
    ]
    assert persisted.version == 3


@pytest.mark.asyncio
async def test_persistence_failure_blocks_execution() -> None:
    """Verifies that required persistence failure halts execution and does not advance work."""
    from app.schemas.governance import Directive, TenantScope, RiskLevel
    failing_repo = AsyncMock()
    failing_repo.save_state.side_effect = RuntimeError("Database connection lost during write")

    service = TaskStateService(
        repository=failing_repo,
        state_machine=TaskStateMachine(),
        provenance_recorder=ProvenanceRecorder(FakeProvenanceRepository()),
    )

    directive = Directive(
        directive_id="dir-fail-pers",
        tenant_id="tenant-fail",
        scope=TenantScope(tenant_id="tenant-fail"),
        risk_ceiling=RiskLevel.LOW,
        budget_cap=5000.0,
        objective="Verify persistence error halts work",
    )
    task = CanonicalTaskState(
        task_id="task-fail-p",
        directive_id=directive.directive_id,
        tenant_id=directive.tenant_id,
        worker_role=WorkerRole.DEVELOPMENT,
        status=TaskStatus.PENDING,
    )

    engine = _build_test_engine(
        workers={WorkerRole.DEVELOPMENT: _MockWorkerAgent(succeeds=True)},
        provenance=service._provenance_recorder,
    )

    with pytest.raises(RuntimeError, match="Database connection lost"):
        await engine.execute_dag(
            directive,
            [task],
            task_state_service=service,
        )


@pytest.mark.asyncio
async def test_worker_failure_terminal_persistence(fake_cts_service: TaskStateService) -> None:
    """Verifies that worker execution crash captures FAILED transition and persists it."""
    from app.schemas.governance import Directive, TenantScope, RiskLevel
    directive = Directive(
        directive_id="dir-crash",
        tenant_id="tenant-crash",
        scope=TenantScope(tenant_id="tenant-crash"),
        risk_ceiling=RiskLevel.LOW,
        budget_cap=5000.0,
        objective="Verify crash handling",
    )
    task = CanonicalTaskState(
        task_id="task-crash-1",
        directive_id=directive.directive_id,
        tenant_id=directive.tenant_id,
        worker_role=WorkerRole.DEVELOPMENT,
        status=TaskStatus.PENDING,
    )
    await fake_cts_service.save_state(directive.tenant_id, task)

    engine = _build_test_engine(
        workers={WorkerRole.DEVELOPMENT: _MockWorkerAgent(raises=True)},
        provenance=fake_cts_service._provenance_recorder,
    )

    with pytest.raises(RuntimeError, match="Simulated worker execution crash"):
        await engine.execute_dag(
            directive,
            [task],
            task_state_service=fake_cts_service,
        )

    # Persisted state must be FAILED with checkpoint note
    persisted = await fake_cts_service.get_state("task-crash-1")
    assert persisted.status == TaskStatus.FAILED
    assert persisted.failure_reason is not None
    assert "Simulated worker execution crash" in persisted.failure_reason
    assert persisted.checkpoints[-1].status == TaskStatus.FAILED


@pytest.mark.asyncio
async def test_downstream_task_blocked_when_upstream_held_in_dag(fake_cts_service: TaskStateService) -> None:
    """Verifies downstream task blocked and held when upstream dependency fails validation."""
    from app.core.exceptions import PolicyViolationError
    from app.schemas.governance import Directive, TenantScope, RiskLevel
    from app.schemas.task_state import TaskDependency
    directive = Directive(
        directive_id="dir-dag-held",
        tenant_id="tenant-dag",
        scope=TenantScope(tenant_id="tenant-dag"),
        risk_ceiling=RiskLevel.LOW,
        budget_cap=5000.0,
        objective="Verify blocked DAG dependency",
    )
    task1 = CanonicalTaskState(
        task_id="task-up",
        directive_id=directive.directive_id,
        tenant_id=directive.tenant_id,
        worker_role=WorkerRole.DEVELOPMENT,
        status=TaskStatus.PENDING,
    )
    task2 = CanonicalTaskState(
        task_id="task-down",
        directive_id=directive.directive_id,
        tenant_id=directive.tenant_id,
        worker_role=WorkerRole.STRATEGY,
        status=TaskStatus.PENDING,
        dependencies=[TaskDependency(upstream_task_id="task-up", downstream_task_id="task-down")],
    )
    await fake_cts_service.save_state(directive.tenant_id, task1)
    await fake_cts_service.save_state(directive.tenant_id, task2)

    # Worker for task1 returns zero confidence (fails validation -> HELD)
    engine = _build_test_engine(
        workers={
            WorkerRole.DEVELOPMENT: _MockWorkerAgent(succeeds=False),
            WorkerRole.STRATEGY: _MockWorkerAgent(succeeds=True),
        },
        provenance=fake_cts_service._provenance_recorder,
    )

    with pytest.raises(PolicyViolationError, match="dependencies are not completed"):
        await engine.execute_dag(
            directive,
            [task1, task2],
            task_state_service=fake_cts_service,
        )

    # Upstream is HELD
    persisted1 = await fake_cts_service.get_state("task-up")
    assert persisted1.status == TaskStatus.HELD

    # Downstream is also HELD (persisted with note before raising)
    persisted2 = await fake_cts_service.get_state("task-down")
    assert persisted2.status == TaskStatus.HELD
    assert persisted2.hold_reason is not None and "dependencies are not completed" in persisted2.hold_reason


