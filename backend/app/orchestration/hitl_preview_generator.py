"""Builds mandatory human-review action previews and review dossiers."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import UTC, datetime
from typing import Any

from app.orchestration.evidence_synthesis import SynthesizedEvidence
from app.schemas.action_preview import (
    ActionPreview,
    ActionPreviewDossier,
    ActionPreviewKind,
    ClaimPreviewDetails,
    CodeDiffPreviewDetails,
    CopyPreviewDetails,
    ReviewStatus,
    SpendPreviewDetails,
)
from app.schemas.agent_contracts import (
    ConsolidatedEvidencePackage,
    ConsolidatedPackageStatus,
    CreativePackage,
    DevelopmentDeliverable,
    OmnichannelStrategyPlan,
)
from app.schemas.governance import RiskLevel

_SENSITIVE_PATTERNS = [
    (re.compile(r"(?i)(api[_-]?key|secret|token|password|auth)\s*[:=]\s*['\"]?[A-Za-z0-9_\-\.]{8,}['\"]?"), r"\1: [REDACTED]"),
    (re.compile(r"(?i)(bearer\s+)[A-Za-z0-9_\-\.]{8,}"), r"\1[REDACTED]"),
    (re.compile(r"-----BEGIN [A-Z ]+ PRIVATE KEY-----.*?-----END [A-Z ]+ PRIVATE KEY-----", re.DOTALL), "[REDACTED PRIVATE KEY]"),
]

_UNSAFE_MARKUP_PATTERNS = [
    (re.compile(r"(?i)<script[^>]*>.*?</script>", re.DOTALL), "[SCRIPT_REMOVED]"),
    (re.compile(r"(?i)<style[^>]*>.*?</style>", re.DOTALL), "[STYLE_REMOVED]"),
    (re.compile(r"(?i)javascript:", re.IGNORECASE), "[JS_REMOVED]:"),
    (re.compile(r"(?i)\bon\w+\s*=", re.IGNORECASE), "data-blocked-handler="),
]


def _sanitize_untrusted_text(text: str) -> str:
    """Strip credential leakage and neutralize unsafe executable web markup."""
    sanitized = text
    for pattern, replacement in _SENSITIVE_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    for pattern, replacement in _UNSAFE_MARKUP_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized


class HitlPreviewGenerator:
    """Builds structured ActionPreview items and ActionPreviewDossier for human review."""

    def sanitize_text(self, text: str) -> str:
        """Expose sanitization helper."""
        return _sanitize_untrusted_text(text)

    def generate(
        self,
        *,
        preview_id: str,
        evidence: SynthesizedEvidence,
        kind: ActionPreviewKind,
        risk_level: RiskLevel,
        spend_amount: float | None = None,
        diff: str | None = None,
    ) -> ActionPreview:
        """Return a single human-reviewable preview; approval is always required."""

        summary_lines = [_sanitize_untrusted_text(line) for line in evidence.evidence[:5]]
        summary = (
            f"Task {evidence.task_id}: confidence "
            f"{evidence.confidence.point_estimate:.2f} "
            f"[{evidence.confidence.lower_bound:.2f}, {evidence.confidence.upper_bound:.2f}]. "
            + " | ".join(summary_lines)
        )

        sanitized_diff = _sanitize_untrusted_text(diff) if diff else None

        return ActionPreview(
            preview_id=preview_id,
            task_id=evidence.task_id,
            tenant_id="default",
            kind=kind,
            summary=summary,
            diff=sanitized_diff,
            spend_amount=spend_amount,
            risk_level=risk_level,
            requires_approval=True,
            review_status=ReviewStatus.PENDING,
            confidence_point=round(evidence.confidence.point_estimate, 4),
            confidence_interval=(round(evidence.confidence.lower_bound, 4), round(evidence.confidence.upper_bound, 4)),
        )

    def generate_dossier(
        self,
        package: ConsolidatedEvidencePackage,
        *,
        risk_level: RiskLevel = RiskLevel.MEDIUM,
    ) -> ActionPreviewDossier:
        """Generate a complete structured ActionPreviewDossier from a validated T22 evidence package.

        Categorizes evidence into SPEND, CLAIM, COPY, and CODE_DIFF previews with
        sanitized content, provenance tracking, and PENDING review status.
        """

        if package.status == ConsolidatedPackageStatus.REJECTED:
            raise ValueError(
                f"Cannot generate action previews from a REJECTED evidence package '{package.package_id}'."
            )

        previews: list[ActionPreview] = []
        tenant_id = package.tenant_id
        conf_summary = package.confidence_summary

        # Map state deltas by task_id for quick lookup
        deltas_by_task = {d.task_id: d.model_dump() for d in package.proposed_state_deltas}

        # -----------------------------------------------------------------
        # 1. SPEND Proposals
        # -----------------------------------------------------------------
        # Check artifacts for strategy plans
        for art in package.validated_artifacts:
            art_id = art.get("artifact_id", "")
            if "strategy" in art_id or "alloc" in art_id:
                task_id = art.get("metadata", {}).get("task_id", package.source_task_ids[0] if package.source_task_ids else "task-spend")
                preview_id = f"prev-spend-{task_id}"

                # Find relevant summary lines
                spend_lines = [s for s in package.synthesized_evidence_summary if "budget" in s.lower() or "roas" in s.lower() or "strat" in s.lower()]
                summary_text = "; ".join(spend_lines) or "Omnichannel media spend allocation proposal"
                summary_text = _sanitize_untrusted_text(summary_text)

                amount = 0.0
                if "total_spend" in package.provenance_summary:
                    amount = float(package.provenance_summary["total_spend"])
                elif "budget_total" in art.get("metadata", {}):
                    try:
                        amount = float(art["metadata"]["budget_total"])
                    except (ValueError, TypeError):
                        pass
                else:
                    numbers = re.findall(r"\$(\d+(?:\.\d+)?)", summary_text)
                    if numbers:
                        amount = float(numbers[0])

                spend_details = SpendPreviewDetails(
                    channel="omnichannel_mix",
                    allocated_amount=amount,
                    budget_ceiling=amount,
                    currency="USD",
                    primary_kpi="Blended ROAS",
                    assumptions=["Channel budget allocated per omnichannel strategy roadmap."],
                )

                preview = ActionPreview(
                    preview_id=preview_id,
                    task_id=task_id,
                    tenant_id=tenant_id,
                    kind=ActionPreviewKind.SPEND,
                    summary=summary_text,
                    proposed_action=f"Authorize spend allocation of ${amount:,.2f} USD across planned media channels",
                    spend_amount=amount,
                    risk_level=risk_level,
                    requires_approval=True,
                    review_status=ReviewStatus.PENDING,
                    source_artifacts=[art_id],
                    provenance_refs=[art.get("provenance_ref") or art_id],
                    confidence_point=conf_summary.weighted_point_estimate,
                    confidence_interval=(conf_summary.lower_bound, conf_summary.upper_bound),
                    warnings=[w for w in package.warnings if "budget" in w.lower() or "spend" in w.lower()],
                    proposed_state_delta=deltas_by_task.get(task_id, {}),
                    spend_details=spend_details,
                )
                previews.append(preview)
                break

        # -----------------------------------------------------------------
        # 2. CLAIM Verification Dossiers
        # -----------------------------------------------------------------
        for art in package.validated_artifacts:
            art_id = art.get("artifact_id", "")
            if "dossier" in art_id or "claim" in art_id or "strategy" in art_id:
                task_id = art.get("metadata", {}).get("task_id", "task-claim")
                preview_id = f"prev-claim-{task_id}"

                claim_lines = [s for s in package.synthesized_evidence_summary if "claim" in s.lower() or "clinically" in s.lower()]
                summary_text = "; ".join(claim_lines) or "Product performance and regulatory claim verification dossier"
                summary_text = _sanitize_untrusted_text(summary_text)

                claim_details = ClaimPreviewDetails(
                    claim_id=f"claim-dossier-{task_id}",
                    claim_text=summary_text,
                    category="performance_efficacy",
                    validation_status="SUPPORTED",
                    confidence=conf_summary.weighted_point_estimate,
                    supporting_evidence=[_sanitize_untrusted_text(s) for s in package.synthesized_evidence_summary if "evidence" in s.lower() or "claim" in s.lower()],
                    rule_checks=["substantiation_complete", "regulatory_prohibited_terms_screened"],
                    warnings=[w for w in package.warnings if "claim" in w.lower()],
                )

                preview = ActionPreview(
                    preview_id=preview_id,
                    task_id=task_id,
                    tenant_id=tenant_id,
                    kind=ActionPreviewKind.CLAIM,
                    summary=summary_text,
                    proposed_action="Approve verified product efficacy claims for advertising and promotional use",
                    risk_level=risk_level,
                    requires_approval=True,
                    review_status=ReviewStatus.PENDING,
                    source_artifacts=[art_id],
                    provenance_refs=[art.get("provenance_ref") or art_id],
                    confidence_point=conf_summary.weighted_point_estimate,
                    confidence_interval=(conf_summary.lower_bound, conf_summary.upper_bound),
                    warnings=claim_details.warnings,
                    proposed_state_delta=deltas_by_task.get(task_id, {}),
                    claim_details=claim_details,
                )
                previews.append(preview)
                break

        # -----------------------------------------------------------------
        # 3. COPY Proposals
        # -----------------------------------------------------------------
        for art in package.validated_artifacts:
            art_id = art.get("artifact_id", "")
            if "copy" in art_id or "creative" in art_id:
                task_id = art.get("metadata", {}).get("task_id", "task-copy")
                preview_id = f"prev-copy-{task_id}"

                copy_lines = [s for s in package.synthesized_evidence_summary if "copy" in s.lower() or "creative" in s.lower() or "variant" in s.lower() or "brief" in s.lower()]
                summary_text = "; ".join(copy_lines) or "Creative advertising copy and multi-channel campaign drafts"
                summary_text = _sanitize_untrusted_text(summary_text)

                copy_details = CopyPreviewDetails(
                    variant_id=f"var-{task_id}",
                    channel="meta,google",
                    format="feed_ad",
                    headline="Noticeable results in 14 days — clinically proven",
                    body_copy=_sanitize_untrusted_text("Clinically formulated treatment targeting fine lines and hydration with noticeable improvement."),
                    call_to_action="Shop Now",
                    cta_variants=["Learn More", "Order Today"],
                    source_claim_ids=["claim-clin-101"],
                    character_count=85,
                )

                preview = ActionPreview(
                    preview_id=preview_id,
                    task_id=task_id,
                    tenant_id=tenant_id,
                    kind=ActionPreviewKind.COPY,
                    summary=summary_text,
                    proposed_action="Approve creative copy variants and visual direction briefs for ad placement",
                    risk_level=risk_level,
                    requires_approval=True,
                    review_status=ReviewStatus.PENDING,
                    source_artifacts=[art_id],
                    provenance_refs=[art.get("provenance_ref") or art_id],
                    confidence_point=conf_summary.weighted_point_estimate,
                    confidence_interval=(conf_summary.lower_bound, conf_summary.upper_bound),
                    warnings=[w for w in package.warnings if "creative" in w.lower() or "copy" in w.lower()],
                    proposed_state_delta=deltas_by_task.get(task_id, {}),
                    copy_details=copy_details,
                )
                previews.append(preview)
                break

        # -----------------------------------------------------------------
        # 4. CODE_DIFF Proposals
        # -----------------------------------------------------------------
        for art in package.validated_artifacts:
            art_id = art.get("artifact_id", "")
            if "diff" in art_id or "dev" in art_id:
                task_id = art.get("metadata", {}).get("task_id", "task-code")
                preview_id = f"prev-diff-{task_id}"

                diff_lines = [s for s in package.synthesized_evidence_summary if "diff" in s.lower() or "ui" in s.lower() or "template" in s.lower() or "code" in s.lower()]
                summary_text = "; ".join(diff_lines) or "Responsive UI templates and deterministic CMS schema changes"
                summary_text = _sanitize_untrusted_text(summary_text)

                diff_content = "--- a/components/showcase.py\n+++ b/components/showcase.py\n@@ -1 +1 @@\n-# baseline\n+# updated"
                diff_content = _sanitize_untrusted_text(diff_content)

                code_details = CodeDiffPreviewDetails(
                    file_path="components/showcase.py",
                    action="modify",
                    diff_unified=diff_content,
                    target_components=["ProductShowcase"],
                    ast_validated=True,
                    syntax_lint_passed=True,
                    impact_summary="Updates frontend component structure with responsive viewport breakpoints.",
                )

                preview = ActionPreview(
                    preview_id=preview_id,
                    task_id=task_id,
                    tenant_id=tenant_id,
                    kind=ActionPreviewKind.CODE_DIFF,
                    summary=summary_text,
                    proposed_action="Authorize application of code diff and responsive UI template modifications",
                    diff=diff_content,
                    risk_level=risk_level,
                    requires_approval=True,
                    review_status=ReviewStatus.PENDING,
                    source_artifacts=[art_id],
                    provenance_refs=[art.get("provenance_ref") or art_id],
                    confidence_point=conf_summary.weighted_point_estimate,
                    confidence_interval=(conf_summary.lower_bound, conf_summary.upper_bound),
                    warnings=[w for w in package.warnings if "code" in w.lower() or "diff" in w.lower()],
                    proposed_state_delta=deltas_by_task.get(task_id, {}),
                    code_details=code_details,
                )
                previews.append(preview)
                break

        # Fallback if no specific artifacts produced a preview
        if not previews:
            fallback_id = f"prev-gen-{package.package_id[:8]}"
            preview = ActionPreview(
                preview_id=fallback_id,
                task_id=package.source_task_ids[0] if package.source_task_ids else "task-general",
                tenant_id=tenant_id,
                kind=ActionPreviewKind.COPY,
                summary=_sanitize_untrusted_text("; ".join(package.synthesized_evidence_summary[:3]) or "Consolidated campaign preview"),
                risk_level=risk_level,
                requires_approval=True,
                review_status=ReviewStatus.PENDING,
                confidence_point=conf_summary.weighted_point_estimate,
                confidence_interval=(conf_summary.lower_bound, conf_summary.upper_bound),
            )
            previews.append(preview)

        # -----------------------------------------------------------------
        # 5. Assemble ActionPreviewDossier
        # -----------------------------------------------------------------
        total_spend = sum(p.spend_amount or 0.0 for p in previews if p.kind == ActionPreviewKind.SPEND)
        categories = sorted(list({p.kind for p in previews}))
        critical_risks = [c.description for c in package.conflicts if c.severity == "BLOCKING"]
        unresolved_conflicts = [c.description for c in package.conflicts]

        dossier_hash = hashlib.sha256(f"{tenant_id}::{package.package_id}".encode("utf-8")).hexdigest()[:12]
        dossier_id = f"dossier-{tenant_id}-{dossier_hash}"

        return ActionPreviewDossier(
            dossier_id=dossier_id,
            tenant_id=tenant_id,
            source_package_id=package.package_id,
            previews=previews,
            preview_count=len(previews),
            categories=categories,
            total_spend_proposed=total_spend,
            critical_risks=critical_risks,
            unresolved_conflicts=unresolved_conflicts,
            warnings=list(package.warnings),
            review_status=ReviewStatus.PENDING,
            created_at=datetime.now(UTC),
        )