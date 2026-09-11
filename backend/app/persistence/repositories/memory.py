"""Persists promoted brand knowledge, heuristics, and model deltas."""
from __future__ import annotations


class MemoryRepository:
    def __init__(self) -> None:
        self._store: dict[str, list[dict]] = {}

    def promote(self, tenant_id: str, delta: dict) -> None:
        self._store.setdefault(tenant_id, []).append(delta)

    def all(self, tenant_id: str) -> list[dict]:
        return list(self._store.get(tenant_id, []))
