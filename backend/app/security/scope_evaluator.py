"""W_LEARN: attribution, fatigue, decay, ROAS, and validated learning deltas."""

from __future__ import annotations

from app.agents.base import BoundedWorkerAgent
from app.schemas.agent_contracts import TaskGrant
from app.schemas.sandbox import SandboxCapability


class LearningPerformanceAgent(BoundedWorkerAgent):
    """Requests S_ATTR execution through the sandbox wrapper."""

    capability = SandboxCapability.ATTR

    def build_payload(self, grant: TaskGrant, context: dict[str, object]) -> dict[str, str]:
        return {
            "task_id": grant.task_id,
            "objective": "compute_attribution_and_decay",
        }