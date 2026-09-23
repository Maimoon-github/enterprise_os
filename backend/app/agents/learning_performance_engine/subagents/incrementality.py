"""LEARN-INCREMENTALITY: Specialist sub-agent for randomized experiments, ITT lift, and calibration proposals."""

from __future__ import annotations

import json
from typing import Any

from app.integrations.sandbox.s_attr_core import compute_incrementality_lift
from app.schemas.agent_contracts import TaskGrant
from app.schemas.learning_performance import (
    CalibrationProposal,
    EvidenceCategory,
    LearningEstimate,
    LearningSpecialistResult,
    LearningUncertainty,
    SpecialistStatus,
    UncertaintyKind,
)


class LearningIncrementalityAgent:
    """Specialist sub-agent for randomized experiment analysis and calibration proposals."""

    specialist_id = "LEARN-INCREMENTALITY"
    profile_id = "learn.incrementality.v1"

    def __init__(self, sandbox_client: Any = None, llm_client: Any = None) -> None:
        self._sandbox_client = sandbox_client
        self._llm_client = llm_client

    async def run(
        self,
        grant: TaskGrant,
        context: dict[str, Any],
        *,
        attempt_id: str | None = None,
    ) -> tuple[CalibrationProposal | None, LearningSpecialistResult]:
        """Execute experiment validation, ITT lift estimation, and calibration proposal generation."""
        task_id = grant.task_id
        grant_tenant = grant.tenant_scope.tenant_id if grant.tenant_scope else "default"
        dataset_version = str(context.get("dataset_version", grant.cts_state.get("dataset_version", "1.0")))

        payload: dict[str, Any] = {
            "task_id": task_id,
            "tenant_id": grant_tenant,
            "operation": "estimate_lift",
            "channel": context.get("channel", "meta"),
            "source_experiment_id": context.get("source_experiment_id") or grant.cts_state.get("source_experiment_id"),
            "treatment_sample_size": context.get("treatment_sample_size") or grant.cts_state.get("treatment_sample_size"),
            "treatment_conversions": context.get("treatment_conversions") or grant.cts_state.get("treatment_conversions"),
            "control_sample_size": context.get("control_sample_size") or grant.cts_state.get("control_sample_size"),
            "control_conversions": context.get("control_conversions") or grant.cts_state.get("control_conversions"),
        }

        res = compute_incrementality_lift(payload)
        status = res.get("status")

        if status == "failed":
            res_obj = LearningSpecialistResult(
                role=self.specialist_id,
                specialist_profile_id=self.profile_id,
                attempt_id=attempt_id or f"att-{task_id[:8]}",
                dataset_version=dataset_version,
                status=SpecialistStatus.FAILED,
                error_category=res.get("error_category", "experiment_invalid"),
                findings=[res.get("error", "Incrementality calculation failed")],
            )
            return None, res_obj

        if status == "insufficient_evidence":
            err_msg = res.get("error", "Insufficient experimental evidence")
            res_obj = LearningSpecialistResult(
                role=self.specialist_id,
                specialist_profile_id=self.profile_id,
                attempt_id=attempt_id or f"att-{task_id[:8]}",
                dataset_version=dataset_version,
                status=SpecialistStatus.INSUFFICIENT_EVIDENCE,
                insufficient_evidence_reason=err_msg,
                findings=[err_msg],
            )
            return None, res_obj

        # Build experimental lift estimate
        ci = res["confidence_interval"]
        uncertainty = LearningUncertainty(
            kind=UncertaintyKind.CONFIDENCE_INTERVAL,
            method="two_proportion_wald_ci",
            lower_bound=ci["lower"],
            upper_bound=ci["upper"],
            level=ci.get("level", 0.95),
            limitations=["Normal approximation valid for large sample sizes."],
        )

        estimate = LearningEstimate(
            estimate_id=f"est-lift-{res.get('channel', 'meta')}",
            metric="absolute_lift",
            estimand="itt_lift",
            evidence_category=EvidenceCategory.EXPERIMENTAL,
            tenant_id=grant_tenant,
            channel=res.get("channel", "meta"),
            method_name="two_proportion_z_contrast",
            point_estimate=float(res["absolute_lift"]),
            units="ratio",
            uncertainty=uncertainty,
            causal_claim_permitted=True,
            diagnostics={
                "treatment_rate": res["treatment_rate"],
                "control_rate": res["control_rate"],
                "relative_lift": res["relative_lift"],
                "standard_error": res["standard_error"],
            },
            assumptions=[
                "Stable Unit Treatment Value Assumption (SUTVA) satisfied.",
                "Randomized assignment mechanism with balanced pre-treatment covariates.",
            ],
        )

        # Build CalibrationProposal
        cal_dict = res.get("calibration_proposal", {})
        cal_proposal = CalibrationProposal.model_validate(cal_dict)

        findings = [
            f"Estimated ITT absolute lift of {res['absolute_lift']:.4f} (95% CI: [{ci['lower']:.4f}, {ci['upper']:.4f}]).",
            f"Treatment conversion rate: {res['treatment_rate']:.4f}, Control: {res['control_rate']:.4f}.",
            f"Formulated calibration proposal {cal_proposal.proposal_id} for channel '{cal_proposal.channel}' (applied=False).",
        ]

        res_obj = LearningSpecialistResult(
            role=self.specialist_id,
            specialist_profile_id=self.profile_id,
            attempt_id=attempt_id or f"att-{task_id[:8]}",
            dataset_version=dataset_version,
            status=SpecialistStatus.COMPLETE,
            estimates=[estimate],
            findings=findings,
            diagnostic_refs=[f"proposal:{cal_proposal.proposal_id}"],
        )
        return cal_proposal, res_obj
