"""Resolves immutable deliverables by UUID/hash."""
from __future__ import annotations

from app.schemas.artifact import ArtifactRef


class ArtifactRepository:
    def __init__(self) -> None:
        self._store: dict[str, ArtifactRef] = {}

    def save(self, ref: ArtifactRef) -> None:
        self._store[ref.artifact_id] = ref

    def resolve(self, artifact_id: str) -> ArtifactRef | None:
        return self._store.get(artifact_id)
