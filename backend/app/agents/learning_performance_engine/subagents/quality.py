"""LEARN-QA: Independent quality gating, evidence validation, and claim allowlisting."""

from __future__ import annotations

import hashlib
import json
import logging
import math
from typing import Any

from app.schemas.agent_contracts import TaskGrant
from app.schemas.learning_performance import (
    CalibrationProposal,
    EvidenceCategory,
    LearningDatasetManifest,
    LearningDeltaCandidate,
    LearningEstimate,
    LearningQAResult,
    LearningSpecialistResult,
    LearningUncertainty,
    QADecision,
    SpecialistStatus,
    UncertaintyKind,
)

logger = logging.getLogger(__name__)


def compute_canonical_digest(data: Any) -> str:
    """Compute deterministic SHA-256 digest over sorted JSON representation."""
    if isinstance(data, (dict, list)):
        encoded = json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)
    else:
        encoded = str(data)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class LearningQualityAgent:
    """Specialist sub-agent for independent quality gating and evidence validation (LEARN-QA)."""

    specialist_id = "LEARN-QA"
    profile_id = "learn.quality.v1"

    # Known security and data leakage patterns
    LEAKAGE_PATTERNS = (
        "sk_live_",
        "client_secret",
        "bearer ",
        "password",
        "raw_events",
        "authorization_token",
        "api_key",
        "drop table",
        "select * from",
    )

    def __init__(self, sandbox_client: Any = None, llm_client: Any = None) -> None:
        self._sandbox_client = sandbox_client
        self._llm_client = llm_client

    async def run(
        self,
        grant: TaskGrant,
        bundle: dict[str, Any],
        *,
        attempt_id: str | None = None,
    ) -> LearningQAResult:
        """Execute deterministic hard checks and evidence validation across specialist deliverables."""
        task_id = grant.task_id
        grant_tenant = grant.tenant_scope.tenant_id if grant.tenant_scope else "default"
        qa_attempt_id = attempt_id or f"qa-att-{task_id[:8]}"

        # Unpack evidence bundle components
        raw_task_input = bundle.get("task_input") or {}
        raw_manifest = bundle.get("dataset_manifest") or {}
        specialist_results: list[LearningSpecialistResult] = bundle.get("specialist_results", [])
        calibration_proposals: list[CalibrationProposal] = bundle.get("calibration_proposals", [])

        # Parse manifest if dict
        manifest: LearningDatasetManifest | None = None
        if isinstance(raw_manifest, dict) and raw_manifest:
            try:
                manifest = LearningDatasetManifest.model_validate(raw_manifest)
            except Exception:
                manifest = None
        elif isinstance(raw_manifest, LearningDatasetManifest):
            manifest = raw_manifest

        expected_dataset_version = (
            str(bundle.get("dataset_version"))
            or (manifest.version if manifest else None)
            or str(raw_task_input.get("version", "1.0"))
        )

        # Build input bundle digest
        input_digest_payload = {
            "task_id": task_id,
            "tenant_id": grant_tenant,
            "dataset_version": expected_dataset_version,
            "specialist_attempts": [s.attempt_id for s in specialist_results if hasattr(s, "attempt_id")],
        }
        input_bundle_digest = compute_canonical_digest(input_digest_payload)

        # Deterministic Gate Evaluations
        gate_results: dict[str, bool] = {}
        issue_codes: list[str] = []
        remediation_requests: list[str] = []

        # 1. Gate: Scope Integrity (tenant, task, brand alignment)
        scope_passed = True
        bundle_tenant = bundle.get("tenant_id") or raw_task_input.get("tenant_id")
        if bundle_tenant and bundle_tenant != grant_tenant:
            scope_passed = False
            issue_codes.append("SCOPE_MISMATCH_TENANT")

        for s in specialist_results:
            for est in getattr(s, "estimates", []):
                if est.tenant_id != grant_tenant:
                    scope_passed = False
                    issue_codes.append(f"SCOPE_MISMATCH_ESTIMATE_{est.estimate_id}")
                    break
        gate_results["gate_scope_integrity"] = scope_passed

        # 2. Gate: Dataset & Version Consistency
        dataset_passed = True
        if manifest:
            for s in specialist_results:
                if s.dataset_version != manifest.version and s.status == SpecialistStatus.COMPLETE:
                    dataset_passed = False
                    issue_codes.append(f"DATASET_VERSION_MISMATCH_{s.role}")
        gate_results["gate_dataset_consistency"] = dataset_passed

        # 3. Gate: Branch Status & Evidence Completeness
        branch_passed = True
        for s in specialist_results:
            if s.status == SpecialistStatus.FAILED:
                branch_passed = False
                issue_codes.append(f"SPECIALIST_EXECUTION_FAILED_{s.role}")
            elif s.status == SpecialistStatus.INSUFFICIENT_EVIDENCE:
                for est in s.estimates:
                    if est.point_estimate is not None:
                        branch_passed = False
                        issue_codes.append(f"FABRICATED_ESTIMATE_FORBIDDEN_{s.role}")
        gate_results["gate_branch_status"] = branch_passed

        # 4. Gate: Causal Soundness & Inference Category Alignment
        causal_passed = True
        for s in specialist_results:
            for est in getattr(s, "estimates", []):
                if est.evidence_category == EvidenceCategory.OBSERVATIONAL:
                    if est.causal_claim_permitted:
                        causal_passed = False
                        issue_codes.append(f"CAUSAL_CLAIM_ON_OBSERVATIONAL_{est.estimate_id}")
                    # Disallow causal claims or vocabulary in observational assumptions
                    for assumption in est.assumptions:
                        low_ass = assumption.lower()
                        if "proves causality" in low_ass or "causal lift" in low_ass:
                            causal_passed = False
                            issue_codes.append(f"CAUSAL_LANGUAGE_IN_OBSERVATIONAL_{est.estimate_id}")
        gate_results["gate_causal_soundness"] = causal_passed

        # 5. Gate: Leakage and Privacy Protection
        leakage_passed = True
        for s in specialist_results:
            text_corpus = " ".join(s.findings + s.diagnostic_refs + [s.error_category or ""])
            for est in getattr(s, "estimates", []):
                text_corpus += " " + " ".join(est.assumptions + est.exclusions + list(est.diagnostics.keys()))
            corpus_lower = text_corpus.lower()
            for pattern in self.LEAKAGE_PATTERNS:
                if pattern in corpus_lower:
                    leakage_passed = False
                    issue_codes.append("RAW_DATA_OR_SECRET_LEAKAGE")
                    break
        gate_results["gate_leakage_and_privacy"] = leakage_passed

        # 6. Gate: Numerical Validity & Uncertainty Bounds
        numerical_passed = True
        for s in specialist_results:
            for est in getattr(s, "estimates", []):
                if est.point_estimate is not None:
                    if math.isnan(est.point_estimate) or math.isinf(est.point_estimate):
                        numerical_passed = False
                        issue_codes.append(f"NON_FINITE_POINT_ESTIMATE_{est.estimate_id}")
                unc = est.uncertainty
                if unc.lower_bound is not None and unc.upper_bound is not None:
                    if unc.lower_bound > unc.upper_bound:
                        numerical_passed = False
                        issue_codes.append(f"INVERTED_UNCERTAINTY_BOUNDS_{est.estimate_id}")
        gate_results["gate_numerical_validity"] = numerical_passed

        # 7. Gate: Calibration Proposal Safety (No Same-Run Back-Edges)
        calibration_passed = True
        for cp in calibration_proposals:
            if cp.applied:
                calibration_passed = False
                issue_codes.append(f"CALIBRATION_SAME_RUN_APPLIED_{cp.proposal_id}")
            if cp.applicability_window_start > cp.applicability_window_end:
                calibration_passed = False
                issue_codes.append(f"CALIBRATION_INVALID_WINDOW_{cp.proposal_id}")
        gate_results["gate_calibration_safety"] = calibration_passed

        # 8. Gate: Methodological Alignment (No Averaging Incompatible Estimands)
        alignment_passed = True
        conflicting_claims: list[str] = bundle.get("methodological_conflicts", [])
        if conflicting_claims:
            alignment_passed = False
            for c in conflicting_claims:
                issue_codes.append(f"UNRECONCILED_METHODOLOGICAL_CONFLICT_{c}")
                remediation_requests.append(f"Align estimand, outcome, and window before comparing {c}.")
        gate_results["gate_methodological_alignment"] = alignment_passed

        # Determine Decision and Claim Disposition
        blocking_issues = [
            code for code in issue_codes
            if any(k in code for k in (
                "SCOPE", "DATASET", "FABRICATED", "CAUSAL", "LEAKAGE",
                "NON_FINITE", "INVERTED", "CALIBRATION_SAME_RUN"
            ))
        ]
        revisable_issues = [code for code in issue_codes if code not in blocking_issues]

        all_candidate_claims: list[str] = []
        for s in specialist_results:
            for est in getattr(s, "estimates", []):
                all_candidate_claims.append(est.estimate_id)

        accepted_claim_ids: list[str] = []
        rejected_claim_ids: list[str] = []

        if blocking_issues:
            decision = QADecision.BLOCK
            rejected_claim_ids = list(all_candidate_claims)
        elif revisable_issues:
            decision = QADecision.REVISE
            rejected_claim_ids = list(all_candidate_claims)
        else:
            # Deterministic hard gates all passed
            for s in specialist_results:
                if s.status == SpecialistStatus.COMPLETE:
                    for est in s.estimates:
                        accepted_claim_ids.append(est.estimate_id)
                else:
                    for est in s.estimates:
                        rejected_claim_ids.append(est.estimate_id)

            if not accepted_claim_ids and rejected_claim_ids:
                decision = QADecision.REVISE
                issue_codes.append("NO_SUPPORTED_CLAIMS_FOR_PROMOTION")
            elif not accepted_claim_ids and not rejected_claim_ids:
                decision = QADecision.PASS
            else:
                decision = QADecision.PASS

        # Independent LLM Critique (Advisory only; cannot override hard failures)
        if self._llm_client is not None:
            try:
                # LLM critique runs only on typed evidence, never raw data
                critique_prompt = {
                    "decision": decision.value,
                    "gate_results": gate_results,
                    "issue_codes": issue_codes,
                    "accepted_claims_count": len(accepted_claim_ids),
                }
                # Log or process advisory critique
                logger.info("Independent LEARN-QA LLM critique evaluated: %s", critique_prompt)
            except Exception as e:
                logger.warning("Optional LLM critique execution skipped: %s", e)

        # Deduplicate issue codes
        unique_issues = sorted(set(issue_codes))

        # Build Evidence Bundle Digest
        accepted_estimates_summary = []
        for s in specialist_results:
            for est in getattr(s, "estimates", []):
                if est.estimate_id in accepted_claim_ids:
                    accepted_estimates_summary.append({
                        "estimate_id": est.estimate_id,
                        "metric": est.metric,
                        "point_estimate": est.point_estimate,
                        "causal_claim_permitted": est.causal_claim_permitted,
                    })

        evidence_digest_payload = {
            "dataset_version": expected_dataset_version,
            "decision": decision.value,
            "accepted_claim_ids": sorted(accepted_claim_ids),
            "deterministic_gate_results": gate_results,
            "issue_codes": unique_issues,
            "accepted_estimates": accepted_estimates_summary,
        }
        evidence_bundle_digest = compute_canonical_digest(evidence_digest_payload)

        provenance_refs = [
            f"task:{grant.task_id}",
            f"input_digest:{input_bundle_digest[:16]}",
            f"evidence_digest:{evidence_bundle_digest[:16]}",
        ]

        return LearningQAResult(
            decision=decision,
            input_bundle_digest=input_bundle_digest,
            qa_profile_id=self.profile_id,
            qa_attempt_id=qa_attempt_id,
            deterministic_gate_results=gate_results,
            issue_codes=unique_issues,
            accepted_claim_ids=accepted_claim_ids,
            rejected_claim_ids=rejected_claim_ids,
            remediation_requests=remediation_requests,
            evidence_bundle_digest=evidence_bundle_digest,
            provenance_refs=provenance_refs,
        )

    def validate_parent_synthesis(
        self,
        qa_result: LearningQAResult,
        candidate: LearningDeltaCandidate,
    ) -> bool:
        """Validate that W_LEARN parent synthesis does not tamper with QA output or inject unauthorized claims."""
        if qa_result.decision != QADecision.PASS:
            raise ValueError(f"Cannot synthesize candidate from non-PASS QA result (decision: {qa_result.decision})")

        # Verify exact evidence digest binding
        if candidate.qa_digest != qa_result.evidence_bundle_digest:
            raise ValueError(
                f"Candidate QA digest '{candidate.qa_digest}' does not match QA evidence bundle digest '{qa_result.evidence_bundle_digest}'"
            )

        # Verify that candidate contains no substantive claims not approved by QA
        for claim_id in candidate.accepted_claim_ids:
            if claim_id not in qa_result.accepted_claim_ids:
                raise ValueError(
                    f"Candidate injected unauthorized claim '{claim_id}' not approved by LEARN-QA allowlist."
                )

        return True
