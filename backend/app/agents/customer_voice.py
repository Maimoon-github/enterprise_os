"""W_VOICE: tickets, reviews, sentiment, and objection analysis."""

from __future__ import annotations

from app.agents.base import BoundedWorkerAgent
from app.schemas.agent_contracts import TaskGrant
from app.schemas.sandbox import SandboxCapability


class CustomerVoiceAgent(BoundedWorkerAgent):
    """Requests S_PARSE execution through the sandbox wrapper."""

    capability = SandboxCapability.PARSE

    def build_payload(self, grant: TaskGrant, context: dict[str, object]) -> dict[str, str]:
        feedback = str(context.get("feedback_text", context.get("query", "Customer reviews and feedback.")))
        return {
            "task_id": grant.task_id,
            "objective": "parse_customer_sentiment",
            "feedback_text": feedback,
        }