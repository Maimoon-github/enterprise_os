"""UUID/hash-addressed deliverable and evidence references."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class ArtifactReference(BaseModel):
    """An immutable reference to a stored deliverable or piece of evidence."""

    artifact_id: str
    content_hash: str
    uri: str
    media_type: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))