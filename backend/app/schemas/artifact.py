"""UUID/hash-addressed deliverable and evidence references."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from pydantic import BaseModel, Field


from enum import StrEnum
from typing import Any


def compute_content_hash(content: str | bytes) -> str:
    """Compute deterministic SHA-256 content hash."""
    if isinstance(content, str):
        content = content.encode("utf-8")
    return hashlib.sha256(content).hexdigest()


class DeliverableType(StrEnum):
    """Recognized categories of immutable deliverables and evidence."""

    GENERIC = "generic"
    EVIDENCE_DOSSIER = "evidence_dossier"
    COPY_PACK = "copy_pack"
    RESEARCH_REPORT = "report"
    CODE_DIFF = "code_diff"
    STRUCTURED_OUTPUT = "structured_deliverable"
    ASSET = "generated_asset"
    VALIDATION_PACKAGE = "validation_package"


class ArtifactReference(BaseModel):
    """An immutable reference to a stored deliverable or piece of evidence."""

    artifact_id: str
    content_hash: str
    uri: str
    media_type: str
    deliverable_type: str = "generic"
    tenant_id: str | None = None
    name: str = ""
    version: int = 1
    creator_agent: str = ""
    provenance_ref: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @staticmethod
    def compute_hash(content: str | bytes) -> str:
        """Helper to compute deterministic SHA-256 content hash."""
        return compute_content_hash(content)

    def verify_integrity(self, content: str | bytes) -> bool:
        """Verify whether candidate content matches the recorded SHA-256 hash."""
        return compute_content_hash(content) == self.content_hash


class EvidenceRecord(BaseModel):
    """Retrieved evidence item carrying source authority and provenance attestation."""

    evidence_id: str
    source_uri: str
    source_authority: str
    tenant_id: str
    content: str
    version: str = "1.0"
    provenance_hash: str
    relevance_score: float = 0.0
    effective_timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    observed_timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def verify_provenance(self) -> bool:
        """Verify that the evidence provenance hash matches its content signature."""
        raw = f"{self.source_uri}::{self.version}::{self.content.strip()}"
        return self.provenance_hash == compute_content_hash(raw)