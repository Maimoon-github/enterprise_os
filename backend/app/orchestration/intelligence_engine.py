"""Central Model-A orchestrator and multi-brand execution coordinator.

The ``IntelligenceEngine`` is the only component that mints
``IntelligenceEngineToken`` instances, holds the ``McpHost``, and is
permitted to delegate bounded task grants to worker agents. It composes
every other orchestration module into the directive -> workers -> HITL ->
actuation -> telemetry -> learning flow described by the architecture.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from app.agents.base import BoundedWorkerAgent
from app.core.exceptions import PolicyViolationError
from app.mcp.host import McpHost
from app.orchestration.context_assembly import ContextAssembler
from app.orchestration.dag_scheduler import DagScheduler
from app.orchestration.evidence_synthesis import EvidenceSynthesizer
from app.orchestration.hitl_preview_generator import HitlPreviewGenerator
from app.orchestration.policy_evaluator import PolicyEvaluator
from app.orchestration.rag_query_dispatch import IntelligenceEngineToken
from app.orchestration.task_state_machine import TaskStateMachine
from app.schemas.action_preview import ActionPreview, ActionPreviewKind
from app.schemas.agent_contracts import ContextRequest, EvidenceEnvelope, TaskGrant
from app.schemas.dispatch import DispatchDirective
from app.schemas.governance import Directive, RiskLevel, WorkerRole
from app.schemas.task_state import CanonicalTaskState, TaskStatus
from app.services.hitl import HitlCoordinator
from app.services.provenance import ProvenanceRecorder


class IntelligenceEngine:
    """Composition root coordinating directives through to actuation."""

    def __init__(
        self,
        *,
        policy_evaluator: PolicyEvaluator,
        dag_scheduler: DagScheduler,
        task_state_machine: TaskStateMachine,
        context_assembler: ContextAssembler,
        evidence_synthesizer: EvidenceSynthesizer,
        hitl_preview_generator: HitlPreviewGenerator,
        hitl_coordinator: HitlCoordinator,
        mcp_host: McpHost,
        provenance_recorder: ProvenanceRecorder,
        workers: dict[WorkerRole, BoundedWorkerAgent],
    ) -> None:
        self._policy_evaluator = policy_evaluator
        self._dag_scheduler = dag_scheduler
        self._task_state_machine = task_state_machine
        self._context_assembler = context_assembler
        self._evidence_synthesizer = evidence_synthesizer
        self._hitl_preview_generator = hitl_preview_generator
        self._hitl_coordinator = hitl_coordinator
        self._mcp_host = mcp_host
        self._provenance_recorder = provenance_recorder
        self._workers = workers

    def _mint_token(self) -> IntelligenceEngineToken:
        return IntelligenceEngineToken(issued_to="intelligence_engine")

    async def delegate_task(
        self,
        directive: Directive,
        task: CanonicalTaskState,
        *,
        query: str,
    ) -> EvidenceEnvelope:
        """Delegate a single bounded task grant to its worker and return its evidence.

        Raises ``PolicyViolationError`` if the delegation is not permitted
        under the parent directive's scope and risk ceiling.
        """

        decision = self._policy_evaluator.evaluate_delegation(
            directive, directive.scope, directive.risk_ceiling
        )
        if not decision.allowed:
            raise PolicyViolationError(decision.reason)

        granted_state = self._task_state_machine.transition(
            task, TaskStatus.GRANTED, checkpoint_id=str(uuid.uuid4())
        )
        self._task_state_machine.transition(
            granted_state, TaskStatus.IN_PROGRESS, checkpoint_id=str(uuid.uuid4())
        )

        grant = TaskGrant(
            task_id=task.task_id,
            worker_role=task.worker_role,
            tenant_scope=directive.scope,
            task_scope=f"{task.worker_role.value} task for {directive.directive_id}",
            sandbox_capabilities=[self._workers[task.worker_role].capability.value],
            token_budget=10000,
            risk_tier=directive.risk_ceiling,
            expires_at=datetime.now(UTC) + timedelta(minutes=30),
        )
        context = await self._context_assembler.assemble(
            self._mint_token(),
            tenant_id=directive.tenant_id,
            request=ContextRequest(task_id=task.task_id, worker_role=task.worker_role, query=query),
        )
        context["budget_cap"] = directive.budget_cap
        context["directive_id"] = directive.directive_id

        worker = self._workers[task.worker_role]
        envelope = await worker.run(grant, context)

        if envelope.confidence.point_estimate > 0.0:
            self._task_state_machine.transition(
                task, TaskStatus.COMPLETED, checkpoint_id=str(uuid.uuid4())
            )
        else:
            self._task_state_machine.transition(
                task, TaskStatus.HELD, checkpoint_id=str(uuid.uuid4()), note="Execution produced zero confidence"
            )

        await self._provenance_recorder.record(
            tenant_id=directive.tenant_id,
            entity_id=task.task_id,
            activity="worker_execution",
            agent=task.worker_role.value,
        )

        return envelope

    async def execute_dag(
        self,
        directive: Directive,
        tasks: list[CanonicalTaskState],
        *,
        queries: dict[str, str] | None = None,
    ) -> dict[str, EvidenceEnvelope]:
        """Execute a full DAG of tasks for ``directive`` in topological dependency order."""
        queries = queries or {}
        ordered_ids = self._dag_scheduler.topological_order(tasks)
        tasks_by_id = {t.task_id: t for t in tasks}
        completed_tasks: dict[str, CanonicalTaskState] = {}
        envelopes: dict[str, EvidenceEnvelope] = {}

        for task_id in ordered_ids:
            task = tasks_by_id[task_id]
            # Verify upstream dependencies completed
            upstream_ids = {
                dep.upstream_task_id
                for dep in task.dependencies
                if dep.downstream_task_id == task_id
            }
            if not all(uid in completed_tasks and completed_tasks[uid].status == TaskStatus.COMPLETED for uid in upstream_ids):
                raise PolicyViolationError(f"Task {task_id} dependencies are not completed.")

            query = queries.get(task_id, f"{task.worker_role.value} execution for {directive.objective}")
            envelope = await self.delegate_task(directive, task, query=query)
            envelopes[task_id] = envelope
            completed_tasks[task_id] = task.model_copy(update={"status": TaskStatus.COMPLETED})

        return envelopes

    def ready_tasks(self, tasks: list[CanonicalTaskState]) -> list[CanonicalTaskState]:
        """Return the subset of ``tasks`` whose dependencies are satisfied."""

        return self._dag_scheduler.next_ready_tasks(tasks)

    async def dispatch_after_approval(self, dispatch: DispatchDirective) -> dict[str, str]:
        """Actuate an approved, signed dispatch through the MCP host."""

        result = await self._mcp_host.actuate(dispatch)
        await self._provenance_recorder.record(
            tenant_id="global",
            entity_id=dispatch.dispatch_id,
            activity="actuation_dispatched",
            agent="mcp_host",
        )
        return result

    async def build_preview(
        self,
        envelopes: list[EvidenceEnvelope],
        *,
        kind: ActionPreviewKind,
        risk_level: RiskLevel,
        spend_amount: float | None = None,
        diff: str | None = None,
    ) -> ActionPreview:
        """Synthesize evidence and produce a mandatory human-review preview."""

        synthesized = self._evidence_synthesizer.synthesize(envelopes)
        # Extract diff if not provided
        if diff is None and kind == ActionPreviewKind.CODE_DIFF:
            for env in envelopes:
                if "diff" in env.payload:
                    diff = env.payload["diff"]
                    break

        # Extract spend if not provided
        if spend_amount is None and kind == ActionPreviewKind.SPEND:
            for env in envelopes:
                if "budget_total" in env.payload:
                    try:
                        spend_amount = float(env.payload["budget_total"])
                    except ValueError:
                        pass
                    break

        preview = self._hitl_preview_generator.generate(
            preview_id=str(uuid.uuid4()),
            evidence=synthesized,
            kind=kind,
            risk_level=risk_level,
            spend_amount=spend_amount,
            diff=diff,
        )
        self._hitl_coordinator.submit_for_approval(preview)
        return preview