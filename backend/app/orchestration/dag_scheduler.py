"""Schedules work according to the canonical task dependency DAG."""

from __future__ import annotations

from app.core.exceptions import GovernedBackendError
from app.schemas.task_state import CanonicalTaskState, TaskStatus


class CyclicDependencyError(GovernedBackendError):
    """Raised when the task dependency graph is not a valid DAG."""


class DagScheduler:
    """Computes ready-to-run tasks from a set of ``CanonicalTaskState`` records."""

    def _upstream_ids(self, task: CanonicalTaskState) -> set[str]:
        return {
            dep.upstream_task_id
            for dep in task.dependencies
            if dep.downstream_task_id == task.task_id
        }

    def topological_order(self, tasks: list[CanonicalTaskState]) -> list[str]:
        """Return task ids in a valid topological order, or raise on a cycle."""

        by_id = {task.task_id: task for task in tasks}
        in_degree = {task.task_id: len(self._upstream_ids(task)) for task in tasks}
        ready = [task_id for task_id, degree in in_degree.items() if degree == 0]
        ordered: list[str] = []

        downstream_index: dict[str, list[str]] = {task_id: [] for task_id in by_id}
        for task in tasks:
            for upstream_id in self._upstream_ids(task):
                downstream_index.setdefault(upstream_id, []).append(task.task_id)

        while ready:
            current = ready.pop(0)
            ordered.append(current)
            for downstream_id in downstream_index.get(current, []):
                in_degree[downstream_id] -= 1
                if in_degree[downstream_id] == 0:
                    ready.append(downstream_id)

        if len(ordered) != len(tasks):
            raise CyclicDependencyError("Task dependency graph contains a cycle.")
        return ordered

    def next_ready_tasks(self, tasks: list[CanonicalTaskState]) -> list[CanonicalTaskState]:
        """Return pending/granted tasks whose upstream dependencies are complete."""

        by_id = {task.task_id: task for task in tasks}
        ready: list[CanonicalTaskState] = []
        for task in tasks:
            if task.status not in (TaskStatus.PENDING, TaskStatus.GRANTED):
                continue
            upstream_ids = self._upstream_ids(task)
            if all(
                by_id[uid].status == TaskStatus.COMPLETED
                for uid in upstream_ids
                if uid in by_id
            ):
                ready.append(task)
        return ready