# pyright: reportMissingImports=false
"""Document chunking and pgvector partition indexing for Enterprise OS (TSK-03).
Ingests brand core materials and playbook research with partition isolation.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any, Dict, List, Optional
import psycopg
from core.persistence import get_db_uri


def compute_dense_embedding(text: str, dim: int = 1536) -> List[float]:
    """Generate normalized dense embedding vector without unproxied external API calls."""
    vec = [0.0] * dim
    tokens = re.findall(r"\w+", text.lower())
    if not tokens:
        tokens = ["empty"]
    for i, token in enumerate(tokens):
        # Stable deterministic projection into embedding space
        h = int(hashlib.sha256(token.encode("utf-8")).hexdigest(), 16)
        idx = h % dim
        sign = 1.0 if ((h >> 16) & 1) else -1.0
        vec[idx] += sign * (1.0 + 1.0 / (1.0 + i * 0.1))

    # L2 normalize
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


class DocumentChunker:
    """Sliding-window character and sentence chunker."""

    def __init__(self, chunk_size: int = 400, chunk_overlap: int = 80):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_text(self, text: str) -> List[str]:
        """Split text into overlapping semantic passages."""
        text = text.strip()
        if len(text) <= self.chunk_size:
            return [text]

        chunks = []
        start = 0
        while start < len(text):
            end = start + self.chunk_size
            if end < len(text):
                # Try to break on sentence or newline boundary
                boundary = text.rfind(". ", start, end)
                if boundary == -1:
                    boundary = text.rfind("\n", start, end)
                if boundary != -1 and boundary > start + (self.chunk_size // 2):
                    end = boundary + 1
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            start = end - self.chunk_overlap
            if start >= len(text) - self.chunk_overlap:
                break
        return chunks


class DocumentIndexer:
    """Indexes chunked documents into PostgreSQL with pgvector partitioned by domain."""

    def __init__(self, db_uri: Optional[str] = None):
        self.db_uri = db_uri or get_db_uri()
        self.chunker = DocumentChunker()

    def _get_connection(self) -> psycopg.Connection:
        return psycopg.connect(self.db_uri)

    def index_document(
        self,
        partition: str,
        doc_id: str,
        title: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        """Chunk, embed, and store document under the specified partition."""
        chunks = self.chunker.chunk_text(content)
        metadata_dict = metadata or {}
        inserted_ids = []

        with self._get_connection() as conn:
            with conn.cursor() as cur:
                for idx, chunk in enumerate(chunks):
                    emb = compute_dense_embedding(f"{title} {chunk}")
                    cur.execute(
                        """
                        INSERT INTO knowledge_documents (partition, doc_id, title, chunk_index, content, metadata, embedding)
                        VALUES (%s, %s, %s, %s, %s, %s, %s::vector)
                        RETURNING id;
                        """,
                        (
                            partition,
                            doc_id,
                            title,
                            idx,
                            chunk,
                            json.dumps(metadata_dict),
                            str(emb),
                        ),
                    )
                    row = cur.fetchone()
                    if row is not None:
                        inserted_ids.append(str(row[0]))
                conn.commit()
        return inserted_ids

    def index_brand_core(
        self,
        doc_id: str,
        title: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        """Index brand assets (manifestos, founder stories, value props) into 'brand_core'."""
        meta = metadata or {}
        meta["category"] = "brand_identity"
        return self.index_document("brand_core", doc_id, title, content, meta)

    def index_playbook(
        self,
        doc_id: str,
        title: str,
        content: str,
        category: str = "cro_heuristics",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        """Index industry heuristics (Baymard, algorithms, SEO) into 'playbooks_research'."""
        meta = metadata or {}
        meta["category"] = category
        return self.index_document("playbooks_research", doc_id, title, content, meta)
