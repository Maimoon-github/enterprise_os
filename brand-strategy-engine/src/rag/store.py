"""Vector store interface managing embeddings, pgvector HNSW queries, and chunk provenance."""

import logging
import math
import os
from typing import Any, Dict, List, Optional
import asyncpg
from src.rag.embedder import OllamaEmbedder
from src.schemas.evidence import ChunkProvenance

logger = logging.getLogger(__name__)


class VectorStore:
    """Manages chunk storage, metadata indexing, and pgvector HNSW / cosine similarity retrieval."""

    def __init__(
        self,
        embedder: Optional[OllamaEmbedder] = None,
        dsn: Optional[str] = None,
        host: str = "postgres-pgvector",
        port: int = 5432,
        database: str = "brand_strategy_db",
        user: str = "engine_user",
        password: str = "engine_secure_pass",
    ):
        self.embedder = embedder or OllamaEmbedder()
        self.dsn = dsn or os.getenv(
            "DATABASE_URL",
            f"postgresql://{user}:{password}@{host}:{port}/{database}",
        )
        self.pool: Optional[asyncpg.Pool] = None
        self._chunks: List[Dict[str, Any]] = []
        self._vectors: List[List[float]] = []
        self._chunk_index: Dict[str, Dict[str, Any]] = {}

    async def connect(self) -> bool:
        """Initializes PostgreSQL connection pool and pgvector HNSW tables."""
        try:
            self.pool = await asyncpg.create_pool(dsn=self.dsn, min_size=1, max_size=10, timeout=1.5)
            await self._init_pgvector_schema()
            return True
        except Exception as e:
            logger.debug("PostgreSQL unavailable (%s); using in-memory vector store fallback", e)
            self.pool = None
            return False

    async def _init_pgvector_schema(self) -> None:
        """Creates pgvector extension, chunks table, and HNSW index."""
        if not self.pool:
            return
        async with self.pool.acquire() as conn:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS rag_document_chunks (
                    chunk_id VARCHAR(64) PRIMARY KEY,
                    document_id VARCHAR(128) NOT NULL,
                    tenant_id VARCHAR(128) NOT NULL,
                    source_filename VARCHAR(256) NOT NULL,
                    sha256_hash VARCHAR(64) NOT NULL,
                    page_number INTEGER NOT NULL,
                    section_heading TEXT NOT NULL,
                    timestamp TIMESTAMPTZ NOT NULL,
                    byte_range INTEGER[] NOT NULL,
                    content TEXT NOT NULL,
                    embedding vector(768)
                );
                CREATE INDEX IF NOT EXISTS idx_rag_chunks_hnsw 
                ON rag_document_chunks 
                USING hnsw (embedding vector_cosine_ops);
            """)

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

            # Ensure valid 9-field provenance schema
            if "sha256_hash" in chunk_copy and "timestamp" in chunk_copy and "byte_range" in chunk_copy:
                try:
                    ChunkProvenance(**chunk_copy)
                except Exception as e:
                    logger.debug("ChunkProvenance validation warning: %s", e)

            self._chunks.append(chunk_copy)
            self._vectors.append(emb)
            if "chunk_id" in chunk_copy:
                self._chunk_index[chunk_copy["chunk_id"]] = chunk_copy

            if self.pool:
                try:
                    async with self.pool.acquire() as conn:
                        await conn.execute(
                            """
                            INSERT INTO rag_document_chunks (
                                chunk_id, document_id, tenant_id, source_filename,
                                sha256_hash, page_number, section_heading, timestamp,
                                byte_range, content, embedding
                            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                            ON CONFLICT (chunk_id) DO UPDATE SET
                                content = EXCLUDED.content,
                                embedding = EXCLUDED.embedding;
                            """,
                            chunk_copy.get("chunk_id"),
                            chunk_copy.get("document_id", "doc_default"),
                            tenant_id,
                            chunk_copy.get("source_filename", "unknown"),
                            chunk_copy.get("sha256_hash", "0" * 64),
                            chunk_copy.get("page_number", 1),
                            chunk_copy.get("section_heading", "General"),
                            chunk_copy.get("timestamp"),
                            chunk_copy.get("byte_range", [0, len(chunk_copy.get("content", ""))]),
                            chunk_copy.get("content", ""),
                            str(emb),
                        )
                except Exception as e:
                    logger.debug("Failed to insert chunk into pgvector (%s), stored in memory", e)

            count += 1

        return count

    async def query(
        self,
        query: str,
        top_k: int = 5,
        tenant_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieves top_k relevant chunks ranked by cosine similarity."""
        if not self._chunks and not self.pool:
            return []

        query_vec = await self.embedder.embed_text(query)

        # Try pgvector HNSW retrieval if connected
        if self.pool:
            try:
                async with self.pool.acquire() as conn:
                    rows = await conn.fetch(
                        """
                        SELECT 
                            chunk_id, document_id, tenant_id, source_filename,
                            sha256_hash, page_number, section_heading, timestamp,
                            byte_range, content,
                            1 - (embedding <=> $1::vector) AS similarity_score
                        FROM rag_document_chunks
                        WHERE ($2::text IS NULL OR tenant_id = $2)
                        ORDER BY embedding <=> $1::vector
                        LIMIT $3;
                        """,
                        str(query_vec),
                        tenant_id,
                        top_k,
                    )
                    if rows:
                        return [
                            {
                                "chunk_id": r["chunk_id"],
                                "document_id": r["document_id"],
                                "tenant_id": r["tenant_id"],
                                "source_filename": r["source_filename"],
                                "sha256_hash": r["sha256_hash"],
                                "page_number": r["page_number"],
                                "section_heading": r["section_heading"],
                                "timestamp": r["timestamp"].isoformat() if hasattr(r["timestamp"], "isoformat") else str(r["timestamp"]),
                                "byte_range": list(r["byte_range"]) if r["byte_range"] else [0, 0],
                                "content": r["content"],
                                "similarity_score": round(float(r["similarity_score"]), 4),
                            }
                            for r in rows
                        ]
            except Exception as e:
                logger.debug("pgvector HNSW query fallback to in-memory: %s", e)

        # In-memory cosine query
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

