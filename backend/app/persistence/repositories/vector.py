"""Persists and retrieves vector namespaces and embeddings.

Provides tenant and namespace-isolated vector indexing and retrieval.
Exact nearest-neighbor cosine similarity serves as the correctness baseline,
with configurable approximate nearest-neighbor (ANN) search available.
"""

from __future__ import annotations

import hashlib
import math
from datetime import UTC, datetime
from typing import Any, Sequence

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.exceptions import RepositoryError
from app.persistence.database import metadata
from app.persistence.repositories.base import standard_table

_table = standard_table("vector_documents", metadata)
_DEFAULT_DIM = 256
_DEFAULT_MODEL = "deterministic-hash-256"
_DEFAULT_METRIC = "cosine"


def _embed(text_content: str, dim: int = _DEFAULT_DIM) -> list[float]:
    """Return a deterministic, dimension-stable hashing-trick embedding."""
    vector = [0.0] * dim
    for token in text_content.lower().split():
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        index = int(digest, 16) % dim
        vector[index] += 1.0
    norm = math.sqrt(sum(component * component for component in vector)) or 1.0
    return [component / norm for component in vector]


def _cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """Compute cosine similarity between two unit-normalized vectors."""
    if len(a) != len(b):
        raise ValueError(f"Vector dimension mismatch: {len(a)} != {len(b)}")
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    return max(0.0, min(1.0, dot))


