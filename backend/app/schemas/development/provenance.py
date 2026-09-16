"""Provenance tracking models for development artifacts, sub-agent transitions, and W3C PROV lineage (DE-05)."""

from __future__ import annotations

import base64
import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DevelopmentProvEvent(BaseModel):
    """Immutable, normalized audit event capturing Development Engine lineage and integrity.

    Cryptographically bound by the control plane to exact input/output artifacts,
    attempt identities, and execution environment. Forms an append-only hash chain.
    """

    model_config = ConfigDict(extra="ignore", frozen=True)

    event_id: str = Field(default_factory=lambda: f"pe-dev-{uuid.uuid4().hex[:12]}")
    task_id: str
    workflow_id: str
    step_id: str
    attempt_id: str
    tenant_id: str = "default"
    work_region: str = "default"
    agent_id: str = "W_DEV"
    worker_role: str = "W_DEV"
    activity_id: str
    sandbox_id: str | None = None
    tool_id: str | None = None
    tool_version: str | None = None
    policy_version: str = "1.0.0"
    input_snapshot_hash: str
    output_snapshot_hash: str | None = None
    artifact_hashes: dict[str, str] = Field(default_factory=dict)
    action_digest: str | None = None
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    status: str = "SUCCESS"
    trace_id: str = Field(default_factory=lambda: f"tr-{uuid.uuid4().hex[:16]}")
    previous_event_hash: str | None = None
    event_hash: str = ""
    control_plane_signature: str | None = None
    evidence_ref: str | None = None
    w3c_prov: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def canonical_bytes(self) -> bytes:
        """Return deterministic JSON-serialized byte representation of canonical event fields."""
        return canonical_development_event_bytes(self)

    def compute_event_hash(self, prev_hash: str | None = None) -> str:
        """Compute tamper-evident SHA-256 digest chaining this event to its predecessor."""
        previous = prev_hash if prev_hash is not None else self.previous_event_hash
        payload = f"{previous or ''}|{self.task_id}|{self.step_id}|{self.attempt_id}|{self.activity_id}|{self.agent_id}|{self.input_snapshot_hash}|{self.output_snapshot_hash or ''}|{self.canonical_bytes().decode('utf-8')}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def verify_signature(
        self,
        public_key_pem: str | None = None,
        validator: Any | None = None,
    ) -> bool:
        """Verify control-plane signature over the event's canonical bytes."""
        if not self.control_plane_signature:
            return False
        if validator is not None and hasattr(validator, "verify"):
            return validator.verify(self.canonical_bytes(), self.control_plane_signature)
        if public_key_pem is not None:
            try:
                from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
                from cryptography.hazmat.primitives.serialization import load_pem_public_key

                pub = load_pem_public_key(public_key_pem.encode("ascii"))
                if isinstance(pub, Ed25519PublicKey):
                    try:
                        sig_bytes = base64.b64decode(self.control_plane_signature)
                    except Exception:
                        sig_bytes = bytes.fromhex(self.control_plane_signature)
                    pub.verify(sig_bytes, self.canonical_bytes())
                    return True
            except Exception:
                return False
        return False


def canonical_development_event_bytes(event: DevelopmentProvEvent) -> bytes:
    """Return canonical JSON-serialized bytes for signing or verifying a development provenance event.

    Deterministically binds:
    - event_id, task_id, workflow_id, step_id, attempt_id
    - tenant_id, work_region
    - agent_id, worker_role, activity_id, sandbox_id
    - tool_id, tool_version, policy_version
    - input_snapshot_hash, output_snapshot_hash, artifact_hashes
    - action_digest, occurred_at, status, trace_id, previous_event_hash
    - evidence_ref
    """
    occurred_iso = (
        event.occurred_at.isoformat()
        if event.occurred_at.tzinfo is not None
        else event.occurred_at.replace(tzinfo=UTC).isoformat()
    )
    payload = {
        "action_digest": event.action_digest or "",
        "activity_id": event.activity_id,
        "agent_id": event.agent_id,
        "artifact_hashes": event.artifact_hashes or {},
        "attempt_id": event.attempt_id,
        "event_id": event.event_id,
        "evidence_ref": event.evidence_ref or "",
        "input_snapshot_hash": event.input_snapshot_hash,
        "occurred_at": occurred_iso,
        "output_snapshot_hash": event.output_snapshot_hash or "",
        "policy_version": event.policy_version,
        "previous_event_hash": event.previous_event_hash or "",
        "sandbox_id": event.sandbox_id or "",
        "status": event.status,
        "step_id": event.step_id,
        "task_id": event.task_id,
        "tenant_id": event.tenant_id,
        "tool_id": event.tool_id or "",
        "tool_version": event.tool_version or "",
        "trace_id": event.trace_id,
        "work_region": event.work_region,
        "worker_role": event.worker_role,
        "workflow_id": event.workflow_id,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


# ---------------------------------------------------------------------------
# SLSA / In-Toto Attestation Models (DE-05 Task 12)
# ---------------------------------------------------------------------------

class SlsaResourceDescriptor(BaseModel):
    """In-toto / SLSA resource descriptor with cryptographic content digests."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    name: str
    digest: dict[str, str] = Field(default_factory=dict)
    annotations: dict[str, str] = Field(default_factory=dict)


class SlsaBuilder(BaseModel):
    """Builder identity executing the development sub-agent task."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    id: str


class SlsaBuildDefinition(BaseModel):
    """SLSA v1.0 BuildDefinition capturing buildType, external parameters, and dependencies."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    buildType: str = "https://enterprise_os.dev/attestations/development_engine/v1"
    externalParameters: dict[str, Any] = Field(default_factory=dict)
    internalParameters: dict[str, Any] = Field(default_factory=dict)
    resolvedDependencies: list[SlsaResourceDescriptor] = Field(default_factory=list)


class SlsaRunDetails(BaseModel):
    """SLSA v1.0 RunDetails capturing builder, invocation metadata, and timestamps."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    builder: SlsaBuilder
    metadata: dict[str, Any] = Field(default_factory=dict)


class SlsaProvenancePredicate(BaseModel):
    """SLSA v1.0 Provenance Predicate."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    buildDefinition: SlsaBuildDefinition
    runDetails: SlsaRunDetails


class InTotoStatement(BaseModel):
    """In-toto v1 Statement binding subject artifacts to a SLSA provenance predicate."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    _type: str = "https://in-toto.io/Statement/v1"
    subject: list[SlsaResourceDescriptor] = Field(default_factory=list)
    predicateType: str = "https://slsa.dev/provenance/v1"
    predicate: SlsaProvenancePredicate


# Backwards compatibility alias for earlier DE-01 references
class DevelopmentProvenanceRecord(DevelopmentProvEvent):
    """Backwards-compatible subclass representing a development provenance record."""
    pass
