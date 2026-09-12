"""W_LEARN: attribution, fatigue, decay, ROAS, and validated learning deltas."""

from __future__ import annotations

from app.agents.base import BoundedWorkerAgent
from app.schemas.agent_contracts import TaskGrant
from app.schemas.sandbox import SandboxCapability


class LearningPerformanceAgent(BoundedWorkerAgent):
    """Requests S_ATTR execution through the sandbox wrapper."""

    capability = SandboxCapability.ATTR

    def build_payload(self, grant: TaskGrant, context: dict[str, object]) -> dict[str, str]:
        roas = "3.2"
        events = context.get("roas_events")
        if isinstance(events, list) and events:
            first = events[0]
            metrics = getattr(first, "metrics", {})
            if isinstance(metrics, dict) and "roas" in metrics:
                roas = str(metrics["roas"])
        elif "roas" in context:
            roas = str(context["roas"])

        return {
            "task_id": grant.task_id,
            "objective": "compute_attribution_and_decay",
            "roas": roas,
            "days_active": str(context.get("days_active", "14.0")),
        }