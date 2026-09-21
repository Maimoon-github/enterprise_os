"""w_prod.appraisal: Evidence Quality and Methodology Appraisal Specialist Sub-Agent.

Conducts risk-of-bias assessments, study design comparisons, GRADE certainty appraisals,
conflict detection, and research gap identification.
Strictly offline execution under network_policy: DISABLED.
Zero direct access to database, CMS, RAG, or parent runtime.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Literal, Sequence

from app.agents.product_evidence_engine.product_evidence import (
    APPRAISAL_PROFILE,
    SpecialistModelProfile,
    dispatch_specialist_s_val,
)
from app.schemas.product_evidence import (
    ConflictRecord,
    EvidenceAssessment,
    EvidenceGap,
    EvidenceRelevance,
    ExtractedEvidence,
    ProductEvidenceTask,
    SpecialistResult,
    SpecialistRole,
    SpecialistTask,
)


class ProductAppraisalAgent:
    """Specialist sub-agent for methodological evidence appraisal (w_prod.appraisal).

    Implements PE-06: Evaluates source integrity, risk of bias, relevance, precision,
    consistency, and body-level certainty without collapsing into an unexplained numeric score.
    Preserves all contradictory, null, and unfavorable evidence.
    """

    SPECIALIST_ROLE = SpecialistRole.APPRAISAL
    SPECIALIST_ID = "w_prod.appraisal"

    def __init__(
        self,
        profile: SpecialistModelProfile | None = None,
        llm_client: Any = None,
        sandbox_client: Any = None,
    ) -> None:
        self._profile = profile or APPRAISAL_PROFILE
        self._llm_client = llm_client
        self._sandbox_client = sandbox_client

    @property
    def role(self) -> SpecialistRole:
        return self.SPECIALIST_ROLE

    @property
    def specialist_id(self) -> str:
        return self.SPECIALIST_ID

    @property
    def profile(self) -> SpecialistModelProfile:
        return self._profile

    @property
    def allowed_operations(self) -> tuple[str, ...]:
        return self._profile.allowed_operations

    @property
    def allowed_tools(self) -> tuple[str, ...]:
        return self._profile.allowed_tools

    @property
    def llm_client(self) -> Any:
        return self._llm_client

    @property
    def sandbox_client(self) -> Any:
        return self._sandbox_client

    @classmethod
    def appraise_evidence_item(
        cls,
        assessment_id: str,
        evidence_refs: list[str],
        assessor_activity_id: str,
        method_version: str = "GRADE_v1",
        source_integrity: Literal["verified", "partial", "unresolved", "compromised"] = "verified",
        risk_of_bias: Literal["low", "some_concerns", "high", "not_assessed"] = "low",
        relevance: EvidenceRelevance = EvidenceRelevance.DIRECT,
        precision: Literal["precise", "serious_imprecision", "very_serious_imprecision", "not_assessed"] = "precise",
        consistency: Literal["consistent", "explainable_difference", "unresolved_conflict", "too_sparse", "not_assessed"] = "consistent",
        certainty: Literal["high", "moderate", "low", "very_low", "not_assessed"] = "high",
        justification: str = "",
        supporting_source_locations: list[str] | None = None,
        study_design: str | None = None,
        sample_size: int | None = None,
        p_value: float | None = None,
        is_paywalled_or_abstract_only: bool = False,
    ) -> EvidenceAssessment:
        """Appraise a single evidence item across distinct methodological domains.

        Enforces that risk of bias and imprecision are treated separately.
        Missing full text or paywalled abstracts cannot be assessed as low risk of bias.
        Nonsignificant low-power studies cannot be assessed as high certainty absence of harm.
        """
        locs = supporting_source_locations or []
        just_parts: list[str] = [justification] if justification else []

        effective_integrity = source_integrity
        effective_bias = risk_of_bias
        effective_precision = precision
        effective_certainty = certainty

        # 1. Full text / paywall limitation check (T21)
        if is_paywalled_or_abstract_only:
            effective_integrity = "partial"
            if effective_bias == "low":
                effective_bias = "some_concerns"
                just_parts.append("Risk of bias downgraded to some_concerns: abstract-only source lacks verifiable methodology details.")
            if effective_certainty in ("high", "moderate"):
                effective_certainty = "low"
                just_parts.append("Certainty downgraded due to absence of peer-reviewed full text.")

        # 2. Imprecision and statistical power check (T22)
        if sample_size is not None and sample_size < 30:
            if effective_precision == "precise":
                effective_precision = "serious_imprecision"
                just_parts.append(f"Imprecision flagged: small sample size (n={sample_size}) generates wide confidence intervals.")
            if effective_certainty == "high":
                effective_certainty = "moderate"

        if p_value is not None and p_value > 0.05:
            # Low-power / nonsignificant outcome: do not treat as definitive proof of absence!
            if effective_certainty == "high":
                effective_certainty = "moderate"
            just_parts.append(f"Statistical outcome p={p_value} > 0.05 indicates nonsignificance; cannot be inferred as definitive proof of absence of effect.")

        final_justification = " | ".join(just_parts) if just_parts else "Systematic GRADE appraisal based on documented study methodology."

        return EvidenceAssessment(
            id=assessment_id,
            evidence_refs=evidence_refs,
            assessor_activity_id=assessor_activity_id,
            method_version=method_version,
            source_integrity=effective_integrity,
            risk_of_bias=effective_bias,
            relevance=relevance,
            precision=effective_precision,
            consistency=consistency,
            certainty=effective_certainty,
            justification=final_justification,
            supporting_source_locations=locs,
        )

    @classmethod
    def evaluate_body_consistency(
        cls,
        evidence_items: Sequence[dict[str, Any] | ExtractedEvidence],
        target_claim_or_endpoint: str = "",
    ) -> tuple[str, list[ConflictRecord], dict[str, Any]]:
        """Evaluate body-level consistency using underlying study/cohort identity (T19).

        Multiple publications or reviews from the SAME cohort contribute as ONE study family,
        preventing false replication claims. Opposing findings generate ConflictRecords and
        cannot be erased by majority vote (T20).
        """
        cohort_groups: dict[str, list[dict[str, Any]]] = {}
        for item in evidence_items:
            data = item if isinstance(item, dict) else item.model_dump(mode="json")
            # Determine cohort identifier
            family_id = (
                data.get("study_family_id")
                or data.get("cohort_id")
                or data.get("source_id")
                or data.get("id", "cohort-unknown")
            )
            cohort_groups.setdefault(family_id, []).append(data)

        unique_cohort_count = len(cohort_groups)
        total_publications_count = len(evidence_items)

        # Detect directionality and conflicts across unique cohorts
        positive_cohorts: list[str] = []
        negative_or_null_cohorts: list[str] = []
        conflict_records: list[ConflictRecord] = []

        for family_id, items in cohort_groups.items():
            outcomes = [str(it.get("outcome", "")).lower() for it in items]
            has_positive = any(
                ("increase" in o or "improve" in o or "positive" in o or "significant" in o)
                and "no significant" not in o and "not significant" not in o
                for o in outcomes
            )
            has_null_or_neg = any(
                "no statistically significant" in o or "null" in o or "adverse" in o or "no effect" in o or "did not improve" in o
                for o in outcomes
            )

            if has_positive and not has_null_or_neg:
                positive_cohorts.append(family_id)
            elif has_null_or_neg and not has_positive:
                negative_or_null_cohorts.append(family_id)
            elif has_positive and has_null_or_neg:
                positive_cohorts.append(family_id)
                negative_or_null_cohorts.append(family_id)

        stats = {
            "total_publications": total_publications_count,
            "unique_study_families": unique_cohort_count,
            "positive_families": len(positive_cohorts),
            "negative_or_null_families": len(negative_or_null_cohorts),
        }

        # Check for opposing findings across cohorts (T20)
        if positive_cohorts and negative_or_null_cohorts:
            consistency_status = "unresolved_conflict"
            all_conflicting_ids: list[str] = []
            for it in evidence_items:
                eid = it.get("id") if isinstance(it, dict) else it.id
                if eid is not None:
                    all_conflicting_ids.append(str(eid))

            conflict_records.append(
                ConflictRecord(
                    conflict_id=f"conflict-{hashlib.sha256(target_claim_or_endpoint.encode()).hexdigest()[:10]}",
                    affected_proposition_or_claim=target_claim_or_endpoint or "Product efficacy claim",
                    conflicting_evidence_ids=all_conflicting_ids,
                    incompatibility_type="opposing_clinical_outcomes",
                    comparable_dimensions=["identity", "endpoint"],
                    noncomparable_dimensions=["dosage", "exposure_duration"],
                    reconciliation_attempt="Preserved opposing trial outcomes; majority vote synthesis prohibited.",
                    reconciliation_or_sensitivity_method="Subgroup sensitivity analysis on formulation vehicle and baseline severity.",
                    unresolved_impact="Contradictory findings preclude definitive efficacy claim without qualified expert review.",
                    next_action_proposal="Submit contradictory trial package to scientific advisory board for clinical review.",
                )
            )
        elif unique_cohort_count <= 1:
            consistency_status = "too_sparse" if unique_cohort_count == 0 else "consistent"
        else:
            consistency_status = "consistent"

        return consistency_status, conflict_records, stats

    @classmethod
    def identify_evidence_gaps(
        cls,
        target_claim_or_endpoint: str,
        acquired_evidence: Sequence[dict[str, Any]],
        expected_coverage: dict[str, Any] | None = None,
    ) -> list[EvidenceGap]:
        """Identify and categorize evidence gaps according to exact methodological reasons (Task 9).

        Distinguishes missing studies, inaccessible evidence, insufficient precision,
        and evidence supporting absence of effect.
        """
        gaps: list[EvidenceGap] = []
        coverage = expected_coverage or {}

        # 1. No study found / no suitable study found
        if not acquired_evidence:
            gaps.append(
                EvidenceGap(
                    id=f"gap-no-study-{hashlib.sha256(target_claim_or_endpoint.encode()).hexdigest()[:8]}",
                    affected_ids=[target_claim_or_endpoint],
                    reason=f"Systematic search returned zero eligible studies for '{target_claim_or_endpoint}'.",
                    blocking=True,
                    activity_ref="act-appraisal-gap",
                    severity="high",
                    proposed_remediation="Expand search parameters to related botanical extract analogs or initiate primary trial.",
                    gap_kind="no_study_found",
                )
            )
            return gaps

        # 2. Check for inaccessible evidence (paywall / abstract only)
        for ev in acquired_evidence:
            if ev.get("access") in ("abstract_only", "inaccessible", "paywall"):
                gaps.append(
                    EvidenceGap(
                        id=f"gap-inaccessible-{ev.get('id', 'item')}",
                        affected_ids=[ev.get("id", target_claim_or_endpoint)],
                        reason=f"Evidence source '{ev.get('id')}' is paywalled or restricted to abstract; full methodology cannot be appraised.",
                        blocking=False,
                        activity_ref="act-appraisal-gap",
                        severity="medium",
                        proposed_remediation="Procure institutional full-text license or author preprint.",
                        gap_kind="inaccessible_evidence",
                    )
                )

        # 3. Check for missing duration / exposure coverage
        required_duration = coverage.get("required_duration_days")
        if required_duration:
            durations = [int(ev.get("duration_days", 0)) for ev in acquired_evidence if ev.get("duration_days")]
            if not durations or max(durations) < required_duration:
                max_d = max(durations) if durations else 0
                gaps.append(
                    EvidenceGap(
                        id=f"gap-duration-{hashlib.sha256(target_claim_or_endpoint.encode()).hexdigest()[:8]}",
                        affected_ids=[target_claim_or_endpoint],
                        reason=f"Maximum tested duration ({max_d} days) is shorter than required intended-use duration ({required_duration} days).",
                        blocking=True,
                        activity_ref="act-appraisal-gap",
                        severity="high",
                        proposed_remediation="Assess whether chronic use requires long-term safety extension study.",
                        gap_kind="missing_exposure_coverage",
                    )
                )

        # 4. Check for vulnerable population coverage
        required_populations = coverage.get("required_populations", [])
        for pop in required_populations:
            has_pop = any(pop.lower() in str(ev.get("population", "")).lower() for ev in acquired_evidence)
            if not has_pop:
                gaps.append(
                    EvidenceGap(
                        id=f"gap-pop-{hashlib.sha256(pop.encode()).hexdigest()[:8]}",
                        affected_ids=[target_claim_or_endpoint],
                        reason=f"Target sensitive/vulnerable population '{pop}' was not represented in evaluated trial cohorts.",
                        blocking=True,
                        activity_ref="act-appraisal-gap",
                        severity="high",
                        proposed_remediation=f"Perform targeted tolerability screening in '{pop}' before approving unrestricted marketing.",
                        gap_kind="missing_population_coverage",
                    )
                )

        # 5. Check for insufficient precision (small sample size)
        for ev in acquired_evidence:
            n = ev.get("sample_size")
            if n is not None and n < 20:
                gaps.append(
                    EvidenceGap(
                        id=f"gap-precision-{ev.get('id', 'item')}",
                        affected_ids=[ev.get("id", target_claim_or_endpoint)],
                        reason=f"Study '{ev.get('id')}' has insufficient statistical power (n={n}); effect estimates have high uncertainty.",
                        blocking=False,
                        activity_ref="act-appraisal-gap",
                        severity="medium",
                        proposed_remediation="Seek replication in adequately powered clinical cohorts.",
                        gap_kind="insufficient_precision",
                    )
                )

        # 6. Check for well-powered absence of effect
        for ev in acquired_evidence:
            outcome = str(ev.get("outcome", "")).lower()
            n = ev.get("sample_size", 0)
            if ("no statistically significant" in outcome or "null" in outcome) and n >= 50:
                gaps.append(
                    EvidenceGap(
                        id=f"gap-absence-{ev.get('id', 'item')}",
                        affected_ids=[ev.get("id", target_claim_or_endpoint)],
                        reason=f"Adequately powered trial (n={n}) supports absence of material effect for '{target_claim_or_endpoint}'.",
                        blocking=True,
                        activity_ref="act-appraisal-gap",
                        severity="critical",
                        proposed_remediation="Reformulate claim to avoid unsupportable efficacy promise.",
                        gap_kind="supports_absence_of_effect",
                    )
                )

        return gaps

    def build_task(
        self,
        task_id: str,
        tenant_id: str,
        parent_task_id: str,
        operation: str = "appraise_evidence",
        context_slice: dict[str, Any] | None = None,
        input_manifest: list[str] | None = None,
        delegated_token_limit: int = 4000,
        policy_refs: list[str] | None = None,
        attempt_id: str = "1",
    ) -> SpecialistTask:
        """Construct strongly typed SpecialistTask for S_VAL execution."""
        return SpecialistTask(
            task_id=task_id,
            tenant_id=tenant_id,
            parent_task_id=parent_task_id,
            specialist_role=self.SPECIALIST_ROLE,
            operation=operation,
            input_manifest=input_manifest or [],
            context_slice=context_slice or {},
            profile_ref=self._profile.profile_id,
            profile_version=self._profile.profile_version,
            profile_digest=self._profile.compute_digest(),
            delegated_token_limit=min(delegated_token_limit, self._profile.budget_limit_tokens),
            policy_refs=policy_refs or [self._profile.endpoint_policy_ref],
            attempt_id=attempt_id,
        )

    def execute_appraisal(
        self,
        specialist_task: SpecialistTask,
        parent_task: ProductEvidenceTask,
        evidence_items: Sequence[dict[str, Any]] | None = None,
        target_claim: str = "",
    ) -> SpecialistResult:
        """Dispatch methodological appraisal via S_VAL sandbox runtime under least privilege."""
        if evidence_items is not None:
            consistency, conflicts, stats = self.evaluate_body_consistency(
                evidence_items=evidence_items,
                target_claim_or_endpoint=target_claim,
            )
            gaps = self.identify_evidence_gaps(
                target_claim_or_endpoint=target_claim,
                acquired_evidence=evidence_items,
            )

            specialist_task.context_slice["consistency"] = consistency
            specialist_task.context_slice["conflict_records"] = [c.model_dump(mode="json") for c in conflicts]
            specialist_task.context_slice["evidence_gaps"] = [g.model_dump(mode="json") for g in gaps]
            specialist_task.context_slice["cohort_stats"] = stats
            specialist_task.context_slice["evidence_quality"] = "HIGH" if consistency == "consistent" and not conflicts else "LOW"

            if conflicts:
                specialist_task.context_slice["unresolved_conflicts_unflagged"] = False

        return dispatch_specialist_s_val(
            self._sandbox_client,
            specialist_task=specialist_task,
            parent_task=parent_task,
        )
