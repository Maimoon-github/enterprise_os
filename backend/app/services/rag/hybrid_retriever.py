"""Performs required vector/BM25 hybrid retrieval.

The retriever is deliberately decoupled from any concrete vector store
implementation: it depends only on the ``VectorRepository`` protocol so it
can be exercised in unit tests against an in-memory fake and in production
against the pgvector-backed repository.
"""

from __future__ import annotations

from typing import Any, Protocol


class VectorRepository(Protocol):
    """The subset of vector-repository behavior the retriever depends on."""

    async def similarity_search(
        self, *, tenant_id: str, query: str, top_k: int
    ) -> list[dict[str, Any]]:
        ...


def _keyword_score(query: str, text: str) -> float:
    """Return a simple normalized keyword-overlap score in ``[0, 1]``."""

    query_terms = {term.lower() for term in query.split() if term}
    if not query_terms:
        return 0.0
    text_terms = {term.lower() for term in text.split() if term}
    overlap = query_terms & text_terms
    return len(overlap) / len(query_terms)


class HybridRetriever:
    """Combines dense vector similarity with sparse keyword overlap scoring."""

    def __init__(self, vector_repository: VectorRepository, *, vector_weight: float = 0.7) -> None:
        self._vector_repository = vector_repository
        self._vector_weight = vector_weight
        self._keyword_weight = 1.0 - vector_weight

    async def retrieve(
        self, *, tenant_id: str, query: str, top_k: int = 10
    ) -> list[dict[str, Any]]:
        """Return documents ranked by a blended vector/keyword score."""

        candidates = await self._vector_repository.similarity_search(
            tenant_id=tenant_id, query=query, top_k=top_k
        )
        scored: list[dict[str, Any]] = []
        for doc in candidates:
            vector_score = float(doc.get("score", 0.0))
            keyword_score = _keyword_score(query, str(doc.get("text", "")))
            blended = (self._vector_weight * vector_score) + (self._keyword_weight * keyword_score)
            scored.append({**doc, "blended_score": blended})
        scored.sort(key=lambda d: d["blended_score"], reverse=True)
        return scored[:top_k]