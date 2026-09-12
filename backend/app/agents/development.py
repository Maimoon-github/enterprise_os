"""W_DEV: CMS schemas, UI layouts, code diffs, and web-development work."""

from __future__ import annotations

from app.agents.base import BoundedWorkerAgent
from app.schemas.agent_contracts import TaskGrant
from app.schemas.sandbox import SandboxCapability


class DevelopmentAgent(BoundedWorkerAgent):
    """Requests S_CODE execution through the sandbox wrapper."""

    capability = SandboxCapability.CODE

    def build_payload(self, grant: TaskGrant, context: dict[str, object]) -> dict[str, str]:
        persona = context.get("brand_persona")
        component = str(context.get("component_name", "LandingHeader"))
        code = str(context.get("code", context.get("schema_content", "")))
        return {
            "task_id": grant.task_id,
            "objective": "generate_code_diff",
            "component_name": component,
            "code": code,
            "brand_voice": getattr(persona, "voice", "neutral"),
        }