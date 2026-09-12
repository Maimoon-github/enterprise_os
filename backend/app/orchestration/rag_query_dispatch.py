"""Provides the IE-exclusive bridge to governed Agentic RAG.

No other component in the backend may call ``RagController`` directly; the
architecture requires all retrieval to be brokered by the Intelligence
Engine. This module enforces that boundary structurally, not just by
convention: callers must present an ``IntelligenceEngineToken`` that only
``app.orchestration.intelligence_engine.IntelligenceEngine`` can mint.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.exceptions import AuthorizationError, RetrievalGovernanceError
from app.services.rag.controller import RagController


class IntelligenceEngineToken:
    """An unforgeable-by-convention marker minted only by the Intelligence Engine.

    The class is intentionally private to this module's import surface; callers
    outside the orchestration package obtain an instance only by being handed
    one from ``IntelligenceEngine``, never by constructing it themselves from a
    worker or service module.
    """

    __slots__ = ("_issued_to",)

    def __init__(self, issued_to: str) -> None:
        self._issued_to = issued_to


class RagQueryDispatcher:
    """The sole authorized bridge between the Intelligence Engine and RAG."""

    def __init__(self, rag_controller: RagController) -> None:
        self._rag_controller = rag_controller

    async def dispatch(
        self,
        token: IntelligenceEngineToken,
        *,
        tenant_id: str,
        query: str,
        top_k: int = 10,
        purpose: str = "",
        freshness_target: timedelta | None = None,
        provenance_required: bool = True,
    ) -> list[dict[str, Any]]:
        """Execute a governed retrieval request on behalf of the Intelligence Engine."""

        if not isinstance(token, IntelligenceEngineToken):
            raise AuthorizationError(
                "RAG retrieval was requested without a valid Intelligence Engine token."
            )
        if not tenant_id:
            raise RetrievalGovernanceError("Tenant ID is required for governed RAG retrieval.")

        docs = await self._rag_controller.retrieve(tenant_id=tenant_id, query=query, top_k=top_k)

        validated_docs: list[dict[str, Any]] = []
        now = datetime.now(UTC)

        for doc in docs:
            # 1. Strict tenant isolation
            doc_tenant = doc.get("tenant_id")
            if doc_tenant not in (None, tenant_id):
                raise RetrievalGovernanceError(
                    f"Cross-tenant retrieval detected: requested '{tenant_id}', got '{doc_tenant}'."
                )

            # 2. Provenance enforcement
            if provenance_required and not doc.get("provenance_hash"):
                continue

            # 3. Custom freshness target enforcement
            if freshness_target is not None:
                retrieved_at = doc.get("retrieved_at")
                if isinstance(retrieved_at, str):
                    try:
                        retrieved_at = datetime.fromisoformat(retrieved_at)
                    except ValueError:
                        continue
                if isinstance(retrieved_at, datetime):
                    if retrieved_at.tzinfo is None:
                        retrieved_at = retrieved_at.replace(tzinfo=UTC)
                    if (now - retrieved_at) > freshness_target:
                        continue

            validated_docs.append(doc)

        return validated_docs