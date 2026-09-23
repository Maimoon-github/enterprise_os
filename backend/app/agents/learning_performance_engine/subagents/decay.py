"""LEARN-DECAY: Specialist sub-agent for lag/adstock kernels, carryover, and half-life estimation."""

from __future__ import annotations

import json
from typing import Any

from app.integrations.sandbox.s_attr_core import compute_lag_and_decay
from app.schemas.agent_contracts import TaskGrant
from app.schemas.learning_performance import (
    EvidenceCategory,
    LearningEstimate,
    LearningSpecialistResult,
    LearningUncertainty,
    SpecialistStatus,
    UncertaintyKind,
)


class LearningDecayAgent:
    """Specialist sub-agent for adstock decay modeling and half-life estimation."""

    specialist_id = "LEARN-DECAY"
    profile_id = "learn.decay.v1"

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
        """Execute lag kernel estimation, half-life calculation, and Hill transformation."""
        task_id = grant.task_id
        grant_tenant = grant.tenant_scope.tenant_id if grant.tenant_scope else "default"
        dataset_version = str(context.get("dataset_version", grant.cts_state.get("dataset_version", "1.0")))

        payload: dict[str, Any] = {
            "task_id": task_id,
            "tenant_id": grant_tenant,
            "operation": "estimate_adstock",
            "alpha": context.get("alpha", context.get("retention_rate", 0.5)),
            "series": context.get("series"),
            "hill_half_saturation": context.get("hill_half_saturation", 50.0),
            "hill_slope": context.get("hill_slope", 1.5),
            "max_lag": context.get("max_lag", 4),
        }

        res = compute_lag_and_decay(payload)
        status = res.get("status")

        if status == "failed":
            return LearningSpecialistResult(
                role=self.specialist_id,
                specialist_profile_id=self.profile_id,
                attempt_id=attempt_id or f"att-{task_id[:8]}",
                dataset_version=dataset_version,
                status=SpecialistStatus.FAILED,
                error_category=res.get("error_category", "decay_estimation_failed"),
                findings=[res.get("error", "Decay estimation failed")],
            )

        estimates: list[LearningEstimate] = []
        alpha = res["alpha"]
        hl_bins = res["half_life_bins"]
        hl_status = res["half_life_status"]

        # Half-life estimate
        if hl_bins is not None:
            unc_hl = LearningUncertainty(
                kind=UncertaintyKind.NOT_APPLICABLE,
                method="geometric_half_life_formula",
            )
        else:
            unc_hl = LearningUncertainty(
                kind=UncertaintyKind.UNAVAILABLE,
                reason_unavailable=f"Boundary condition: alpha={alpha} has no finite geometric half-life.",
            )

        estimates.append(
            LearningEstimate(
                estimate_id=f"est-halflife-{task_id[:8]}",
                metric="half_life",
                estimand="geometric_half_life_bins",
                evidence_category=EvidenceCategory.OBSERVATIONAL,
                tenant_id=grant_tenant,
                method_name="log_ratio_geometric_formula",
                point_estimate=float(hl_bins) if hl_bins is not None else None,
                units="bins",
                uncertainty=unc_hl,
                causal_claim_permitted=False,
                diagnostics={
                    "alpha": alpha,
                    "half_life_status": hl_status,
                    "diagnostics": res.get("diagnostics", {}),
                },
                assumptions=["Geometric decay rate alpha remains constant over horizon."],
            )
        )

        # Adstock retention rate alpha
        estimates.append(
            LearningEstimate(
                estimate_id=f"est-alpha-{task_id[:8]}",
                metric="retention_rate",
                estimand="adstock_alpha",
                evidence_category=EvidenceCategory.OBSERVATIONAL,
                tenant_id=grant_tenant,
                method_name="geometric_adstock_kernel",
                point_estimate=float(alpha),
                units="ratio",
                uncertainty=LearningUncertainty(
                    kind=UncertaintyKind.NOT_APPLICABLE,
                    method="geometric_adstock_formula",
                ),
                causal_claim_permitted=False,
                diagnostics=res.get("diagnostics", {}),
            )
        )

        findings = [
            f"Adstock kernel parameter alpha: {alpha}. Half-life: {hl_bins} bins ({hl_status}).",
            f"Adstocked series points: {len(res.get('adstock_series', []))}. Hill transformed series evaluated.",
        ]

        return LearningSpecialistResult(
            role=self.specialist_id,
            specialist_profile_id=self.profile_id,
            attempt_id=attempt_id or f"att-{task_id[:8]}",
            dataset_version=dataset_version,
            status=SpecialistStatus.COMPLETE,
            estimates=estimates,
            findings=findings,
            diagnostic_refs=[f"half_life_status:{hl_status}"],
        )
