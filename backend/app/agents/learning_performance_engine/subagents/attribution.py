"""LEARN-ATTRIBUTION: Specialist sub-agent for multi-touch attribution, MMM contributions, and ROAS."""

from __future__ import annotations

import json
from typing import Any

from app.integrations.sandbox.s_attr_core import compute_attribution_and_roas
from app.schemas.agent_contracts import TaskGrant
from app.schemas.learning_performance import (
    EvidenceCategory,
    LearningEstimate,
    LearningSpecialistResult,
    LearningUncertainty,
    SpecialistStatus,
    UncertaintyKind,
)


class LearningAttributionAgent:
    """Specialist sub-agent for observational touchpoint attribution and ROAS modeling."""

    specialist_id = "LEARN-ATTRIBUTION"
    profile_id = "learn.attribution.v1"

    def __init__(self, sandbox_client: Any = None, llm_client: Any = None) -> None:
        self._sandbox_client = sandbox_client
        self._llm_client = llm_client

    async def run(
        self,
        grant: TaskGrant,
        context: dict[str, Any],
        *,
        attempt_id: str | None = None,
    ) -> LearningSpecialistResult:
        """Execute attribution and safe ROAS computation under Model A governance."""
        task_id = grant.task_id
        grant_tenant = grant.tenant_scope.tenant_id if grant.tenant_scope else "default"
        dataset_version = str(context.get("dataset_version", grant.cts_state.get("dataset_version", "1.0")))

        payload: dict[str, Any] = {
            "task_id": task_id,
            "tenant_id": grant_tenant,
            "operation": "estimate_attribution",
            "model_type": context.get("model_type", "linear"),
            "paths": context.get("paths") or context.get("conversion_paths") or grant.cts_state.get("conversion_paths") or [],
            "spend_data": context.get("spend_data") or context.get("spend") or grant.cts_state.get("spend_data") or {},
        }

        res = compute_attribution_and_roas(payload)
        status = res.get("status")

        if status == "failed":
            return LearningSpecialistResult(
                role=self.specialist_id,
                specialist_profile_id=self.profile_id,
                attempt_id=attempt_id or f"att-{task_id[:8]}",
                dataset_version=dataset_version,
                status=SpecialistStatus.FAILED,
                error_category=res.get("error_category", "attribution_failed"),
                findings=[res.get("error", "Attribution calculation failed")],
            )

        if status == "insufficient_evidence":
            err_msg = res.get("error", "Insufficient attribution evidence")
            return LearningSpecialistResult(
                role=self.specialist_id,
                specialist_profile_id=self.profile_id,
                attempt_id=attempt_id or f"att-{task_id[:8]}",
                dataset_version=dataset_version,
                status=SpecialistStatus.INSUFFICIENT_EVIDENCE,
                insufficient_evidence_reason=err_msg,
                findings=[err_msg],
            )

        estimates: list[LearningEstimate] = []
        model_name = res.get("model_type", "linear")

        # Attribution weights
        for item in res.get("channel_weights", []):
            ch = item["channel"]
            estimates.append(
                LearningEstimate(
                    estimate_id=f"est-attr-{ch}",
                    metric="attribution_weight",
                    estimand="channel_weight",
                    evidence_category=EvidenceCategory.OBSERVATIONAL,
                    tenant_id=grant_tenant,
                    channel=ch,
                    method_name=f"{model_name}_attribution",
                    point_estimate=float(item["weight"]),
                    units="ratio",
                    uncertainty=LearningUncertainty(
                        kind=UncertaintyKind.NOT_APPLICABLE,
                        method="point_weight",
                    ),
                    causal_claim_permitted=False,
                    diagnostics={
                        "attributed_revenue": item["attributed_revenue"],
                        "attributed_conversions": item["attributed_conversions"],
                    },
                    assumptions=["Touchpoints within lookback window contribute according to selected heuristic model."],
                )
            )

        # Safe ROAS metrics
        for item in res.get("roas_metrics", []):
            ch = item["channel"]
            roas_val = item["roas"]
            if roas_val is not None:
                unc = LearningUncertainty(kind=UncertaintyKind.NOT_APPLICABLE, method="deterministic_ratio")
            else:
                unc = LearningUncertainty(
                    kind=UncertaintyKind.UNAVAILABLE,
                    reason_unavailable=item.get("reason", "Undefined denominator"),
                )

            estimates.append(
                LearningEstimate(
                    estimate_id=f"est-roas-{ch}",
                    metric="roas",
                    estimand="attributed_roas",
                    evidence_category=EvidenceCategory.OBSERVATIONAL,
                    tenant_id=grant_tenant,
                    channel=ch,
                    method_name="spend_revenue_ratio",
                    point_estimate=float(roas_val) if roas_val is not None else None,
                    units="ratio",
                    uncertainty=unc,
                    causal_claim_permitted=False,
                    diagnostics={
                        "spend": item["spend"],
                        "revenue": item["revenue"],
                        "status": item["status"],
                        "reason": item["reason"],
                    },
                    assumptions=["Attributed revenue divided by matched spend; non-causal observational metric."],
                )
            )

        reconc = res.get("reconciliation", {})
        findings = [
            f"Attributed total revenue: {reconc.get('attributed_revenue', 0.0)} across {reconc.get('attributed_conversions', 0)} conversions.",
            f"Unattributed revenue: {reconc.get('unattributed_revenue', 0.0)}. Total conversions: {reconc.get('total_conversions', 0)}.",
        ]

        return LearningSpecialistResult(
            role=self.specialist_id,
            specialist_profile_id=self.profile_id,
            attempt_id=attempt_id or f"att-{task_id[:8]}",
            dataset_version=dataset_version,
            status=SpecialistStatus.COMPLETE,
            estimates=estimates,
            findings=findings,
            diagnostic_refs=[f"reconciliation:total_rev={reconc.get('total_revenue', 0.0)}"],
        )
