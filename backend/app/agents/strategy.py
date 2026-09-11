"""W_STRAT: omnichannel roadmaps, funnels, media mix, and budgets."""

from __future__ import annotations

from app.agents.base import BoundedWorkerAgent
from app.schemas.agent_contracts import TaskGrant
from app.schemas.sandbox import SandboxCapability


class StrategyAgent(BoundedWorkerAgent):
    """Requests S_ALLOC execution through the sandbox wrapper."""

    capability = SandboxCapability.ALLOC

    def build_payload(self, grant: TaskGrant, context: dict[str, object]) -> dict[str, str]:
        return {
            "task_id": grant.task_id,
            "objective": "propose_media_mix_allocation",
            "allowed_channels": ",".join(grant.tenant_scope.allowed_channels),
        }