"""Persists and retrieves vector namespaces and embeddings.

The concrete embedding model and pgvector ANN indexing strategy were
unspecified by the source architecture (see ``docs/ASSUMPTIONS.md``). This
repository ships a deterministic hashing-trick embedding as its default
strategy and performs an in-Python cosine-similarity ranking, so retrieval
is fully functional without an external embedding provider configured.
Swapping in a real embedding provider only requires replacing
``_embed`` and, for scale, delegating ranking to pgvector's native
operators instead of the full in-process scan performed here.
"""

from __future__ import annotations

import hashlib
import math
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.persistence.database import metadata
from app.persistence.repositories.base import standard_table

_table = standard_table("vector_documents", metadata)
_EMBEDDING_DIM = 256


def _embed(text: str, dim: int = _EMBEDDING_DIM) -> list[float]:
    """Return a deterministic, dimension-stable hashing-trick embedding."""

    vector = [0.0] * dim
    for token in text.lower().split():
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        index = int(digest, 16) % dim
        vector[index] += 1.0
    norm = math.sqrt(sum(component * component for component in vector)) or 1.0
    return [component / norm for component in vector]


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    return max(0.0, min(1.0, dot))


class VectorRepository:
    """Stores embedded documents and serves cosine-similarity search."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def index_document(
        self,
        *,
        doc_id: str,
        tenant_id: str,
        text: str,
        source: str,
    ) -> None:
        """Embed and persist ``text`` under ``doc_id``, scoped to ``tenant_id``."""

        payload = {
            "doc_id": doc_id,
            "tenant_id": tenant_id,
            "text": text,
            "source": source,
            "embedding": _embed(text),
            "retrieved_at": datetime.now(UTC).isoformat(),
        }
        async with self._session_factory() as session:
            existing = await session.scalar(select(_table.c.id).where(_table.c.id == doc_id))
            if existing is None:
                await session.execute(
                    _table.insert().values(
                        id=doc_id,
                        tenant_id=tenant_id,
                        document=payload,
                        updated_at=datetime.now(UTC),
                    )
                )
            else:
                await session.execute(
                    _table.update()
                    .where(_table.c.id == doc_id)
                    .values(document=payload, updated_at=datetime.now(UTC))
                )
            await session.commit()

    async def similarity_search(
        self, *, tenant_id: str, query: str, top_k: int
    ) -> list[dict[str, Any]]:
        """Return the ``top_k`` documents for ``tenant_id`` ranked by cosine similarity."""

        query_vector = _embed(query)
        async with self._session_factory() as session:
            rows = await session.execute(
                select(_table.c.document).where(_table.c.tenant_id == tenant_id)
            )
            documents = [doc for (doc,) in rows.all()]

        scored = []
        for doc in documents:
            score = _cosine_similarity(query_vector, doc["embedding"])
            scored.append({**doc, "score": score})
        scored.sort(key=lambda d: d["score"], reverse=True)
        return scored[:top_k]