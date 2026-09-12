"""W_STRAT: omnichannel roadmaps, funnels, media mix, and budgets."""

from __future__ import annotations

from app.agents.base import BoundedWorkerAgent
from app.schemas.agent_contracts import TaskGrant
from app.schemas.sandbox import SandboxCapability


class StrategyAgent(BoundedWorkerAgent):
    """Requests S_ALLOC execution through the sandbox wrapper."""

    capability = SandboxCapability.ALLOC

    def build_payload(self, grant: TaskGrant, context: dict[str, object]) -> dict[str, str]:
        channels = ",".join(grant.tenant_scope.allowed_channels) or "meta,google,tiktok,linkedin"
        budget = str(context.get("budget_cap", context.get("budget", "10000.0")))
        return {
            "task_id": grant.task_id,
            "operation": "optimize_budget",
            "objective": "propose_media_mix_allocation",
            "channels": channels,
            "budget": budget,
            "allowed_channels": channels,
        }