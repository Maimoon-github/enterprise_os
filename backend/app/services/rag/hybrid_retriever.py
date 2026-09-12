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


def _bm25_score(query: str, text: str, avg_doc_len: float = 50.0, k1: float = 1.5, b: float = 0.75) -> float:
    """Return a BM25 normalized keyword relevance score in [0, 1]."""
    query_terms = [t.lower() for t in query.split() if t]
    if not query_terms:
        return 0.0
    text_terms = [t.lower() for t in text.split() if t]
    doc_len = len(text_terms)
    if doc_len == 0:
        return 0.0

    score = 0.0
    for q in set(query_terms):
        tf = text_terms.count(q)
        if tf > 0:
            numerator = tf * (k1 + 1)
            denominator = tf + k1 * (1 - b + b * (doc_len / avg_doc_len))
            score += numerator / denominator

    max_possible = len(set(query_terms)) * (k1 + 1)
    return min(1.0, score / max_possible) if max_possible > 0 else 0.0


def _keyword_score(query: str, text: str) -> float:
    """Keyword score combining exact token overlap and BM25 term saturation."""
    query_terms = {term.lower() for term in query.split() if term}
    if not query_terms:
        return 0.0
    text_terms = {term.lower() for term in text.split() if term}
    overlap = len(query_terms & text_terms) / len(query_terms)
    bm25 = _bm25_score(query, text)
    return 0.5 * overlap + 0.5 * bm25


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