class VectorRepository:
    """Stores embedded documents and serves exact & ANN cosine-similarity search."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
        *,
        dimension: int = _DEFAULT_DIM,
        model: str = _DEFAULT_MODEL,
        metric: str = _DEFAULT_METRIC,
    ) -> None:
        self._session_factory = session_factory
        self._dimension = dimension
        self._model = model
        self._metric = metric

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def metric(self) -> str:
        return self._metric

    @property
    def model(self) -> str:
        return self._model

    async def _apply_tenant_context(self, session: AsyncSession, tenant_id: str) -> None:
        try:
            await session.execute(
                text("SET LOCAL app.current_tenant = :tenant_id"),
                {"tenant_id": tenant_id},
            )
        except Exception:
            pass

    async def index_document(
        self,
        *,
        doc_id: str,
        tenant_id: str,
        text: str,
        source: str,
        namespace: str = "default",
        embedding: list[float] | None = None,
        model: str | None = None,
        metric: str | None = None,
        session: AsyncSession | None = None,
    ) -> None:
        """Embed and persist ``text`` under ``doc_id``, bound to ``tenant_id`` and ``namespace``.

        Fails closed on missing tenant/doc IDs, cross-tenant overwrites, or dimension mismatch.
        """
        if not tenant_id or not isinstance(tenant_id, str) or not tenant_id.strip():
            raise RepositoryError("Tenant ID cannot be empty.")
        if not doc_id or not isinstance(doc_id, str) or not doc_id.strip():
            raise RepositoryError("Doc ID cannot be empty.")

        ns = (namespace or "default").strip()
        emb_model = model or self._model
        emb_metric = metric or self._metric

        if emb_metric != "cosine":
            raise ValueError(f"Unsupported distance metric: '{emb_metric}'. Supported: ['cosine']")

        if embedding is not None:
            if len(embedding) != self._dimension:
                raise ValueError(
                    f"Embedding dimension mismatch: expected {self._dimension}, got {len(embedding)}"
                )
            vec = embedding
        else:
            vec = _embed(text, dim=self._dimension)

        payload = {
            "doc_id": doc_id,
            "tenant_id": tenant_id,
            "namespace": ns,
            "text": text,
            "source": source,
            "embedding": vec,
            "model": emb_model,
            "metric": emb_metric,
            "dimension": len(vec),
            "retrieved_at": datetime.now(UTC).isoformat(),
        }

        async def _execute_write(sess: AsyncSession) -> None:
            await self._apply_tenant_context(sess, tenant_id)
            existing_row = await sess.execute(
                select(_table.c.tenant_id).where(_table.c.id == doc_id)
            )
            existing_tenant = existing_row.scalar_one_or_none()

            if existing_tenant is not None and existing_tenant != tenant_id:
                raise RepositoryError(
                    f"Cross-tenant access violation: document '{doc_id}' does not belong to tenant '{tenant_id}'."
                )

            if existing_tenant is None:
                await sess.execute(
                    _table.insert().values(
                        id=doc_id,
                        tenant_id=tenant_id,
                        document=payload,
                        updated_at=datetime.now(UTC),
                    )
                )
            else:
                await sess.execute(
                    _table.update()
                    .where((_table.c.id == doc_id) & (_table.c.tenant_id == tenant_id))
                    .values(document=payload, updated_at=datetime.now(UTC))
                )

        if session is not None:
            await _execute_write(session)
        else:
            if self._session_factory is None:
                raise RepositoryError("No session factory configured for VectorRepository.")
            async with self._session_factory() as local_sess:
                await _execute_write(local_sess)
                await local_sess.commit()

    async def similarity_search(
        self,
        *,
        tenant_id: str,
        query: str | None = None,
        query_vector: list[float] | None = None,
        top_k: int = 10,
        namespace: str | None = None,
        search_type: str = "exact",
        metric: str = "cosine",
        min_score: float = 0.0,
        ef_search: int = 40,
        session: AsyncSession | None = None,
    ) -> list[dict[str, Any]]:
        """Return the ``top_k`` documents for ``tenant_id`` and ``namespace``.

        Supports exact baseline nearest-neighbor search (`search_type='exact'`)
        or configurable ANN search (`search_type='ann'`).
        """
        if not tenant_id or not isinstance(tenant_id, str) or not tenant_id.strip():
            raise RepositoryError("Tenant ID cannot be empty.")
        if top_k <= 0:
            return []

        if metric != "cosine":
            raise ValueError(f"Unsupported distance metric: '{metric}'. Supported: ['cosine']")

        if query_vector is not None:
            if len(query_vector) != self._dimension:
                raise ValueError(
                    f"Query vector dimension mismatch: expected {self._dimension}, got {len(query_vector)}"
                )
            target_vec = query_vector
        elif query is not None:
            target_vec = _embed(query, dim=self._dimension)
        else:
            raise ValueError("Either query or query_vector must be provided.")

        stmt = select(_table.c.document).where(_table.c.tenant_id == tenant_id)
        if session is not None:
            await self._apply_tenant_context(session, tenant_id)
            rows = await session.execute(stmt)
            raw_docs = [doc for (doc,) in rows.all()]
        else:
            if self._session_factory is None:
                return []
            async with self._session_factory() as local_sess:
                await self._apply_tenant_context(local_sess, tenant_id)
                rows = await local_sess.execute(stmt)
                raw_docs = [doc for (doc,) in rows.all()]

        # Filter strictly by tenant and namespace
        target_ns = namespace.strip() if namespace else None
        candidates: list[dict[str, Any]] = []
        for doc in raw_docs:
            if not isinstance(doc, dict):
                continue
            if doc.get("tenant_id") != tenant_id:
                # Zero cross-tenant leakage defense-in-depth
                continue
            if target_ns is not None and doc.get("namespace", "default") != target_ns:
                continue
            candidates.append(doc)

        if not candidates:
            return []

        scored: list[dict[str, Any]] = []

        if search_type == "ann" and len(candidates) > ef_search:
            # Approximate nearest-neighbor: filter candidates using coordinate clustering/pruning
            subset = sorted(
                candidates,
                key=lambda d: sum(
                    x * y
                    for x, y in zip(target_vec[:32], d.get("embedding", [])[:32], strict=False)
                ),
                reverse=True,
            )[:ef_search]
            for doc in subset:
                doc_emb = doc.get("embedding")
                if not doc_emb or len(doc_emb) != len(target_vec):
                    continue
                score = _cosine_similarity(target_vec, doc_emb)
                if score >= min_score:
                    scored.append({**doc, "score": score, "search_mode": "ann"})
        else:
            # Exact nearest-neighbor baseline: linear scan across all tenant/ns candidates
            for doc in candidates:
                doc_emb = doc.get("embedding")
                if not doc_emb or len(doc_emb) != len(target_vec):
                    continue
                score = _cosine_similarity(target_vec, doc_emb)
                if score >= min_score:
                    scored.append({**doc, "score": score, "search_mode": "exact"})

        # Deterministic tie-breaking on score descending, doc_id ascending
        scored.sort(key=lambda d: (-d["score"], str(d.get("doc_id", ""))))
        return scored[:top_k]