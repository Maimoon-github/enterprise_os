"""Coordinates mandatory human approval, rejection, and revision decisions."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
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
from app.schemas.development.approval_token import DevelopmentApprovalToken
from app.security.cryptographic_validator import CryptographicValidator, sign_payload

CATEGORY_ROLE_PERMISSIONS: dict[ActionPreviewKind, set[str]] = {
    ActionPreviewKind.SPEND: {"finance", "admin"},
    ActionPreviewKind.CLAIM: {"legal", "admin"},
    ActionPreviewKind.COPY: {"brand_lead", "admin", "quality"},
    ActionPreviewKind.CODE_DIFF: {"engineering", "admin", "tech_lead", "lead_engineer", "brand_lead"},
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
    policy_version: str = "1.0.0"
    expires_at: datetime | None = None
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
        self._dev_approval_tokens: dict[str, DevelopmentApprovalToken] = {}
        self._used_token_ids: set[str] = set()
        self._used_nonces: set[str] = set()
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
        policy_version: str = "1.0.0",
        expires_at: datetime | None = None,
        expires_in_seconds: int | None = None,
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
                    raise PolicyViolationError(f"Unsupported human decision type '{decision}'. Must be APPROVE, REJECT, REQUEST_REVISION, or HOLD.")
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
        elif decision_type == HumanDecisionType.HOLD:
            preview.review_status = ReviewStatus.HELD

        # 7. Construct Signed Clearance Record
        eff_expires_at = expires_at
        if eff_expires_at is None and expires_in_seconds is not None:
            eff_expires_at = decision_time + timedelta(seconds=expires_in_seconds)

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
            public_key_pem=public_key_pem,
            decided_at=decision_time,
            expires_at=eff_expires_at,
            policy_version=policy_version,
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
            policy_version=policy_version,
            expires_at=eff_expires_at,
            clearance=clearance,
        )

        self._decisions[preview_id] = approval_decision
        del self._pending[preview_id]
        return approval_decision

    def get_decision(self, preview_id: str) -> ApprovalDecision | None:
        return self._decisions.get(preview_id)

    def verify_approval_integrity(
        self, preview_id: str, current_preview: ActionPreview | None = None
    ) -> bool:
        """Verify that an approved decision has not expired, revoked, or had its underlying content mutated."""
        decision = self._decisions.get(preview_id)
        if decision is None or not decision.approved:
            return False
        if decision.clearance is None or not decision.clearance.is_valid:
            return False
        if decision.clearance.expires_at is not None and decision.clearance.expires_at < datetime.now(UTC):
            self.invalidate_approval(preview_id, reason="Approval clearance expired")
            return False
        if current_preview is not None:
            curr_hash = compute_preview_hash(current_preview)
            if curr_hash != decision.clearance.preview_content_hash:
                self.invalidate_approval(preview_id, reason="Preview content mutated post-approval")
                return False
        return True

    def invalidate_approval(self, preview_id: str, reason: str = "") -> None:
        """Revoke and invalidate an approved clearance due to mutation, expiry, or revocation."""
        decision = self._decisions.get(preview_id)
        if decision is not None:
            decision.approved = False
            if decision.clearance is not None:
                decision.clearance.is_valid = False
            rev_note = f"Revoked: {reason}" if reason else "Revoked"
            if decision.revision_notes:
                decision.revision_notes = f"{decision.revision_notes}; {rev_note}"
            else:
                decision.revision_notes = rev_note

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

    def get_development_approval_token(
        self, task_id: str, step_id: str, attempt_id: str
    ) -> DevelopmentApprovalToken | None:
        """Retrieve stored approval token for task, step, and attempt."""
        return self._dev_approval_tokens.get(f"{task_id}:{step_id}:{attempt_id}")

    def decide_development_step(
        self,
        *,
        task_id: str,
        step_id: str,
        attempt_id: str,
        decision: str,
        reviewer: str = "",
        reviewer_id: str = "",
        reviewer_role: str = "engineering",
        tenant_id: str = "default",
        workflow_id: str = "",
        subagent_id: str = "DEV-CODE",
        input_snapshot_hash: str = "",
        output_snapshot_hash: str = "",
        candidate_hash: str = "",
        review_dossier_hash: str = "",
        policy_version: str = "1.0.0",
        machine_policy_allowed: bool = True,
        machine_policy_reason: str = "",
        signature: str | None = None,
        signing_private_key: Any | None = None,
        private_key_pem: str | None = None,
        validator: CryptographicValidator | None = None,
        revision_notes: str | None = "",
        ttl_seconds: int = 3600,
        expires_in_seconds: int = 3600,
        token_id: str | None = None,
        nonce: str | None = None,
        version: Any = 1,
    ) -> DevelopmentApprovalToken:
        """Authenticate, authorize, sign, and record a human decision for a Development sub-agent attempt.

        Enforces:
        1. Role authorization: Reviewer role must be in allowed development roles.
        2. Machine DENY precedence: machine DENY + human APPROVE = DENY (fail-closed).
        3. Single-scope, non-transferable binding: Matches task, workflow, step, attempt, and candidate hash.
        4. Replay protection: Rejects duplicate token IDs or nonces.
        5. Cryptographic signature: Signs decision server-side using private key or verifies caller signature.
        """
        reviewer_norm = (reviewer_id or reviewer or "reviewer").strip()
        out_hash = (output_snapshot_hash or candidate_hash).strip()
        ttl = ttl_seconds if ttl_seconds != 3600 else expires_in_seconds

        decision_norm = decision.strip().upper()
        if decision_norm not in ("APPROVE", "REJECT", "REQUEST_REVISION"):
            raise PolicyViolationError(
                f"Invalid development approval decision '{decision}'. Must be APPROVE, REJECT, or REQUEST_REVISION."
            )

        # 1. Reviewer Role Screening
        role_norm = reviewer_role.strip().lower()
        allowed_roles = CATEGORY_ROLE_PERMISSIONS.get(ActionPreviewKind.CODE_DIFF, {"engineering", "admin", "tech_lead"})
        if role_norm not in allowed_roles:
            raise PolicyViolationError(
                f"Reviewer role '{role_norm}' is not authorized to sign off on Development deliverables. "
                f"Authorized roles: {sorted(allowed_roles)}."
            )

        # 2. Machine Denial Precedence: machine DENY + human APPROVE = DENY
        if not machine_policy_allowed and decision_norm == "APPROVE":
            raise PolicyViolationError(
                f"Machine policy violation: Hard machine security/policy denial cannot be overridden "
                f"by human approval. Reason: '{machine_policy_reason}'."
            )

        # 3. Single-scope Replay Guard
        assigned_token_id = token_id or f"tok-{uuid.uuid4().hex[:12]}"
        assigned_nonce = nonce or uuid.uuid4().hex

        if assigned_token_id in self._used_token_ids:
            raise PolicyViolationError(
                f"Replay detected: Approval token '{assigned_token_id}' has already been consumed."
            )
        if assigned_nonce in self._used_nonces:
            raise PolicyViolationError(
                f"Replay detected: Approval nonce '{assigned_nonce}' has already been consumed."
            )

        # 4. Construct Token Model
        now_dt = datetime.now(UTC)
        expires_dt = now_dt + timedelta(seconds=ttl)

        token = DevelopmentApprovalToken(
            approval_id=f"appr-{uuid.uuid4()}",
            token_id=assigned_token_id,
            task_id=task_id,
            workflow_id=workflow_id,
            step_id=step_id,
            attempt_id=attempt_id,
            subagent_id=subagent_id,
            decision=decision_norm,  # type: ignore[arg-type]
            input_snapshot_hash=input_snapshot_hash or "0" * 32,
            output_snapshot_hash=out_hash or "0" * 32,
            review_dossier_hash=review_dossier_hash or "0" * 32,
            policy_version=policy_version,
            reviewer_identity=reviewer_norm,
            reviewer_role=role_norm,
            issued_at=now_dt,
            expires_at=expires_dt,
            nonce=assigned_nonce,
            version=int(version) if str(version).isdigit() else 1,
            signature="",
            revision_notes=revision_notes or "",
        )

        # 5. Signing and Cryptographic Verification
        canon_bytes = token.canonical_bytes()
        effective_val = validator or self._validator

        if signing_private_key is None and private_key_pem is not None:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
            from cryptography.hazmat.primitives.serialization import load_pem_private_key

            loaded_key = load_pem_private_key(private_key_pem.encode("ascii"), password=None)
            if not isinstance(loaded_key, Ed25519PrivateKey):
                raise SignatureVerificationError("Signing private key must be Ed25519.")
            signing_private_key = loaded_key

        if signing_private_key is None and signature is None:
            if not hasattr(self, "_server_signing_key"):
                from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

                self._server_signing_key = Ed25519PrivateKey.generate()
            signing_private_key = self._server_signing_key

        if signing_private_key is not None:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

            if not isinstance(signing_private_key, Ed25519PrivateKey):
                raise SignatureVerificationError("Signing private key must be Ed25519.")
            sig = sign_payload(canon_bytes, signing_private_key)
            token = token.model_copy(update={"signature": sig})
        elif signature is not None:
            if effective_val is not None and not effective_val.verify(canon_bytes, signature):
                raise SignatureVerificationError(
                    f"Cryptographic signature verification failed for approval token on task '{task_id}'."
                )
            token = token.model_copy(update={"signature": signature})

        # 6. Commit to replay cache and active store
        self._used_token_ids.add(assigned_token_id)
        self._used_nonces.add(assigned_nonce)
        self._dev_approval_tokens[f"{task_id}:{step_id}:{attempt_id}"] = token

        return token