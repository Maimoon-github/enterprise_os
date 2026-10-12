# pyright: reportMissingImports=false
"""Hybrid retriever for Enterprise OS (TSK-03).
Combines dense pgvector cosine similarity, sparse BM25 lexical search, and cross-reranking.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
import psycopg
from pydantic import BaseModel, Field
from rank_bm25 import BM25Okapi

from core.persistence import get_db_uri
from rag.ingestion import compute_dense_embedding


class RetrievalResult(BaseModel):
    """Structured search hit with component rank breakdown."""

    id: str
    partition: str
    doc_id: str
    title: str
    content: str
    score: float
    dense_score: float = 0.0
    sparse_score: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class HybridRetriever:
    """Hybrid search engine with dense pgvector search, BM25 lexical scoring, and RRF reranking."""

    def __init__(self, db_uri: Optional[str] = None, rrf_k: int = 60):
        self.db_uri = db_uri or get_db_uri()
        self.rrf_k = rrf_k

    def _get_connection(self) -> psycopg.Connection:
        return psycopg.connect(self.db_uri)

    def _dense_search(
        self,
        query: str,
        partition: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Dense vector cosine similarity search in pgvector."""
        query_emb = compute_dense_embedding(query)
        sql = """
            SELECT id, partition, doc_id, title, content, metadata,
                   1 - (embedding <=> %s::vector) AS similarity
            FROM knowledge_documents
        """
        params: list = [str(query_emb)]
        if partition:
            sql += " WHERE partition = %s"
            params.append(partition)
        sql += " ORDER BY embedding <=> %s::vector LIMIT %s;"
        params.extend([str(query_emb), limit])

        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
                return [
                    {
                        "id": str(r[0]),
                        "partition": r[1],
                        "doc_id": r[2],
                        "title": r[3],
                        "content": r[4],
                        "metadata": r[5],
                        "similarity": float(r[6]),
                    }
                    for r in rows
                ]

    def _sparse_search(
        self,
        query: str,
        partition: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Sparse BM25 lexical search over documents in the partition."""
        sql = "SELECT id, partition, doc_id, title, content, metadata FROM knowledge_documents"
        params: list = []
        if partition:
            sql += " WHERE partition = %s"
            params.append(partition)
        sql += " LIMIT 200;"

        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()

        if not rows:
            return []

        corpus = [r[4] for r in rows]
        tokenized_corpus = [re.findall(r"\w+", doc.lower()) for doc in corpus]
        bm25 = BM25Okapi(tokenized_corpus)

        tokenized_query = re.findall(r"\w+", query.lower())
        if not tokenized_query:
            return []

        doc_scores = bm25.get_scores(tokenized_query)
        scored_indices = sorted(range(len(doc_scores)), key=lambda i: doc_scores[i], reverse=True)[:limit]

        results = []
        for idx in scored_indices:
            r = rows[idx]
            results.append(
                {
                    "id": str(r[0]),
                    "partition": r[1],
                    "doc_id": r[2],
                    "title": r[3],
                    "content": r[4],
                    "metadata": r[5],
                    "bm25_score": float(doc_scores[idx]),
                }
            )
        return results

    def _cross_rerank(
        self,
        query: str,
        dense_hits: List[Dict[str, Any]],
        sparse_hits: List[Dict[str, Any]],
        top_k: int = 5,
    ) -> List[RetrievalResult]:
        """Reciprocal Rank Fusion (RRF) with exact-match cross-entropy weighting."""
        candidates: Dict[str, Dict[str, Any]] = {}
        query_terms = set(re.findall(r"\w+", query.lower()))

        # Score dense rank
        for rank, hit in enumerate(dense_hits):
            doc_id = hit["id"]
            if doc_id not in candidates:
                candidates[doc_id] = {**hit, "dense_score": hit["similarity"], "sparse_score": 0.0, "rrf": 0.0}
            candidates[doc_id]["rrf"] += 1.0 / (self.rrf_k + rank + 1)
            candidates[doc_id]["dense_score"] = hit["similarity"]

        # Score sparse rank
        for rank, hit in enumerate(sparse_hits):
            doc_id = hit["id"]
            if doc_id not in candidates:
                candidates[doc_id] = {**hit, "dense_score": 0.0, "sparse_score": hit["bm25_score"], "rrf": 0.0}
            candidates[doc_id]["rrf"] += 1.0 / (self.rrf_k + rank + 1)
            candidates[doc_id]["sparse_score"] = hit["bm25_score"]

        # Cross-encoder keyword boost
        final_list = []
        for doc in candidates.values():
            text_terms = set(re.findall(r"\w+", (doc["title"] + " " + doc["content"]).lower()))
            overlap = len(query_terms.intersection(text_terms)) / (len(query_terms) or 1)
            final_score = doc["rrf"] * 0.6 + doc["dense_score"] * 0.25 + overlap * 0.15
            final_list.append(
                RetrievalResult(
                    id=doc["id"],
                    partition=doc["partition"],
                    doc_id=doc["doc_id"],
                    title=doc["title"],
                    content=doc["content"],
                    score=round(final_score, 4),
                    dense_score=round(doc["dense_score"], 4),
                    sparse_score=round(doc["sparse_score"], 4),
                    metadata=doc.get("metadata", {}),
                )
            )

        final_list.sort(key=lambda x: x.score, reverse=True)
        return final_list[:top_k]

    def search(
        self,
        query: str,
        partition: Optional[str] = None,
        top_k: int = 5,
    ) -> List[RetrievalResult]:
        """Perform hybrid retrieval with dense vector, BM25, and reciprocal rank fusion."""
        dense_hits = self._dense_search(query, partition=partition, limit=top_k * 3)
        sparse_hits = self._sparse_search(query, partition=partition, limit=top_k * 3)
        return self._cross_rerank(query, dense_hits, sparse_hits, top_k=top_k)
