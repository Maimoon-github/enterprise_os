"""Applies policy decisions before delegation and execution."""
from __future__ import annotations

from dataclasses import dataclass

from app.schemas.governance import PolicyEnvelope


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason: str | None = None


class PolicyEvaluator:
    def evaluate(self, envelope: PolicyEnvelope) -> PolicyDecision:
        if envelope.budget.amount > envelope.risk.max_spend:
            return PolicyDecision(False, "budget exceeds risk envelope")
        return PolicyDecision(True)
