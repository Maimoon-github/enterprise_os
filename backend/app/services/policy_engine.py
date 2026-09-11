"""Produces and validates machine-readable policy and compliance envelopes."""
from __future__ import annotations

from uuid import uuid4

from app.schemas.governance import Directive, PolicyEnvelope


class PolicyEngine:
    def compile_envelope(self, directive: Directive) -> PolicyEnvelope:
        return PolicyEnvelope(
            policy_id=str(uuid4()),
            directive_id=directive.directive_id,
            tenant_id=directive.tenant_id,
            scopes=list(directive.scopes),
            budget=directive.budget,
            risk=directive.risk,
        )

    def validate(self, envelope: PolicyEnvelope) -> bool:
        return envelope.budget.amount <= envelope.risk.max_spend
