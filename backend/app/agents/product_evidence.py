"""W_PROD: product specifications, evidence, claims, and compliance dossiers."""

from __future__ import annotations

from app.agents.base import BoundedWorkerAgent
from app.schemas.agent_contracts import TaskGrant
from app.schemas.sandbox import SandboxCapability


class ProductEvidenceAgent(BoundedWorkerAgent):
    """Requests S_VAL execution through the sandbox wrapper."""

    capability = SandboxCapability.VAL

    def build_payload(self, grant: TaskGrant, context: dict[str, object]) -> dict[str, str]:
        return {
            "task_id": grant.task_id,
            "objective": "validate_product_claims",
        }