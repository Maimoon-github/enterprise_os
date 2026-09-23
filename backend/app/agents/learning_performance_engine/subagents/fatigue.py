"""LEARN-FATIGUE: Specialist sub-agent for creative wearout and audience saturation analysis."""

from __future__ import annotations

import json
from typing import Any

from app.integrations.sandbox.s_attr_core import compute_creative_fatigue
from app.schemas.agent_contracts import TaskGrant
from app.schemas.learning_performance import (
    EvidenceCategory,
    LearningEstimate,
    LearningSpecialistResult,
    LearningUncertainty,
    SpecialistStatus,
    UncertaintyKind,
)


class LearningFatigueAgent:
    """Specialist sub-agent for longitudinal fatigue analysis and saturation distinction."""

    specialist_id = "LEARN-FATIGUE"
    profile_id = "learn.fatigue.v1"

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
        """Execute longitudinal fatigue trajectories analysis distinguishing wearout from saturation."""
        task_id = grant.task_id
        grant_tenant = grant.tenant_scope.tenant_id if grant.tenant_scope else "default"
        dataset_version = str(context.get("dataset_version", grant.cts_state.get("dataset_version", "1.0")))

        payload: dict[str, Any] = {
            "task_id": task_id,
            "tenant_id": grant_tenant,
            "operation": "analyze_wearout",
            "creatives": context.get("creatives") or grant.cts_state.get("creatives") or [],
            "creative_id": context.get("creative_id"),
            "days_active": context.get("days_active"),
            "roas": context.get("roas"),
            "frequency_trajectory": context.get("frequency_trajectory"),
            "ctr_trajectory": context.get("ctr_trajectory"),
        }

        res = compute_creative_fatigue(payload)
        status = res.get("status")

        if status == "failed":
            return LearningSpecialistResult(
                role=self.specialist_id,
                specialist_profile_id=self.profile_id,
                attempt_id=attempt_id or f"att-{task_id[:8]}",
                dataset_version=dataset_version,
                status=SpecialistStatus.FAILED,
                error_category=res.get("error_category", "fatigue_analysis_failed"),
                findings=[res.get("error", "Fatigue analysis failed")],
            )

        if status == "insufficient_evidence":
            err_msg = res.get("error", "Insufficient creative trajectory data")
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
        findings: list[str] = []

        for c_eval in res.get("creative_evaluations", []):
            cid = c_eval["creative_id"]
            estimates.append(
                LearningEstimate(
                    estimate_id=f"est-fatigue-{cid}",
                    metric="decay_multiplier",
                    estimand="creative_retention",
                    evidence_category=EvidenceCategory.OBSERVATIONAL,
                    tenant_id=grant_tenant,
                    method_name="exponential_decay_trajectory",
                    point_estimate=float(c_eval["decay_multiplier"]),
                    units="ratio",
                    uncertainty=LearningUncertainty(
                        kind=UncertaintyKind.NOT_APPLICABLE,
                        method="exponential_decay_formula",
                    ),
                    causal_claim_permitted=False,
                    diagnostics={
                        "creative_id": cid,
                        "days_active": c_eval["days_active"],
                        "fatigue_detected": c_eval["fatigue_detected"],
                        "audience_saturation_detected": c_eval["audience_saturation_detected"],
                        "recommended_action": c_eval["recommended_action"],
                        "projected_roas": c_eval["projected_roas"],
                        "diagnostics": c_eval.get("diagnostics", {}),
                    },
                    assumptions=[
                        "Observational trajectory evaluated against CPM inflation and delivery shift alternatives.",
                    ],
                )
            )
            findings.append(
                f"Creative '{cid}' (active {c_eval['days_active']}d): decay multiplier {c_eval['decay_multiplier']}, "
                f"wearout={c_eval['fatigue_detected']}, saturation={c_eval['audience_saturation_detected']}, action='{c_eval['recommended_action']}'."
            )

        return LearningSpecialistResult(
            role=self.specialist_id,
            specialist_profile_id=self.profile_id,
            attempt_id=attempt_id or f"att-{task_id[:8]}",
            dataset_version=dataset_version,
            status=SpecialistStatus.COMPLETE,
            estimates=estimates,
            findings=findings,
            diagnostic_refs=[f"creatives_evaluated:{len(estimates)}"],
        )
