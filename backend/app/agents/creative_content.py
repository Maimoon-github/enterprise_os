"""W_CREAT: copy variants, hooks, visual briefs, and social schedules."""

from __future__ import annotations

from app.agents.base import BoundedWorkerAgent
from app.schemas.agent_contracts import TaskGrant
from app.schemas.sandbox import SandboxCapability


class CreativeContentAgent(BoundedWorkerAgent):
    """Requests S_COPY execution through the sandbox wrapper."""

    capability = SandboxCapability.COPY

    def build_payload(self, grant: TaskGrant, context: dict[str, object]) -> dict[str, str]:
        persona = context.get("brand_persona")
        return {
            "task_id": grant.task_id,
            "objective": "generate_copy_variants",
            "brand_voice": getattr(persona, "voice", "neutral"),
        }