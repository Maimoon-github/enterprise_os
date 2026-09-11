"""Coordinates authorized retrieval and ingestion requests."""
from __future__ import annotations

from app.services.rag.freshness import FreshnessPolicy
from app.services.rag.hybrid_retriever import HybridRetriever
from app.services.rag.schema_validator import SchemaValidator


class RagController:
    def __init__(
        self,
        retriever: HybridRetriever | None = None,
        freshness: FreshnessPolicy | None = None,
        validator: SchemaValidator | None = None,
    ) -> None:
        self.retriever = retriever or HybridRetriever()
        self.freshness = freshness or FreshnessPolicy()
        self.validator = validator or SchemaValidator()

    def query(self, query: str, tenant_id: str) -> dict:
        hits = self.retriever.retrieve(query, tenant_id)
        filtered = [h for h in hits if self.freshness.is_fresh(h)]
        validated = [h for h in filtered if self.validator.is_valid(h)]
        return {"query": query, "tenant_id": tenant_id, "results": validated}
