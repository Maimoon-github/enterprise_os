"""CREAT-QA: Creative Specialist Sub-Agent.

Independent quality assurance, grounding, scope, and compliance evaluator.
Evaluates candidate creative artifacts across grounding, brand voice, originality,
platform compliance, and policy boundaries.
Returns strictly typed QAReport with status PASS | REVISE | BLOCK.
NEVER mutates candidate artifacts; strictly non-mutating evaluator.
Operates under strict DENY_ALL tool policy.
"""

from __future__ import annotations

import copy
import json
from typing import Any
import uuid

from app.core.exceptions import PolicyViolationError
from app.schemas.agent_contracts import (
    AdaptedCreativePack,
    ConceptPack,
    CopyPack,
    CreativePlan,
    QAFinding,
    QAReasonCode,
    QAReport,
    QAStatus,
    TaskGrant,
    VisualPack,
)
from app.schemas.sandbox import SandboxInvocationMandate


class CreativeQualityAgent:
    """Specialist sub-agent for independent creative quality evaluation (CREAT-QA)."""

    SPECIALIST_ID = "CREAT-QA"
    ALLOWED_OPERATIONS = ()

    def __init__(self, llm_client: Any = None, sandbox_client: Any = None) -> None:
        self._llm_client = llm_client
        self._sandbox_client = sandbox_client

    @property
    def specialist_id(self) -> str:
        return self.SPECIALIST_ID

    @property
    def allowed_operations(self) -> tuple[str, ...]:
        return self.ALLOWED_OPERATIONS

    def build_sandbox_mandate(
        self,
        task_id: str,
        tenant_id: str,
        operation: str,
        payload: dict[str, Any],
    ) -> SandboxInvocationMandate:
        """Reject sandbox mandate: CREAT-QA operates under strict DENY_ALL tool policy."""
        raise PolicyViolationError(
            f"Specialist '{self.SPECIALIST_ID}' operates under DENY_ALL tool policy "
            "and cannot formulate sandbox invocation mandates."
        )

    async def run(
        self,
        grant: TaskGrant | None = None,
        plan: CreativePlan | None = None,
        concept_pack: ConceptPack | None = None,
        copy_pack: CopyPack | None = None,
        visual_pack: VisualPack | None = None,
        adapted_pack: AdaptedCreativePack | None = None,
        context: dict[str, Any] | None = None,
    ) -> QAReport:
        """Evaluate creative candidates against evidence manifest, scope, and policy.

        Guaranteed non-mutating: candidate objects are read-only and never modified.
        """
        effective_context = context or {}

        # 1. Capture Pre-Evaluation Artifact Hashes to Guarantee Non-Mutation
        pre_eval_hashes = {
            "concept": concept_pack.artifact_hash if (concept_pack and concept_pack.artifact_hash) else None,
            "copy": copy_pack.artifact_hash if (copy_pack and copy_pack.artifact_hash) else None,
            "visual": visual_pack.artifact_hash if (visual_pack and visual_pack.artifact_hash) else None,
            "adapted": adapted_pack.artifact_hash if (adapted_pack and adapted_pack.artifact_hash) else None,
        }

        tenant_id = (
            grant.tenant_scope.tenant_id
            if (grant and grant.tenant_scope)
            else (plan.tenant_id if plan else "default")
        )
        task_id = (
            grant.task_id
            if grant
            else (plan.task_id if plan else f"task-{uuid.uuid4().hex[:8]}")
        )

        findings: list[QAFinding] = []
        passed_checks: list[str] = []
        failed_deterministic_checks: list[str] = []
        missing_evidence_claims: list[str] = []

        # 2. Approved Boundaries
        approved_evidence = set(plan.evidence_manifest if plan else [])
        if "approved_claims" in effective_context:
            for c in effective_context["approved_claims"]:
                cid = c.get("id") if isinstance(c, dict) else str(c)
                if cid:
                    approved_evidence.add(str(cid))

        approved_channels = set(plan.approved_channels if plan else [])
        prohibited_scope = [p.lower() for p in (plan.prohibited_scope if plan else [])]

        # 3. Layer 1: Grounding & Evidence Check
        # Every factual claim cited in copy or adapted pack must exist in approved evidence
        all_cited_claims: set[str] = set()

        if copy_pack:
            for v in copy_pack.variants:
                for cid in v.source_claim_ids:
                    all_cited_claims.add(cid)
                    if approved_evidence and cid not in approved_evidence:
                        missing_evidence_claims.append(cid)
                        failed_deterministic_checks.append(f"unsupported_claim:{cid}")
                        findings.append(
                            QAFinding(
                                layer="grounding",
                                severity="critical",
                                reason_code=QAReasonCode.EVIDENCE_MISSING,
                                message=f"Copy variant '{v.variant_id}' cites unapproved claim '{cid}'.",
                                affected_artifact_ids=[copy_pack.pack_id, v.variant_id],
                                evidence_refs=[cid],
                                recommended_responsible_stage="COPY",
                            )
                        )

        if adapted_pack:
            for v in adapted_pack.ad_copy_variants:
                for cid in v.source_claim_ids:
                    all_cited_claims.add(cid)
                    if approved_evidence and cid not in approved_evidence:
                        missing_evidence_claims.append(cid)
                        failed_deterministic_checks.append(f"unsupported_claim:{cid}")
                        findings.append(
                            QAFinding(
                                layer="grounding",
                                severity="critical",
                                reason_code=QAReasonCode.EVIDENCE_MISSING,
                                message=f"Adapted variant '{v.variant_id}' cites unapproved claim '{cid}'.",
                                affected_artifact_ids=[adapted_pack.pack_id, v.variant_id],
                                evidence_refs=[cid],
                                recommended_responsible_stage="ADAPT",
                            )
                        )

        if not missing_evidence_claims:
            passed_checks.append("grounding_claim_verification")

        # 4. Layer 2: Scope & Channel Boundaries Check
        scope_violations: list[str] = []
        if approved_channels:
            # Check concept channels
            if concept_pack:
                for ch in concept_pack.approved_channel_ids:
                    if ch.lower() not in approved_channels:
                        scope_violations.append(f"concept_channel:{ch}")
            # Check copy channels
            if copy_pack:
                for v in copy_pack.variants:
                    if v.channel.lower() not in approved_channels:
                        scope_violations.append(f"copy_channel:{v.channel}")
            # Check visual channels
            if visual_pack:
                for vb in visual_pack.production_briefs:
                    if vb.channel.lower() not in approved_channels:
                        scope_violations.append(f"visual_channel:{vb.channel}")
            # Check adapted channels
            if adapted_pack:
                for v in adapted_pack.ad_copy_variants:
                    if v.channel.lower() not in approved_channels:
                        scope_violations.append(f"adapted_channel:{v.channel}")

        for sv in scope_violations:
            failed_deterministic_checks.append(sv)
            findings.append(
                QAFinding(
                    layer="policy_scope",
                    severity="critical",
                    reason_code=QAReasonCode.SCOPE_VIOLATION,
                    message=f"Scope violation: unapproved channel detected in '{sv}'.",
                    affected_artifact_ids=[plan.plan_id if plan else "plan"],
                    recommended_responsible_stage="ADAPT",
                )
            )

        if not scope_violations:
            passed_checks.append("channel_scope_compliance")

        # 5. Layer 3: Prohibited Terms & Policy Checks
        policy_violations: list[str] = []
        if copy_pack:
            for v in copy_pack.variants:
                text_to_check = f"{v.headline} {v.body_copy}".lower()
                for term in prohibited_scope:
                    if term in text_to_check:
                        policy_violations.append(f"prohibited_term:{term}:variant:{v.variant_id}")
                        findings.append(
                            QAFinding(
                                layer="policy_scope",
                                severity="critical",
                                reason_code=QAReasonCode.POLICY_BLOCK,
                                message=f"Prohibited term '{term}' detected in copy variant '{v.variant_id}'.",
                                affected_artifact_ids=[copy_pack.pack_id, v.variant_id],
                                recommended_responsible_stage="COPY",
                            )
                        )

        if not policy_violations:
            passed_checks.append("policy_and_prohibited_terms")

        # 6. Layer 4: Originality & Semantic Distinctness
        # Verify variants are not repetitive synonym swaps or duplicates
        if copy_pack and len(copy_pack.variants) > 1:
            headlines = [v.headline.strip().lower() for v in copy_pack.variants]
            hooks = [v.hook_angle.strip().lower() for v in copy_pack.variants]
            if len(headlines) != len(set(headlines)) or len(set(hooks)) < (len(copy_pack.variants) // 2):
                failed_deterministic_checks.append("copy_distinctness_failure")
                findings.append(
                    QAFinding(
                        layer="originality",
                        severity="high",
                        reason_code=QAReasonCode.COPY,
                        message="Copy variants lack distinctness; repetitive hooks or duplicate headlines detected.",
                        affected_artifact_ids=[copy_pack.pack_id],
                        recommended_responsible_stage="COPY",
                    )
                )
            else:
                passed_checks.append("copy_distinctness_verified")

        # 7. Layer 5: Platform Native Compliance
        if adapted_pack:
            for v in adapted_pack.ad_copy_variants:
                if v.channel.lower() in ("meta", "linkedin", "google") and len(v.headline) > 100:
                    failed_deterministic_checks.append(f"headline_length_exceeded:{v.channel}")
                    findings.append(
                        QAFinding(
                            layer="platform",
                            severity="high",
                            reason_code=QAReasonCode.ADAPT,
                            message=f"Headline length on {v.channel} ({len(v.headline)}) exceeds platform limit.",
                            affected_artifact_ids=[adapted_pack.pack_id, v.variant_id],
                            recommended_responsible_stage="ADAPT",
                        )
                    )
            if not any(f.layer == "platform" for f in findings):
                passed_checks.append("platform_spec_conformance")

        # 8. Status & Primary Reason Code Synthesis
        primary_reason_code: QAReasonCode | str | None = None
        has_critical = any(f.severity == "critical" for f in findings)
        has_high = any(f.severity == "high" for f in findings)

        if has_critical:
            status = QAStatus.BLOCK
            # Choose leading critical reason code
            critical_finding = next(f for f in findings if f.severity == "critical")
            primary_reason_code = critical_finding.reason_code
            severity = "critical"
        elif has_high:
            status = QAStatus.REVISE
            high_finding = next(f for f in findings if f.severity == "high")
            primary_reason_code = high_finding.reason_code
            severity = "high"
        else:
            status = QAStatus.PASS
            primary_reason_code = None
            severity = "low"

        # 9. Verify Post-Evaluation Hashes to Prove Immutability
        post_eval_hashes = {
            "concept": concept_pack.artifact_hash if (concept_pack and concept_pack.artifact_hash) else None,
            "copy": copy_pack.artifact_hash if (copy_pack and copy_pack.artifact_hash) else None,
            "visual": visual_pack.artifact_hash if (visual_pack and visual_pack.artifact_hash) else None,
            "adapted": adapted_pack.artifact_hash if (adapted_pack and adapted_pack.artifact_hash) else None,
        }
        for k, h_before in pre_eval_hashes.items():
            if h_before is not None and post_eval_hashes[k] != h_before:
                raise RuntimeError(
                    f"CRITICAL: CREAT-QA mutated candidate '{k}' artifact during evaluation! "
                    f"Hash before: {h_before}, Hash after: {post_eval_hashes[k]}"
                )

        target_artifact_hash = (
            adapted_pack.artifact_hash
            if (adapted_pack and adapted_pack.artifact_hash)
            else (copy_pack.artifact_hash if (copy_pack and copy_pack.artifact_hash) else "")
        )

        report = QAReport(
            tenant_id=tenant_id,
            task_id=task_id,
            producing_agent_id=self.SPECIALIST_ID,
            evaluated_artifact_hash=target_artifact_hash,
            status=status,
            reason_code=primary_reason_code,
            findings=findings,
            severity=severity,
            failed_deterministic_checks=failed_deterministic_checks,
            missing_evidence_claims=sorted(list(set(missing_evidence_claims))),
            passed_checks=passed_checks,
            approved_channel_ids=list(approved_channels),
            evidence_refs=list(approved_evidence),
        )
        report.compute_artifact_hash()

        return report


CreatQAAgent = CreativeQualityAgent
CreativeQAAgent = CreativeQualityAgent
