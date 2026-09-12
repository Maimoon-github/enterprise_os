"""Coordinates authorized retrieval and ingestion requests for Agentic RAG."""

from __future__ import annotations

import hashlib
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
        data_gateway: Any | None = None,
    ) -> None:
        self._retriever = retriever
        self._freshness_policy = freshness_policy or FreshnessPolicy()
        self._schema_validator = schema_validator or SchemaValidator()
        self._data_gateway = data_gateway

    async def retrieve(
        self, *, tenant_id: str, query: str, top_k: int = 10
    ) -> list[dict[str, Any]]:
        """Return validated, fresh, tenant-scoped documents with provenance metadata for ``query``."""

        if not tenant_id:
            raise RetrievalGovernanceError("Retrieval requires a tenant id for isolation.")

        candidates = await self._retriever.retrieve(tenant_id=tenant_id, query=query, top_k=top_k)
        off_tenant = [doc for doc in candidates if doc.get("tenant_id") not in (None, tenant_id)]
        if off_tenant:
            raise RetrievalGovernanceError("Retriever returned documents outside tenant isolation.")

        valid = self._schema_validator.filter_valid(candidates)
        fresh = self._freshness_policy.filter_fresh(valid)

        for doc in fresh:
            if "provenance_hash" not in doc:
                raw_sig = f"{doc.get('source', 'rag')}::{tenant_id}::{str(doc.get('text', '')).strip()}"
                doc["provenance_hash"] = hashlib.sha256(raw_sig.encode("utf-8")).hexdigest()
            if "source_authority" not in doc:
                doc["source_authority"] = doc.get("source", "governed_knowledge_store")

        return fresh

    async def ingest(
        self,
        *,
        tenant_id: str,
        doc_id: str,
        text: str,
        source: str,
    ) -> None:
        """Ingest a knowledge document through the Governed MCP Data Gateway."""
        if not tenant_id:
            raise RetrievalGovernanceError("Ingestion requires a tenant id for isolation.")
        if self._data_gateway is not None:
            from app.schemas.governance import RiskLevel, TenantScope
            from app.security.authorization_boundary import CallerIdentity

            caller = CallerIdentity(
                subject="rag_controller",
                tenant_scope=TenantScope(tenant_id=tenant_id),
                risk_ceiling=RiskLevel.MEDIUM,
            )
            await self._data_gateway.ingest(
                caller, tenant_id=tenant_id, doc_id=doc_id, text=text, source=source
            )