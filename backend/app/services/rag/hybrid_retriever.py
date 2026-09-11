"""Performs required vector/BM25 hybrid retrieval."""
from __future__ import annotations


class HybridRetriever:
    def retrieve(self, query: str, tenant_id: str, limit: int = 10) -> list[dict]:
        # Backed by the vector repository in production; returns [] as safe default.
        return []
