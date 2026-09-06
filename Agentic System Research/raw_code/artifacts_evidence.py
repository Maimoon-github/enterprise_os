# File: artifacts_evidence.py
"""
Layer 6: Artifacts & Evidence.

Permanent, inspectable outputs stored outside model context:
- Artifacts are strictly immutable; updates create new versioned derivatives.
- Light-weight references (URI, UUID, SHA-256 content hash) exposed to model context.
- Evidence carries source authority, chunk ID, and provenance hashes.
- Deep integration with W3C PROV audit logging.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

from audit_provenance import ImmutableAuditLedger, ProvRelationType

logger = logging.getLogger("artifacts_evidence")


@dataclasses.dataclass(frozen=True)
class ArtifactReference:
    """Stable, token-light identifier passed into model contexts."""
    artifact_id: str
    tenant_id: str
    name: str
    version: int
    content_hash: str
    storage_uri: str
    mime_type: str


@dataclasses.dataclass(frozen=True)
class EvidenceRecord:
    """Retrieved evidence item retaining complete source and retrieval metadata."""
    evidence_id: str
    source_uri: str
    source_authority: str
    tenant_id: str
    content: str
    version: str
    effective_timestamp: datetime
    observed_timestamp: datetime
    provenance_hash: str
    relevance_score: float = 0.0

    def verify_provenance(self) -> bool:
        raw = f"{self.source_uri}::{self.version}::{self.content.strip()}"
        computed = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return self.provenance_hash == computed


@dataclasses.dataclass(frozen=True)
class Artifact:
    """Immutable deliverable persisted outside model context."""
    artifact_id: str
    tenant_id: str
    brand_id: str
    name: str
    version: int
    parent_artifact_id: Optional[str]
    content_hash: str
    storage_uri: str
    content_payload: str
    mime_type: str
    created_by_agent: str
    created_at: datetime
    is_approved: bool
    evidence_refs: Tuple[str, ...] = ()
    metadata: Dict[str, Any] = dataclasses.field(default_factory=dict)

    def to_reference(self) -> ArtifactReference:
        return ArtifactReference(
            artifact_id=self.artifact_id,
            tenant_id=self.tenant_id,
            name=self.name,
            version=self.version,
            content_hash=self.content_hash,
            storage_uri=self.storage_uri,
            mime_type=self.mime_type
        )


class ArtifactRegistry:
    """
    Persistent store for deliverables and inspectable outputs.
    Artifacts cannot be overwritten in place; modifications yield new derivatives.
    """

    def __init__(self, base_storage_uri: str = "s3://enterprise-artifact-registry",
                 audit_ledger: Optional[ImmutableAuditLedger] = None):
        self.base_storage_uri = base_storage_uri.rstrip("/")
        self.audit_ledger = audit_ledger
        self._artifacts: Dict[str, Artifact] = {}
        self._evidence: Dict[str, EvidenceRecord] = {}
        self._lineage: Dict[str, List[str]] = {}  # name -> [artifact_ids]

    @staticmethod
    def compute_hash(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def record_evidence(self, source_uri: str, source_authority: str, tenant_id: str,
                        content: str, version: str, effective_timestamp: datetime) -> EvidenceRecord:
        now = datetime.now(timezone.utc)
        raw = f"{source_uri}::{version}::{content.strip()}"
        prov_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        ev_id = f"ev_{uuid.uuid4().hex[:10]}"

        ev = EvidenceRecord(
            evidence_id=ev_id,
            source_uri=source_uri,
            source_authority=source_authority,
            tenant_id=tenant_id,
            content=content,
            version=version,
            effective_timestamp=effective_timestamp,
            observed_timestamp=now,
            provenance_hash=prov_hash
        )
        self._evidence[ev_id] = ev

        if self.audit_ledger:
            self.audit_ledger.record_entity(ev_id, "EvidenceRecord", {"source_uri": source_uri, "hash": prov_hash})
            self.audit_ledger.append_entry(
                actor_id=source_authority,
                action_type="EVIDENCE_RECORDED",
                details={"evidence_id": ev_id, "source_uri": source_uri, "hash": prov_hash}
            )

        return ev

    def register_artifact(self, tenant_id: str, brand_id: str, name: str,
                          content_payload: str, mime_type: str,
                          created_by_agent: str, evidence_refs: Optional[Sequence[str]] = None,
                          metadata: Optional[Dict[str, Any]] = None) -> Artifact:
        artifact_id = f"art_{uuid.uuid4().hex[:12]}"
        content_hash = self.compute_hash(content_payload)
        storage_uri = f"{self.base_storage_uri}/{tenant_id}/{name}/v1/{content_hash[:12]}"

        artifact = Artifact(
            artifact_id=artifact_id,
            tenant_id=tenant_id,
            brand_id=brand_id,
            name=name,
            version=1,
            parent_artifact_id=None,
            content_hash=content_hash,
            storage_uri=storage_uri,
            content_payload=content_payload,
            mime_type=mime_type,
            created_by_agent=created_by_agent,
            created_at=datetime.now(timezone.utc),
            is_approved=False,
            evidence_refs=tuple(evidence_refs or ()),
            metadata=metadata or {}
        )
        self._artifacts[artifact_id] = artifact
        self._lineage[name] = [artifact_id]

        if self.audit_ledger:
            self.audit_ledger.record_entity(artifact_id, "Artifact", {"name": name, "version": 1, "hash": content_hash})
            self.audit_ledger.append_entry(
                actor_id=created_by_agent,
                action_type="ARTIFACT_REGISTERED",
                details={"artifact_id": artifact_id, "name": name, "version": 1, "hash": content_hash}
            )
            for ev_ref in (evidence_refs or ()):
                self.audit_ledger.record_prov_statement(
                    relation=ProvRelationType.USED,
                    subject_id=artifact_id,
                    object_id=ev_ref,
                    metadata={"role": "supporting_evidence"}
                )

        logger.info("Registered initial artifact %s ('%s' v1)", artifact_id, name)
        return artifact

    def create_derivative(self, parent_artifact_id: str, content_payload: str,
                          created_by_agent: str, evidence_refs: Optional[Sequence[str]] = None,
                          metadata: Optional[Dict[str, Any]] = None) -> Artifact:
        """Enforces immutability: creates a new derivative version linked to parent."""
        if parent_artifact_id not in self._artifacts:
            raise KeyError(f"Parent artifact '{parent_artifact_id}' does not exist.")

        parent = self._artifacts[parent_artifact_id]
        new_version = parent.version + 1
        new_id = f"art_{uuid.uuid4().hex[:12]}"
        new_hash = self.compute_hash(content_payload)
        new_storage_uri = f"{self.base_storage_uri}/{parent.tenant_id}/{parent.name}/v{new_version}/{new_hash[:12]}"

        derivative = Artifact(
            artifact_id=new_id,
            tenant_id=parent.tenant_id,
            brand_id=parent.brand_id,
            name=parent.name,
            version=new_version,
            parent_artifact_id=parent_artifact_id,
            content_hash=new_hash,
            storage_uri=new_storage_uri,
            content_payload=content_payload,
            mime_type=parent.mime_type,
            created_by_agent=created_by_agent,
            created_at=datetime.now(timezone.utc),
            is_approved=False,
            evidence_refs=tuple(evidence_refs or parent.evidence_refs),
            metadata=metadata or parent.metadata
        )
        self._artifacts[new_id] = derivative
        self._lineage[parent.name].append(new_id)

        if self.audit_ledger:
            self.audit_ledger.record_entity(new_id, "ArtifactDerivative", {"name": parent.name, "version": new_version, "hash": new_hash})
            self.audit_ledger.record_prov_statement(
                relation=ProvRelationType.WAS_DERIVED_FROM,
                subject_id=new_id,
                object_id=parent_artifact_id,
                metadata={"version_transition": f"{parent.version}->{new_version}"}
            )
            self.audit_ledger.append_entry(
                actor_id=created_by_agent,
                action_type="ARTIFACT_DERIVATIVE_CREATED",
                details={
                    "derivative_id": new_id,
                    "parent_id": parent_artifact_id,
                    "version": new_version,
                    "hash": new_hash
                }
            )

        logger.info("Created derivative artifact %s ('%s' v%d) derived from %s",
                    new_id, parent.name, new_version, parent_artifact_id)
        return derivative

    def get_artifact(self, artifact_id: str) -> Artifact:
        if artifact_id not in self._artifacts:
            raise KeyError(f"Artifact '{artifact_id}' not found.")
        return self._artifacts[artifact_id]

    def get_evidence(self, evidence_id: str) -> EvidenceRecord:
        if evidence_id not in self._evidence:
            raise KeyError(f"Evidence '{evidence_id}' not found.")
        return self._evidence[evidence_id]

    def resolve_reference(self, reference: ArtifactReference) -> Artifact:
        art = self.get_artifact(reference.artifact_id)
        if art.content_hash != reference.content_hash:
            raise ValueError(f"Artifact hash mismatch: expected {reference.content_hash}, got {art.content_hash}")
        return art