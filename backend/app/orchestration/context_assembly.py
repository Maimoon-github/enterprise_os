"""Builds policy-screened context slices for workers.

Context is assembled exclusively through the IE-exclusive RAG bridge and the
brand persona resolver, so a worker never receives more than the task's
delegated scope permits.
"""

from __future__ import annotations

from app.orchestration.brand_persona import BrandPersonaResolver
from app.orchestration.rag_query_dispatch import IntelligenceEngineToken, RagQueryDispatcher
from app.schemas.agent_contracts import ContextRequest


class ContextAssembler:
    """Assembles the bounded context payload handed to a worker with its grant."""

    def __init__(
        self,
        rag_dispatcher: RagQueryDispatcher,
        brand_persona_resolver: BrandPersonaResolver | None = None,
    ) -> None:
        self._rag_dispatcher = rag_dispatcher
        self._brand_persona_resolver = brand_persona_resolver or BrandPersonaResolver()

    async def assemble(
        self,
        token: IntelligenceEngineToken,
        *,
        tenant_id: str,
        request: ContextRequest,
    ) -> dict[str, object]:
        """Return a context dict combining retrieved evidence and brand persona."""

        documents = await self._rag_dispatcher.dispatch(
            token, tenant_id=tenant_id, query=request.query, top_k=request.max_items
        )
        if hasattr(self._brand_persona_resolver, "resolve_with_memory"):
            persona = await self._brand_persona_resolver.resolve_with_memory(tenant_id=tenant_id)
        else:
            persona = self._brand_persona_resolver.resolve(tenant_id=tenant_id)
        return {
            "task_id": request.task_id,
            "worker_role": request.worker_role.value,
            "query": request.query,
            "documents": documents,
            "brand_persona": persona,
        }