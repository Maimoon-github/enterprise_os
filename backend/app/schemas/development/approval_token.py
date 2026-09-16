"""Cryptographically bindable approval token schemas for development workflow steps (DE-04)."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

if TYPE_CHECKING:
    from app.security.cryptographic_validator import CryptographicValidator


class DevelopmentApprovalToken(BaseModel):
    """Cryptographic approval token binding a human decision to exact input/output artifacts."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    approval_id: str = Field(default_factory=lambda: f"appr-{uuid.uuid4()}")
    token_id: str = Field(default_factory=lambda: f"tok-{uuid.uuid4().hex[:12]}")
    task_id: str
    workflow_id: str = Field(default="")
    step_id: str
    attempt_id: str = Field(default="attempt-1")
    subagent_id: str
    decision: Literal["APPROVE", "REJECT", "REQUEST_REVISION"]
    input_snapshot_hash: str = Field(min_length=1)
    output_snapshot_hash: str = Field(min_length=1)
    review_dossier_hash: str = Field(min_length=1)
    policy_version: str = "1.0.0"
    reviewer_identity: str = ""
    reviewer_role: str = "engineering"
    issued_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime
    nonce: str = Field(default_factory=lambda: uuid.uuid4().hex)
    version: int = 1
    signature: str = Field(default="")
    revision_notes: str = ""

    @model_validator(mode="before")
    @classmethod
    def _normalize_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Normalize reviewer_id -> reviewer_identity
            if "reviewer_id" in data and not data.get("reviewer_identity"):
                data["reviewer_identity"] = data["reviewer_id"]
            elif "reviewer_identity" in data and not data.get("reviewer_id"):
                data["reviewer_id"] = data["reviewer_identity"]
            # Normalize created_at -> issued_at
            if "created_at" in data and not data.get("issued_at"):
                data["issued_at"] = data["created_at"]
            # Normalize candidate_hash -> output_snapshot_hash
            if "candidate_hash" in data and not data.get("output_snapshot_hash"):
                data["output_snapshot_hash"] = data["candidate_hash"]
            # Normalize revision_notes None -> ""
            if data.get("revision_notes") is None:
                data["revision_notes"] = ""
        return data

    @property
    def reviewer_id(self) -> str:
        return self.reviewer_identity

    @property
    def created_at(self) -> datetime:
        return self.issued_at

    @property
    def candidate_hash(self) -> str:
        return self.output_snapshot_hash

    def is_expired(self, at: datetime | None = None) -> bool:
        """Check if token has passed its expiration time."""
        current_time = at or datetime.now(UTC)
        exp = self.expires_at if self.expires_at.tzinfo is not None else self.expires_at.replace(tzinfo=UTC)
        return exp <= current_time

    def canonical_bytes(self) -> bytes:
        """Return canonical byte sequence covered by cryptographic signature."""
        return canonical_approval_token_bytes(self)

    def verify_signature(
        self,
        validator: CryptographicValidator | None = None,
        public_key_pem: str | None = None,
    ) -> bool:
        """Verify token signature using validator or public key PEM."""
        if not self.signature:
            return False
        if validator is not None:
            return validator.verify(self.canonical_bytes(), self.signature)
        if public_key_pem is not None:
            try:
                import base64
                from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
                from cryptography.hazmat.primitives.serialization import load_pem_public_key

                pub = load_pem_public_key(public_key_pem.encode("ascii"))
                if isinstance(pub, Ed25519PublicKey):
                    try:
                        sig_bytes = base64.b64decode(self.signature)
                    except Exception:
                        sig_bytes = bytes.fromhex(self.signature)
                    pub.verify(sig_bytes, self.canonical_bytes())
                    return True
            except Exception:
                return False
        return False


def compute_output_snapshot_hash(candidate_output: Any) -> str:
    """Compute deterministic SHA-256 hash of candidate output."""
    if hasattr(candidate_output, "model_dump_json"):
        raw = candidate_output.model_dump_json().encode("utf-8")
    elif isinstance(candidate_output, (dict, list)):
        raw = json.dumps(candidate_output, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    elif isinstance(candidate_output, bytes):
        raw = candidate_output
    else:
        raw = str(candidate_output).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


ApprovalToken = DevelopmentApprovalToken


def canonical_approval_token_bytes(token: DevelopmentApprovalToken) -> bytes:
    """Return canonical JSON-serialized bytes for signing or verifying an approval token.

    Deterministically binds:
    - approval_id and token_id
    - task_id, workflow_id, step_id, attempt_id, subagent_id
    - input_snapshot_hash, output_snapshot_hash, review_dossier_hash
    - policy_version
    - decision
    - reviewer_identity, reviewer_role
    - issued_at, expires_at
    - nonce, version
    - revision_notes
    """
    issued_iso = (
        token.issued_at.isoformat()
        if token.issued_at.tzinfo is not None
        else token.issued_at.replace(tzinfo=UTC).isoformat()
    )
    expires_iso = (
        token.expires_at.isoformat()
        if token.expires_at.tzinfo is not None
        else token.expires_at.replace(tzinfo=UTC).isoformat()
    )

    canonical_payload = {
        "approval_id": token.approval_id,
        "attempt_id": token.attempt_id,
        "decision": token.decision,
        "expires_at": expires_iso,
        "input_snapshot_hash": token.input_snapshot_hash,
        "issued_at": issued_iso,
        "nonce": token.nonce,
        "output_snapshot_hash": token.output_snapshot_hash,
        "policy_version": token.policy_version,
        "review_dossier_hash": token.review_dossier_hash,
        "reviewer_identity": token.reviewer_identity,
        "reviewer_role": token.reviewer_role,
        "revision_notes": token.revision_notes,
        "step_id": token.step_id,
        "subagent_id": token.subagent_id,
        "task_id": token.task_id,
        "token_id": token.token_id,
        "version": token.version,
        "workflow_id": token.workflow_id,
    }
    return json.dumps(canonical_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
