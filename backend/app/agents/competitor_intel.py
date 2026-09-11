"""W_COMP: pricing, ad-library, SERP, trend, and positioning intelligence."""

from __future__ import annotations

from app.agents.base import BoundedWorkerAgent
from app.schemas.agent_contracts import TaskGrant
from app.schemas.sandbox import SandboxCapability


class CompetitorIntelAgent(BoundedWorkerAgent):
    """Requests S_SCRAPE execution through the sandbox wrapper."""

    capability = SandboxCapability.SCRAPE

    def build_payload(self, grant: TaskGrant, context: dict[str, object]) -> dict[str, str]:
        return {
            "task_id": grant.task_id,
            "objective": "gather_competitor_intelligence",
        }