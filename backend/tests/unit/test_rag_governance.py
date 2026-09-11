"""Verifies IE-only RAG access, tenant isolation, freshness, and validation."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from app.core.exceptions import AuthorizationError, RetrievalGovernanceError
from app.orchestration.rag_query_dispatch import IntelligenceEngineToken, RagQueryDispatcher
from app.services.rag.controller import RagController
from app.services.rag.freshness import FreshnessPolicy
from app.services.rag.hybrid_retriever import HybridRetriever
from app.services.rag.schema_validator import SchemaValidator
from tests.conftest import FakeVectorRepository


@pytest.mark.asyncio
async def test_rag_query_dispatch_requires_intelligence_engine_token() -> None:
    controller = RagController(HybridRetriever(FakeVectorRepository()))
    dispatcher = RagQueryDispatcher(controller)

    with pytest.raises(AuthorizationError):
        await dispatcher.dispatch(object(), tenant_id="acme", query="anything")  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_rag_query_dispatch_succeeds_with_valid_token() -> None:
    vector_repository = FakeVectorRepository()
    vector_repository.seed(tenant_id="acme", text="summer campaign performance summary")
    controller = RagController(HybridRetriever(vector_repository))
    dispatcher = RagQueryDispatcher(controller)
    token = IntelligenceEngineToken(issued_to="intelligence_engine")

    results = await dispatcher.dispatch(token, tenant_id="acme", query="summer campaign")

    assert len(results) == 1
    assert results[0]["tenant_id"] == "acme"


@pytest.mark.asyncio
async def test_rag_controller_rejects_cross_tenant_documents() -> None:
    class LeakyVectorRepository:
        """Simulates a misbehaving retriever that ignores tenant filtering."""

        async def similarity_search(self, *, tenant_id: str, query: str, top_k: int):
            return [
                {
                    "doc_id": "leaked",
                    "tenant_id": "other-tenant",
                    "text": "leaked document",
                    "source": "test",
                    "retrieved_at": datetime.now(UTC),
                    "score": 0.9,
                }
            ]

    controller = RagController(HybridRetriever(LeakyVectorRepository()))

    with pytest.raises(RetrievalGovernanceError):
        await controller.retrieve(tenant_id="acme", query="leaked")


def test_freshness_policy_filters_stale_documents(
    fresh_document: dict[str, Any], stale_document: dict[str, Any]
) -> None:
    policy = FreshnessPolicy()

    filtered = policy.filter_fresh([fresh_document, stale_document])

    assert filtered == [fresh_document]


def test_schema_validator_rejects_incomplete_documents(fresh_document: dict[str, Any]) -> None:
    validator = SchemaValidator()
    incomplete = {"doc_id": "x", "tenant_id": "acme"}

    filtered = validator.filter_valid([fresh_document, incomplete])

    assert filtered == [fresh_document]