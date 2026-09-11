"""Coordinates authorized retrieval and ingestion requests for Agentic RAG."""

from __future__ import annotations

from typing import Any

from app.core.exceptions import RetrievalGovernanceError
from app.services.rag.freshness import FreshnessPolicy
from app.services.rag.hybrid_retriever import HybridRetriever
from app.services.rag.schema_validator import SchemaValidator


class RagController:
    """The single entrypoint for governed retrieval, called only via the
    Intelligence-Engine-exclusive ``RagQueryDispatcher`` bridge.
    """

    def __init__(
        self,
        retriever: HybridRetriever,
        freshness_policy: FreshnessPolicy | None = None,
        schema_validator: SchemaValidator | None = None,
    ) -> None:
        self._retriever = retriever
        self._freshness_policy = freshness_policy or FreshnessPolicy()
        self._schema_validator = schema_validator or SchemaValidator()

    async def retrieve(
        self, *, tenant_id: str, query: str, top_k: int = 10
    ) -> list[dict[str, Any]]:
        """Return validated, fresh, tenant-scoped documents for ``query``."""

        if not tenant_id:
            raise RetrievalGovernanceError("Retrieval requires a tenant id for isolation.")

        candidates = await self._retriever.retrieve(tenant_id=tenant_id, query=query, top_k=top_k)
        off_tenant = [doc for doc in candidates if doc.get("tenant_id") not in (None, tenant_id)]
        if off_tenant:
            raise RetrievalGovernanceError("Retriever returned documents outside tenant isolation.")

        valid = self._schema_validator.filter_valid(candidates)
        fresh = self._freshness_policy.filter_fresh(valid)
        return fresh