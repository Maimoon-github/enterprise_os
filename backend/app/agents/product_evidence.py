"""W_PROD: product specifications, evidence, claims, and compliance dossiers."""

from __future__ import annotations

from app.agents.base import BoundedWorkerAgent
from app.schemas.agent_contracts import TaskGrant
from app.schemas.sandbox import SandboxCapability


class ProductEvidenceAgent(BoundedWorkerAgent):
    """Requests S_VAL execution through the sandbox wrapper."""

    capability = SandboxCapability.VAL

    def build_payload(self, grant: TaskGrant, context: dict[str, object]) -> dict[str, str]:
        claim = str(context.get("claim", context.get("statement", "Clinically tested to improve performance by 40%.")))
        persona = context.get("brand_persona")
        disclaimers = getattr(persona, "required_disclaimers", ())
        disclaimer = disclaimers[0] if disclaimers else "*Results may vary based on usage."
        return {
            "task_id": grant.task_id,
            "objective": "validate_product_claims",
            "claim": claim,
            "required_disclaimer": disclaimer,
        }