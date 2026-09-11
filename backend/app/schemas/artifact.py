"""UUID/hash-addressed deliverable and evidence references."""
from __future__ import annotations

from pydantic import BaseModel


class ArtifactRef(BaseModel):
    artifact_id: str
    content_hash: str
    uri: str
    media_type: str = "application/octet-stream"
