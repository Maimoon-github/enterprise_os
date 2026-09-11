"""Persists and retrieves vector namespaces and embeddings."""
from __future__ import annotations


class VectorRepository:
    def __init__(self) -> None:
        self._namespaces: dict[str, list[dict]] = {}

    def upsert(self, namespace: str, documents: list[dict]) -> None:
        bucket = self._namespaces.setdefault(namespace, [])
        bucket.extend(documents)

    def query(self, namespace: str, query: str, limit: int = 10) -> list[dict]:
        return self._namespaces.get(namespace, [])[:limit]
