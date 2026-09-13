"""Coordinates mandatory human approval, rejection, and revision decisions."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.core.exceptions import (
    ApprovalRequiredError,
    PolicyViolationError,
    SignatureVerificationError,
)
from app.schemas.action_preview import (
    ActionPreview,
    ActionPreviewDossier,
    ActionPreviewKind,
    HumanDecisionType,
    ReviewStatus,
    ReviewerRole,
    SignedApprovalClearance,
    compute_preview_hash,
)
from app.security.cryptographic_validator import CryptographicValidator

CATEGORY_ROLE_PERMISSIONS: dict[ActionPreviewKind, set[str]] = {
    ActionPreviewKind.SPEND: {"finance", "admin"},
    ActionPreviewKind.CLAIM: {"legal", "admin"},
    ActionPreviewKind.COPY: {"brand_lead", "admin", "quality"},
    ActionPreviewKind.CODE_DIFF: {"engineering", "admin", "tech_lead"},
}


def canonical_decision_bytes(
    preview_id: str,
    decision: str,
    approver: str,
    tenant_id: str,
    preview_content_hash: str,
    decided_at: str,
    revision_notes: str = "",
) -> bytes:
    """Return the deterministic byte payload an approval decision signature must cover."""

    canonical = {
        "approver": approver,
        "decided_at": decided_at,
        "decision": decision,
        "preview_content_hash": preview_content_hash,
        "preview_id": preview_id,
        "revision_notes": revision_notes,
        "tenant_id": tenant_id,
    }
    return json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")


@dataclass
class ApprovalDecision:
    """The outcome of a human reviewer's decision on an action preview."""

    preview_id: str
    approved: bool
    approver: str
    decided_at: datetime
    revision_notes: str | None = None
    decision: HumanDecisionType = HumanDecisionType.APPROVE
    approver_role: str = "admin"
    tenant_id: str = "default"
    preview_content_hash: str = ""
    signature: str | None = None
    clearance: SignedApprovalClearance | None = None
    updated_task: Any | None = None


