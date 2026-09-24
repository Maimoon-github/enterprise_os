"""Unit tests for TaskStateService, checkpoints, holds, retries, and recovery."""

from __future__ import annotations

import pytest

from app.core.exceptions import InvalidTransitionError
from app.orchestration.task_state_machine import TaskStateMachine
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
        repository=repo,  # type: ignore[arg-type]
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

