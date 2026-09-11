"""Central Model-A orchestrator and multi-brand execution coordinator."""
from __future__ import annotations

from app.orchestration.context_assembly import ContextAssembler
from app.orchestration.dag_scheduler import DagScheduler
from app.orchestration.hitl_preview_generator import HitlPreviewGenerator
from app.orchestration.policy_evaluator import PolicyEvaluator
from app.orchestration.rag_query_dispatch import RagQueryDispatcher
from app.orchestration.task_state_machine import TaskStateMachine
from app.schemas.governance import PolicyEnvelope


class IntelligenceEngine:
    def __init__(
        self,
        policy: PolicyEvaluator | None = None,
        dag: DagScheduler | None = None,
        context: ContextAssembler | None = None,
        rag: RagQueryDispatcher | None = None,
        preview: HitlPreviewGenerator | None = None,
        state: TaskStateMachine | None = None,
    ) -> None:
        self.policy = policy or PolicyEvaluator()
        self.dag = dag or DagScheduler()
        self.context = context or ContextAssembler()
        self.rag = rag or RagQueryDispatcher()
        self.preview = preview or HitlPreviewGenerator()
        self.state = state or TaskStateMachine()

    def run(self, envelope: PolicyEnvelope) -> dict:
        decision = self.policy.evaluate(envelope)
        if not decision.allowed:
            return {"status": "rejected", "reason": decision.reason}
        plan = self.dag.plan(envelope)
        return {"status": "scheduled", "plan": plan}