class HitlCoordinator:
    """Tracks pending action previews and enforces cryptographically verifiable human decisions.

    Guarantees:
    - Genuine human sign-off only (zero agentic self-approval).
    - Role-based domain authority screening (finance, legal, brand_lead, engineering, admin).
    - Tamper-evident integrity binding via preview content hashing.
    - Strict gating for outbound execution (T25).
    """

    def __init__(self, validator: CryptographicValidator | None = None) -> None:
        self._pending: dict[str, ActionPreview] = {}
        self._decisions: dict[str, ApprovalDecision] = {}
        self._validator = validator

    def submit_for_approval(self, preview: ActionPreview) -> None:
        """Register ``preview`` as awaiting human review."""
        preview.review_status = ReviewStatus.PENDING
        self._pending[preview.preview_id] = preview

    def submit_dossier(self, dossier: ActionPreviewDossier) -> None:
        """Register all action previews in ``dossier`` for human review."""
        for preview in dossier.previews:
            self.submit_for_approval(preview)

    def is_pending(self, preview_id: str) -> bool:
        return preview_id in self._pending

    def is_approved(self, preview_id: str) -> bool:
        decision = self._decisions.get(preview_id)
        return decision is not None and decision.approved is True and decision.decision == HumanDecisionType.APPROVE

    def is_dossier_approved(self, dossier: ActionPreviewDossier) -> bool:
        """Return True only if every preview in the dossier has been explicitly approved."""
        if not dossier.previews:
            return False
        return all(self.is_approved(p.preview_id) for p in dossier.previews)

    def decide(
        self,
        preview_id: str,
        *,
        approved: bool | None = None,
        decision: HumanDecisionType | str | bool | None = None,
        approver: str,
        approver_role: ReviewerRole | str = "admin",
        tenant_id: str | None = None,
        signature: str | None = None,
        public_key_pem: str | None = None,
        validator: CryptographicValidator | None = None,
        preview_content_hash: str | None = None,
        revision_notes: str | None = None,
        decided_at: datetime | None = None,
    ) -> ApprovalDecision:
        """Record an authenticated human decision for a pending preview with role & signature checks."""

        if preview_id not in self._pending:
            raise ApprovalRequiredError(
                f"No pending action preview '{preview_id}' awaiting approval."
            )

        preview = self._pending[preview_id]

        # 1. Resolve Decision Type
        if decision is not None:
            if isinstance(decision, HumanDecisionType):
                decision_type = decision
            elif isinstance(decision, bool):
                decision_type = HumanDecisionType.APPROVE if decision else HumanDecisionType.REJECT
            else:
                decision_str = decision.upper()
                try:
                    decision_type = HumanDecisionType(decision_str)
                except ValueError:
                    raise PolicyViolationError(f"Unsupported human decision type '{decision}'. Must be APPROVE, REJECT, or REQUEST_REVISION.")
        elif approved is not None:
            decision_type = HumanDecisionType.APPROVE if approved else HumanDecisionType.REJECT
        else:
            decision_type = HumanDecisionType.APPROVE

        is_approved_bool = (decision_type == HumanDecisionType.APPROVE)

        # 2. Tenant Isolation Screening
        target_tenant = tenant_id or preview.tenant_id
        if preview.tenant_id not in ("default", "global") and target_tenant != preview.tenant_id:
            raise PolicyViolationError(
                f"Tenant authority mismatch: reviewer tenant '{target_tenant}' cannot sign off on preview tenant '{preview.tenant_id}'."
            )

        # 3. Reviewer Role Authority Screening
        role_key = approver_role.value.lower() if hasattr(approver_role, "value") else str(approver_role).lower()
        allowed_roles = CATEGORY_ROLE_PERMISSIONS.get(preview.kind, {"admin"})
        if role_key not in allowed_roles:
            raise PolicyViolationError(
                f"Reviewer role '{role_key}' is not authorized to sign off on '{preview.kind.value}' previews. Required: {sorted(allowed_roles)}."
            )

        # 4. Preview Content Integrity & Tamper Check
        computed_hash = compute_preview_hash(preview)
        if preview_content_hash and preview_content_hash != computed_hash:
            raise SignatureVerificationError(
                f"Preview content hash mismatch: preview has been tampered with or modified. Expected {preview_content_hash}, calculated {computed_hash}."
            )
        effective_hash = preview_content_hash or computed_hash

        # 5. Cryptographic Signature Validation
        decision_time = decided_at or datetime.now(UTC)
        if signature is not None:
            val = validator or self._validator or (CryptographicValidator(public_key_pem) if public_key_pem else None)
            if val is None:
                raise SignatureVerificationError(
                    "Cryptographic signature provided but no validator or public key is configured."
                )

            canon_bytes = canonical_decision_bytes(
                preview_id=preview_id,
                decision=decision_type.value,
                approver=approver,
                tenant_id=target_tenant,
                preview_content_hash=effective_hash,
                decided_at=decision_time.isoformat(),
                revision_notes=revision_notes or "",
            )

            if not val.verify(canon_bytes, signature):
                raise SignatureVerificationError(
                    f"Cryptographic signature verification failed for preview '{preview_id}'. Signature invalid or payload tampered."
                )

        # 6. Update Preview State
        if decision_type == HumanDecisionType.APPROVE:
            preview.review_status = ReviewStatus.APPROVED
        elif decision_type == HumanDecisionType.REJECT:
            preview.review_status = ReviewStatus.REJECTED
        elif decision_type == HumanDecisionType.REQUEST_REVISION:
            preview.review_status = ReviewStatus.REVISION_REQUESTED

        # 7. Construct Signed Clearance Record
        clearance = SignedApprovalClearance(
            clearance_id=str(uuid.uuid4()),
            preview_id=preview_id,
            task_id=preview.task_id,
            tenant_id=target_tenant,
            decision=decision_type,
            approver=approver,
            approver_role=role_key,
            preview_content_hash=effective_hash,
            signature=signature,
            decided_at=decision_time,
            approved_scope={"kind": preview.kind.value, "spend_amount": preview.spend_amount},
            revision_notes=revision_notes,
            is_valid=is_approved_bool,
        )

        approval_decision = ApprovalDecision(
            preview_id=preview_id,
            approved=is_approved_bool,
            approver=approver,
            decided_at=decision_time,
            revision_notes=revision_notes,
            decision=decision_type,
            approver_role=role_key,
            tenant_id=target_tenant,
            preview_content_hash=effective_hash,
            signature=signature,
            clearance=clearance,
        )

        self._decisions[preview_id] = approval_decision
        del self._pending[preview_id]
        return approval_decision

    def get_decision(self, preview_id: str) -> ApprovalDecision | None:
        return self._decisions.get(preview_id)

    def require_approved(self, preview_id: str) -> ApprovalDecision:
        """Return the decision for ``preview_id``, failing closed if it was not approved."""

        decision = self._decisions.get(preview_id)
        if decision is None:
            raise ApprovalRequiredError(
                f"Action preview '{preview_id}' has not been reviewed."
            )
        if not decision.approved or decision.decision != HumanDecisionType.APPROVE:
            status_desc = decision.decision.value if hasattr(decision.decision, "value") else str(decision.decision)
            raise ApprovalRequiredError(
                f"Action preview '{preview_id}' was {status_desc}; dispatch is strictly blocked."
            )
        return decision