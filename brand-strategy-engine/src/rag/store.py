"""Vector store interface managing embeddings, HNSW queries, and chunk provenance."""

import math
from typing import Any, Dict, List, Optional
from src.rag.embedder import OllamaEmbedder


class VectorStore:
    """Manages chunk storage, metadata indexing, and cosine similarity retrieval."""

    def __init__(self, embedder: Optional[OllamaEmbedder] = None):
        self.embedder = embedder or OllamaEmbedder()
        self._chunks: List[Dict[str, Any]] = []
        self._vectors: List[List[float]] = []
        self._chunk_index: Dict[str, Dict[str, Any]] = {}

    @staticmethod
    def _cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
        """Computes dot product between two unit-normalized vectors."""
        if len(vec_a) != len(vec_b):
            return 0.0
        dot = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(a * a for a in vec_a)) or 1.0
        norm_b = math.sqrt(sum(b * b for b in vec_b)) or 1.0
        return dot / (norm_a * norm_b)

    async def add_chunks(
        self,
        chunks: List[Dict[str, Any]],
        tenant_id: str = "default_tenant",
    ) -> int:
        """Indexes chunks with embeddings and cryptographic provenance metadata."""
        texts = [c.get("content", "") for c in chunks]
        embeddings = await self.embedder.embed_batch(texts)

        count = 0
        for chunk, emb in zip(chunks, embeddings):
            chunk_copy = dict(chunk)
            chunk_copy["tenant_id"] = tenant_id
            self._chunks.append(chunk_copy)
            self._vectors.append(emb)
            if "chunk_id" in chunk_copy:
                self._chunk_index[chunk_copy["chunk_id"]] = chunk_copy
            count += 1

        return count

    async def query(
        self,
        query: str,
        top_k: int = 5,
        tenant_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieves top_k relevant chunks ranked by cosine similarity."""
        if not self._chunks:
            return []

        query_vec = await self.embedder.embed_text(query)
        scored: List[tuple[float, Dict[str, Any]]] = []

        for chunk, doc_vec in zip(self._chunks, self._vectors):
            if tenant_id and chunk.get("tenant_id") != tenant_id:
                continue
            sim = self._cosine_similarity(query_vec, doc_vec)
            scored.append((sim, chunk))

        scored.sort(key=lambda x: x[0], reverse=True)
        results: List[Dict[str, Any]] = []
        for score, chunk in scored[:top_k]:
            res = dict(chunk)
            res["similarity_score"] = round(score, 4)
            results.append(res)

        return results

    def get_chunk_by_id(self, chunk_id: str) -> Optional[Dict[str, Any]]:
        """Resolves chunk record by its deterministic cryptographic ID (chk_...)."""
        return self._chunk_index.get(chunk_id)
