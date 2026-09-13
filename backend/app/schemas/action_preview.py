"""Spend, claims, copy, and code-diff review dossiers for mandatory HITL review."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.governance import RiskLevel


class ActionPreviewKind(StrEnum):
    """The category of action a human reviewer is being asked to approve."""

    SPEND = "spend"
    CLAIM = "claim"
    COPY = "copy"
    CODE_DIFF = "code_diff"


class ReviewStatus(StrEnum):
    """The lifecycle review state of an action preview item or dossier."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REVISION_REQUESTED = "REVISION_REQUESTED"


class HumanDecisionType(StrEnum):
    """Explicit human reviewer decisions supported by the HITL Gate."""

    APPROVE = "APPROVE"
    REJECT = "REJECT"
    REQUEST_REVISION = "REQUEST_REVISION"


class ReviewerRole(StrEnum):
    """Authorized reviewer domains for role-based sign-off authorization."""

    LEGAL = "legal"
    FINANCE = "finance"
    BRAND_LEAD = "brand_lead"
    ENGINEERING = "engineering"
    ADMIN = "admin"


class SpendPreviewDetails(BaseModel):
    """Structured details for a spend or media budget allocation proposal."""

    channel: str
    allocated_amount: float
    percentage_of_total: float = 0.0
    currency: str = "USD"
    budget_ceiling: float | None = None
    primary_kpi: str = "Blended ROAS"
    target_roas_range: tuple[float, float] | None = None
    assumptions: list[str] = Field(default_factory=list)


class ClaimPreviewDetails(BaseModel):
    """Structured details for a product claim verification item."""

    claim_id: str
    claim_text: str
    category: str = "performance"
    validation_status: str = "SUPPORTED"
    confidence: float = 0.0
    supporting_evidence: list[str] = Field(default_factory=list)
    rule_checks: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class CopyPreviewDetails(BaseModel):
    """Structured details for a creative ad-copy or content variant."""

    variant_id: str
    channel: str
    format: str = "feed_ad"
    headline: str
    body_copy: str
    call_to_action: str = "Learn More"
    cta_variants: list[str] = Field(default_factory=list)
    source_claim_ids: list[str] = Field(default_factory=list)
    character_count: int = 0


class CodeDiffPreviewDetails(BaseModel):
    """Structured details for a code diff or CMS/UI schema modification."""

    file_path: str
    action: str = "modify"
    diff_unified: str
    target_components: list[str] = Field(default_factory=list)
    ast_validated: bool = True
    syntax_lint_passed: bool = True
    impact_summary: str = ""


class ActionPreview(BaseModel):
    """A human-reviewable dossier item describing a proposed action before execution."""

    preview_id: str
    task_id: str
    tenant_id: str = "default"
    kind: ActionPreviewKind
    summary: str
    proposed_action: str = ""
    diff: str | None = None
    spend_amount: float | None = Field(default=None, ge=0)
    risk_level: RiskLevel = RiskLevel.MEDIUM
    requires_approval: bool = True
    review_status: ReviewStatus = ReviewStatus.PENDING
    source_artifacts: list[str] = Field(default_factory=list)
    provenance_refs: list[str] = Field(default_factory=list)
    confidence_point: float = 1.0
    confidence_interval: tuple[float, float] = (0.0, 1.0)
    warnings: list[str] = Field(default_factory=list)
    proposed_state_delta: dict[str, Any] = Field(default_factory=dict)
    spend_details: SpendPreviewDetails | None = None
    claim_details: ClaimPreviewDetails | None = None
    copy_details: CopyPreviewDetails | None = None
    code_details: CodeDiffPreviewDetails | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ActionPreviewDossier(BaseModel):
    """Consolidated review dossier aggregating all categorized action previews for T24 HITL."""

    dossier_id: str
    tenant_id: str
    source_package_id: str
    previews: list[ActionPreview] = Field(default_factory=list)
    preview_count: int = 0
    categories: list[ActionPreviewKind] = Field(default_factory=list)
    total_spend_proposed: float = 0.0
    critical_risks: list[str] = Field(default_factory=list)
    unresolved_conflicts: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    review_status: ReviewStatus = ReviewStatus.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SignedApprovalClearance(BaseModel):
    """Cryptographically verifiable sign-off clearance issued by an authorized human reviewer."""

    clearance_id: str
    preview_id: str
    task_id: str
    tenant_id: str
    decision: HumanDecisionType
    approver: str
    approver_role: str
    preview_content_hash: str
    signature: str | None = None
    decided_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    approved_scope: dict[str, Any] = Field(default_factory=dict)
    revision_notes: str | None = None
    is_valid: bool = True


def compute_preview_hash(preview: ActionPreview) -> str:
    """Compute deterministic SHA-256 hash of reviewable preview content for tamper detection."""
    payload = {
        "preview_id": preview.preview_id,
        "task_id": preview.task_id,
        "tenant_id": preview.tenant_id,
        "kind": preview.kind.value if hasattr(preview.kind, "value") else str(preview.kind),
        "summary": preview.summary,
        "diff": preview.diff,
        "spend_amount": preview.spend_amount,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()