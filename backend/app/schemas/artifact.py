"""UUID/hash-addressed deliverable and evidence references."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from pydantic import BaseModel, Field


def compute_content_hash(content: str | bytes) -> str:
    """Compute deterministic SHA-256 content hash."""
    if isinstance(content, str):
        content = content.encode("utf-8")
    return hashlib.sha256(content).hexdigest()


class ArtifactReference(BaseModel):
    """An immutable reference to a stored deliverable or piece of evidence."""

    artifact_id: str
    content_hash: str
    uri: str
    media_type: str
    deliverable_type: str = "generic"
    metadata: dict[str, str] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))